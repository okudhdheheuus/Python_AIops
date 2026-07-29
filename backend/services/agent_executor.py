import json
import re
import asyncio
import logging
import time as time_module
from datetime import datetime
from sqlalchemy import select
from .llm_service import call_llm
from .ssh_pool import pool
from .knowledge_service import build_rag_context
from ..database import AsyncSessionLocal
from ..models import Server, Alert, RemediationLog, RemediationPolicy

logger = logging.getLogger("itops")

# 危险命令黑名单 — 匹配到则拒绝执行
DANGEROUS_PATTERNS = [
    (r'\brm\s+-rf\s+/', "递归删除根目录"),
    (r'\bdd\s+if=', "裸磁盘写入(dd)"),
    (r'\bmkfs\.', "创建文件系统(mkfs)"),
    (r':\(\)\s*\{.*:\|:&.*\};:', "Fork炸弹"),
    (r'>\s*/dev/sd[a-z]', "覆盖裸设备"),
    (r'\bchmod\s+777\s+/', "修改根目录权限为777"),
    (r'\bchown\s+-R\s+\w+\s+/', "递归修改根目录所有者"),
    (r'\bshutdown\s+-h\s+now', "立即关机"),
    (r'\breboot\s+-f', "强制重启"),
    (r'\biptables\s+-F\b', "清空iptables规则"),
    (r'\bwget\s+.*\|.*sh\b', "管道执行远程脚本"),
    (r'\bcurl\s+.*\|.*sh\b', "管道执行远程脚本"),
    (r'\b>:\(\s*\)', "覆盖系统文件"),
    (r'>\s*/etc/', "覆盖/etc/配置文件"),
]


class AgentExecutor:
    """多Agent执行器 — AI驱动命令生成 + SSH执行 + AI分析"""

    AGENT_DESCRIPTIONS = {
        "generic": "通用IT运维助手",
        "diagnostic": "服务器故障诊断专家",
        "monitor": "系统指标采集Agent",
        "remediation": "自动修复执行Agent",
        "alert_analyzer": "告警分析与严重程度评估Agent",
        "log_analyzer": "日志分析与异常检测Agent",
        "change_executor": "变更执行与回滚Agent",
        "doc_generator": "运维文档与报告生成Agent",
        "compliance_checker": "合规检查Agent",
    }

    # 各Agent的"命令生成"角色Prompt —— 强分化，各司其职
    CMD_GEN_PROMPTS = {
        "monitor": (
            "You are a hardware metrics collection specialist. "
            "Your ONLY job: generate commands to read system resource data. "
            "Collect: CPU usage, CPU temperature (sensors / thermal_zone), memory usage, "
            "disk space and I/O, network throughput, load average, process count, swap usage. "
            "Use: top, free, df, iostat, vmstat, sensors, cat /sys/class/thermal/thermal_zone*/temp, "
            "cat /proc/cpuinfo, cat /proc/meminfo, uptime, sar, mpstat, ss, ps. "
            "Output raw numbers only — no interpretation, no fixes, no log checks. "
            "Only use read-only, non-intrusive commands. Never modify anything."
        ),
        "diagnostic": (
            "You are a server problem investigator. "
            "Your ONLY job: generate commands to find the root cause of a specific problem. "
            "Do NOT just dump all metrics — instead, think about the symptom and hunt for the cause. "
            "For slow response: check CPU/memory/IO/network bottlenecks, top processes, connection counts. "
            "For crashes: check dmesg, journalctl errors, coredumps, OOM killer logs. "
            "For service failure: check systemctl status, dependency chains, config file syntax. "
            "Structure: 1) quick symptom check 2) drill-down based on initial findings. "
            "Only use read-only commands — do NOT attempt any repair or restart."
        ),
        "remediation": (
            "You are a server repair operator. "
            "Your ONLY job: generate commands to FIX things — restart services, kill processes, "
            "cleanup resources, apply configuration changes. "
            "Focus on process and service management: systemctl restart/stop/start, "
            "kill/pkill for stuck processes, service reload, config validation. "
            "Structure EVERY action as: pre-check → repair action → verify success. "
            "Be conservative: prefer restarting a single service over rebooting, "
            "prefer reload over restart when possible. Report exact commands for rollback."
        ),
        "ai_remediation": (
            "You are an intelligent server repair specialist. "
            "You will receive an alert with specific details about what went wrong. "
            "Your job: 1) quickly verify the alert is accurate with pre-check commands, "
            "2) determine the root cause, 3) generate the safest fix commands, "
            "4) verify the fix worked. "
            "Structure: pre-check → diagnosis → repair → verify. "
            "For CPU alerts: identify the top process, check if it's stuck/spiking, "
            "restart only if necessary. For memory: find the leaking process, "
            "consider graceful restart. For disk: find large files/logs, clean safely. "
            "For service down: check dependencies, config files, then restart. "
            "Be conservative — never reboot, never kill system processes, "
            "never delete without confirmation of what you're deleting. "
            "Output the diagnostic finding as a comment before each fix command."
        ),
        "log_analyzer": (
            "You are a log extraction specialist. "
            "Your ONLY job: generate commands to pull and filter logs from the system. "
            "Use: journalctl with priority/unit/since filters, dmesg, "
            "tail -n / grep / awk on /var/log files (messages, secure, syslog, audit). "
            "Filter for: errors, warnings, failures, time ranges, specific services. "
            "Never collect metrics, never diagnose, never fix — ONLY pull logs. "
            "Limit to recent entries (last 500 lines or last 2 hours) to keep output manageable."
        ),
        "compliance_checker": (
            "You are a security baseline auditor. "
            "Your ONLY job: generate read-only check commands to verify security configuration. "
            "Check: SSH hardening (PermitRootLogin, PasswordAuthentication, Port), "
            "firewall status (firewalld/ufw/iptables), SELinux/AppArmor enforcement mode, "
            "password policy (minlen, complexity in pwquality.conf), "
            "empty passwords in /etc/shadow, world-writable files (find / -perm -0002), "
            "unnecessary listening ports (ss -tlnp), auditd/chronyd status, "
            "file permissions on critical paths (/etc/passwd, /etc/shadow, /etc/sudoers). "
            "Each check must output a clear indicator so results can be scored. "
            "Never modify any configuration — only report the current state."
        ),
    }

    # 各Agent的"输出分析"角色Prompt —— 输出风格匹配各自角色
    ANALYSIS_PROMPTS = {
        "monitor": (
            "You are a hardware metrics analyst. Translate the raw command output into "
            "a structured resource report. Use tables and numbers. "
            "Highlight: whether each metric is healthy/warning/critical with thresholds, "
            "hardware temperature status, resource utilization trends, capacity planning notes. "
            "Focus ONLY on metrics — do NOT suggest fixes, do NOT diagnose problems, "
            "do NOT analyze logs. Pure metric analysis only. "
            "Output in Chinese with a clear table structure."
        ),
        "diagnostic": (
            "You are a senior server troubleshooter. Analyze the diagnostic output and "
            "identify the ROOT CAUSE of the reported problem. "
            "Rate confidence (low/medium/high) and severity. "
            "Provide: root cause hypothesis → evidence from the output → recommended fix direction. "
            "Distinguish between symptoms and causes. If the output is insufficient, "
            "specify what additional information is needed. "
            "Output in Chinese, structured and actionable."
        ),
        "remediation": (
            "You are a repair verification specialist. Analyze the command execution output. "
            "Report clearly: what was done → whether it succeeded → the new state. "
            "If a repair failed, explain why (from stderr/output) and suggest the next step. "
            "If successful, confirm the service/process is now healthy. "
            "Be concise and direct. Output in Chinese."
        ),
        "log_analyzer": (
            "You are a log forensics analyst. Examine the extracted log data for: "
            "anomalies, attack indicators (brute force, privilege escalation), "
            "service failures, recurring error patterns, and timeline reconstruction. "
            "Rank findings by: critical > warning > info. "
            "For each finding: timestamp → event → potential impact → suggested action. "
            "Output in Chinese, structured by severity level."
        ),
        "compliance_checker": (
            "You are a security compliance auditor. Produce a formal audit report from the check results. "
            "Format as a table: check item | status (PASS/FAIL) | risk level | finding | remediation. "
            "Calculate: compliance score = passed / total × 100%. "
            "Highlight critical failures (unrestricted root SSH, empty passwords, no firewall). "
            "For each FAIL item, provide the exact fix command. "
            "End with a prioritized action plan. Output in Chinese."
        ),
    }

    # ===== 对外入口 =====

    async def execute(
        self, agent_type: str, input_text: str,
        server_id: str = None, server_msg: str = None, timeout: int = 30
    ) -> dict:
        try:
            handler = getattr(self, f"_handle_{agent_type}", None)
            if handler:
                return await handler(input_text, server_id, server_msg, timeout)
            answer = await call_llm(input_text, temperature=0.7)
            return {"output": answer, "agent": agent_type}
        except Exception as e:
            logger.exception(f"Agent执行失败 [{agent_type}]")
            return {"status": "error", "output": f"Agent执行失败: {str(e)}", "agent": agent_type, "error": str(e)}

    async def remediate_alert(
        self, alert_id: str, server_id: str = None, triggered_by: str = "auto"
    ) -> dict:
        """
        基于告警的AI自动修复：
        1. 加载告警和服务器信息
        2. AI诊断 + 生成修复命令
        3. SSH执行
        4. AI分析结果
        5. 写入RemediationLog
        6. 返回结果
        """
        start_time = time_module.time()
        async with AsyncSessionLocal() as db:
            alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
            if not alert:
                return {"status": "failed", "output": f"告警 {alert_id} 不存在"}

            server = None
            if server_id:
                server = (await db.execute(select(Server).where(Server.id == server_id))).scalar_one_or_none()
            elif alert.server_id:
                server = (await db.execute(select(Server).where(Server.id == alert.server_id))).scalar_one_or_none()
            elif alert.instance:
                # 从 instance 字段解析 (格式 ip:port)
                instance = alert.instance
                if ":" in instance:
                    ip, port_str = instance.split(":", 1)
                    try:
                        port = int(port_str)
                        server = (await db.execute(
                            select(Server).where(Server.host == ip, Server.port == port)
                        )).scalar_one_or_none()
                    except ValueError:
                        pass

        if not server:
            return {
                "status": "failed",
                "output": f"无法定位告警关联的服务器。告警实例: {alert.instance}，请在服务器管理中配置该实例。",
            }

        cred_error = self._validate_server_credential(server)
        if cred_error:
            # 创建失败日志
            await self._write_remediation_log(
                alert_id=alert_id, server_id=server.id, action=f"AI修复: {alert.alert_name}",
                triggered_by=triggered_by, status="skipped",
                input_text=cred_error, error_output=cred_error,
            )
            return {"status": "failed", "output": cred_error}

        # 构建富含告警上下文的修复指令
        repair_prompt = self._build_alert_repair_prompt(alert, server)

        # 记录开始执行的日志
        log_id = await self._write_remediation_log(
            alert_id=alert_id, server_id=server.id,
            action=f"AI修复: {alert.alert_name}",
            triggered_by=triggered_by, status="running",
            input_text=repair_prompt,
        )

        # 执行AI修复管道
        result = await self._ai_execute_on_server("ai_remediation", repair_prompt, server, 60)

        # 更新日志
        duration_ms = int((time_module.time() - start_time) * 1000)
        await self._update_remediation_log(
            log_id,
            status=result.get("status", "failed"),
            command=result.get("commands", ""),
            output=result.get("raw_output", ""),
            error_output=result.get("output", "") if result.get("status") == "failed" else "",
            exit_code=result.get("exit_code"),
            duration_ms=duration_ms,
        )

        # 发送修复结果通知
        try:
            from .notification_service import send_notification
            status_cn = "成功" if result.get("status") == "success" else "失败"
            await send_notification(
                alert_name=f"修复{status_cn}: {alert.alert_name}",
                summary=f"AI修复「{alert.alert_name}」执行{status_cn}。服务器: {server.name}。{result.get('output', '')[:150]}",
                severity="info",
                instance=alert.instance,
            )
        except Exception:
            pass

        # 附加告警信息到返回结果
        result["alert_id"] = alert_id
        result["alert_name"] = alert.alert_name
        result["server_name"] = server.name
        result["log_id"] = log_id
        return result

    def _build_alert_repair_prompt(self, alert, server) -> str:
        """基于告警信息构建智能修复提示词"""
        severity_cn = {"critical": "严重", "warning": "警告", "info": "提示"}.get(alert.severity, "未知")
        return (
            f"【告警信息】\n"
            f"  告警名称: {alert.alert_name}\n"
            f"  严重级别: {severity_cn}\n"
            f"  告警实例: {alert.instance}\n"
            f"  告警摘要: {alert.summary}\n"
            f"  告警来源: {alert.source}\n\n"
            f"【目标服务器】\n"
            f"  名称: {server.name}\n"
            f"  地址: {server.host}:{server.port}\n\n"
            f"请根据以上告警信息，对目标服务器进行诊断并执行修复。"
            f"先快速验证告警是否准确，再确定根因，最后执行最安全的修复操作。"
        )

    async def _write_remediation_log(
        self, alert_id: str, server_id: str, action: str,
        triggered_by: str = "auto", status: str = "pending",
        input_text: str = "", command: str = "",
        output: str = "", error_output: str = "",
        exit_code: int = None, duration_ms: int = None,
    ) -> str:
        """写入修复日志，返回日志ID"""
        async with AsyncSessionLocal() as db:
            log = RemediationLog(
                alert_id=alert_id, server_id=server_id,
                action=action, triggered_by=triggered_by, status=status,
                input_text=input_text, command=command,
                output=output, error_output=error_output,
                exit_code=exit_code, duration_ms=duration_ms,
            )
            db.add(log)
            await db.commit()
            await db.refresh(log)
            return log.id

    async def _update_remediation_log(self, log_id: str, **kwargs):
        """更新修复日志字段"""
        async with AsyncSessionLocal() as db:
            log = await db.get(RemediationLog, log_id)
            if log:
                for field, value in kwargs.items():
                    if value is not None:
                        setattr(log, field, value)
                await db.commit()

    # ===== 核心管道：AI生成命令 → SSH执行 → AI分析 =====

    async def _ai_execute_on_server(
        self, agent_type: str, user_input: str, server, timeout: int
    ) -> dict:
        """
        统一的AI驱动运维管道:
        1. 根据agent角色, 让LLM生成Linux命令
        2. 安全检查
        3. SSH执行
        4. LLM分析原始输出
        5. 返回结构化结果
        """
        cmd_gen_prompt = self.CMD_GEN_PROMPTS.get(agent_type, self.CMD_GEN_PROMPTS["monitor"])
        analysis_prompt = self.ANALYSIS_PROMPTS.get(agent_type, self.ANALYSIS_PROMPTS["monitor"])

        # Step 1: LLM 生成命令
        gen_full_prompt = (
            f"{cmd_gen_prompt}\n\n"
            f"Server: {server.name} ({server.host})\n"
            f"User request: {user_input}\n\n"
            f"Output ONLY a ```bash code block. Be concise — no verbose comments, "
            f"just the commands. The block MUST be closed with ```. "
            f"Do NOT include explanations, markdown headers, or commentary."
        )
        llm_response = await call_llm(gen_full_prompt, temperature=0.2, max_tokens=4096)
        logger.info(f"[AI命令生成] agent={agent_type} response_len={len(llm_response)}")
        commands = self._extract_commands(llm_response)

        if not commands:
            logger.warning(f"[AI命令提取失败] agent={agent_type} prompt_len={len(gen_full_prompt)} response_len={len(llm_response)} first_200={llm_response[:200]!r}")
            return {
                "status": "failed",
                "output": f"AI未能生成有效的Shell命令。\nAI原始响应:\n{llm_response[:500]}",
                "agent": agent_type,
            }

        # Step 2: 安全检查
        blocked_reason = self._check_dangerous(commands)
        if blocked_reason:
            logger.warning(f"[安全拦截] agent={agent_type} blocked={blocked_reason}")
            return {
                "status": "blocked",
                "output": f"🛡️ 安全拦截: {blocked_reason}\n\nAI生成的命令:\n```bash\n{commands}\n```",
                "agent": agent_type,
                "commands": commands,
            }

        # Step 3: SSH 执行
        try:
            async with pool.get_connection(
                host=server.host, port=server.port,
                username=server.username,
                password=server.password if not server.use_ssh_key else None,
                private_key=server.private_key if server.use_ssh_key else None,
            ) as conn:
                result = await asyncio.wait_for(
                    conn.run(commands, check=False, timeout=timeout),
                    timeout=timeout + 5,
                )
                raw_output = result.stdout or ""
                stderr_output = result.stderr or ""
                exit_code = result.exit_status if hasattr(result, 'exit_status') else -1
        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "output": f"⏱ 命令执行超时({timeout}s)\n\n执行命令:\n```bash\n{commands}\n```",
                "agent": agent_type,
                "commands": commands,
            }
        except Exception as e:
            return {
                "status": "failed",
                "output": f"SSH执行失败: {str(e)}\n\n执行命令:\n```bash\n{commands}\n```",
                "agent": agent_type,
                "commands": commands,
            }

        # 截断过长的输出再送给LLM
        output_for_analysis = raw_output[:8000]
        if stderr_output:
            output_for_analysis += f"\n\n[stderr]\n{stderr_output[:2000]}"

        # Step 4: LLM 分析输出
        analysis_full_prompt = (
            f"User request: {user_input}\n\n"
            f"Commands executed:\n```bash\n{commands}\n```\n\n"
            f"Exit code: {exit_code}\n\n"
            f"Command output:\n{output_for_analysis}\n\n"
            f"{analysis_prompt}"
        )
        analysis = await call_llm(analysis_full_prompt, temperature=0.4, max_tokens=4096)

        return {
            "status": "success" if exit_code == 0 else "partial",
            "output": analysis,
            "agent": agent_type,
            "commands": commands,
            "exit_code": exit_code,
            "raw_output": raw_output[:2000],
        }

    def _extract_commands(self, llm_response: str) -> str:
        """从LLM响应中提取bash代码块"""
        # 匹配 ```bash / ```sh / ```shell (含闭合标签)
        match = re.search(r'```(?:ba)?sh(?:ell)?\s*\n(.*?)```', llm_response, re.DOTALL)
        if match:
            return match.group(1).strip()

        # 匹配无语言标记的代码块
        match = re.search(r'```\s*\n(.*?)```', llm_response, re.DOTALL)
        if match:
            content = match.group(1).strip()
            if any(kw in content for kw in ('echo', 'grep', 'awk', 'sed', 'curl', 'ps ', 'df ', 'free ', 'top ', 'systemctl', 'journalctl', 'ss ', 'cat ', 'ls ', 'find ', 'netstat')):
                return content
            return ""

        # 代码块未闭合（token截断）：提取 ```bash 之后的所有内容作为命令
        match = re.search(r'```(?:ba)?sh(?:ell)?\s*\n(.+)', llm_response, re.DOTALL)
        if match:
            content = match.group(1).strip()
            # 如果内容足够长（有多行命令），就直接使用
            if len(content) > 30 and '\n' in content:
                return content

        return ""

    def _check_dangerous(self, commands: str) -> str:
        """检查命令是否匹配危险模式, 返回危险原因或空字符串"""
        for pattern, description in DANGEROUS_PATTERNS:
            if re.search(pattern, commands, re.IGNORECASE):
                return description
        return ""

    # ===== SSH Agent Handlers (都走 AI 管道) =====

    async def _handle_monitor(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        server_result = await self._get_server(server_id, server_msg)
        if isinstance(server_result, dict):
            return server_result
        cred_error = self._validate_server_credential(server_result)
        if cred_error:
            return {"status": "failed", "output": cred_error, "agent": "monitor"}
        return await self._ai_execute_on_server("monitor", input_text or "采集全部系统指标", server_result, timeout)

    async def _handle_diagnostic(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        server_result = await self._get_server(server_id, server_msg)
        if isinstance(server_result, dict):
            return server_result
        cred_error = self._validate_server_credential(server_result)
        if cred_error:
            return {"status": "failed", "output": cred_error, "agent": "diagnostic"}
        return await self._ai_execute_on_server("diagnostic", input_text, server_result, timeout)

    async def _handle_remediation(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        server_result = await self._get_server(server_id, server_msg)
        if isinstance(server_result, dict):
            return server_result
        cred_error = self._validate_server_credential(server_result)
        if cred_error:
            return {"status": "failed", "output": cred_error, "agent": "remediation"}
        return await self._ai_execute_on_server("remediation", input_text, server_result, timeout)

    async def _handle_log_analyzer(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        server_result = await self._get_server(server_id, server_msg)
        if isinstance(server_result, dict):
            return server_result
        cred_error = self._validate_server_credential(server_result)
        if cred_error:
            return {"status": "failed", "output": cred_error, "agent": "log_analyzer"}
        return await self._ai_execute_on_server("log_analyzer", input_text, server_result, timeout)

    async def _handle_compliance_checker(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        server_result = await self._get_server(server_id, server_msg)
        if isinstance(server_result, dict):
            return server_result
        cred_error = self._validate_server_credential(server_result)
        if cred_error:
            return {"status": "failed", "output": cred_error, "agent": "compliance_checker"}
        return await self._ai_execute_on_server("compliance_checker", input_text or "执行全部安全合规检查", server_result, timeout)

    # ===== 纯LLM Agent Handlers (无需SSH) =====

    async def _handle_alert_analyzer(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        context_lines = []
        try:
            async with AsyncSessionLocal() as db:
                firing_alerts = (await db.execute(
                    select(Alert).where(Alert.status == "firing").order_by(Alert.created_at.desc()).limit(20)
                )).scalars().all()
                if firing_alerts:
                    context_lines.append("当前活跃告警：")
                    for a in firing_alerts:
                        context_lines.append(f"  [{a.severity}] {a.alert_name} @ {a.instance}: {a.summary[:100]}")
        except Exception:
            pass

        context = "\n".join(context_lines) if context_lines else "无活跃告警"
        system_prompt = (
            "You are an alert analysis expert. Evaluate the severity, urgency, and potential impact "
            "of the given alert. Suggest the appropriate response priority (P0-P4) and recommended actions."
        )
        answer = await call_llm(f"{context}\n\nAlert to analyze: {input_text}", system_prompt, temperature=0.4)
        return {"output": answer, "agent": "alert_analyzer"}

    async def _handle_change_executor(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        system_prompt = (
            "You are a change execution expert. Based on the request, generate a detailed change plan "
            "that includes: pre-change checks, step-by-step execution commands, "
            "verification steps, and a rollback plan. Format in Markdown."
        )
        plan = await call_llm(input_text, system_prompt, temperature=0.3)
        return {
            "output": plan,
            "agent": "change_executor",
            "requires_confirmation": True,
        }

    async def _handle_doc_generator(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        server_info = ""
        if server_id:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Server).where(Server.id == server_id))
                server = result.scalar_one_or_none()
                if server:
                    server_info = f"Server: {server.name} ({server.host}:{server.port})\n"

        system_prompt = (
            "You are a technical documentation expert. Generate clear, well-structured "
            "IT operations documentation based on the provided information. Format in Markdown."
        )
        full_prompt = f"{server_info}\n\nRequest: {input_text}"
        answer = await call_llm(full_prompt, system_prompt, temperature=0.6)
        return {"output": answer, "agent": "doc_generator"}

    async def _handle_generic(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        # 意图检测 → 自动路由到专用Agent
        detected = self._detect_intent(input_text)
        if detected != "generic" and hasattr(self, f"_handle_{detected}"):
            hint = (
                f"\n\n[系统提示] 您的问题更适合使用「{self.AGENT_DESCRIPTIONS.get(detected, detected)}」Agent处理。"
                f"已自动切换为 {detected} 模式。"
            )
            result = await self.execute(detected, input_text, server_id, server_msg, timeout)
            if isinstance(result, dict) and "output" in result:
                result["output"] = result.get("output", "") + hint
                result["agent"] = detected
                result["auto_routed_from"] = "generic"
            return result

        rag_context = await build_rag_context(input_text)
        system_prompt = (
            "You are an IT operations expert assistant. Provide practical, actionable guidance. "
            "When monitoring, diagnostics, or repairs are needed, respond with the exact shell "
            "commands the user should run, or ask them to select a server in the UI."
        )
        full_prompt = f"{rag_context}\n\nQuestion: {input_text}" if rag_context else input_text
        answer = await call_llm(full_prompt, system_prompt, temperature=0.7)
        return {"output": answer, "agent": "generic"}

    # ===== 辅助方法 =====

    async def _get_server(self, server_id: str = None, server_msg: str = None):
        """统一获取Server对象, 返回Server或错误dict"""
        if server_id:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Server).where(Server.id == server_id))
                server = result.scalar_one_or_none()
                if not server:
                    return {"status": "failed", "output": f"服务器 {server_id} 不存在"}
                return server

        if server_msg:
            parts = server_msg.split(":")
            if len(parts) != 2:
                return {"status": "failed", "output": f"instance格式不正确: {server_msg}"}
            ip, port_str = parts
            try:
                port = int(port_str)
            except ValueError:
                return {"status": "failed", "output": f"端口号不是整数: {port_str}"}
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Server).where(Server.host == ip, Server.port == port))
                server = result.scalar_one_or_none()
                if not server:
                    return {"status": "failed", "output": f"服务器 {ip}:{port} 不存在"}
                return server

        return {"status": "failed", "output": "缺少服务器标识，请从服务器下拉列表中选择目标服务器"}

    def _validate_server_credential(self, server: Server) -> str | None:
        """验证服务器是否有可用的SSH凭据"""
        if not server.password and not server.use_ssh_key:
            return (
                f"服务器「{server.name}」({server.host}:{server.port}) 未配置认证凭据。"
                f"请在服务器管理中为该服务器添加密码或 SSH 密钥。"
            )
        if server.use_ssh_key and not server.private_key:
            return (
                f"服务器「{server.name}」({server.host}:{server.port}) 已启用 SSH 密钥认证但未配置密钥内容。"
                f"请在服务器管理中上传 SSH 私钥。"
            )
        return None

    # ===== 意图检测（通用Agent自动路由） =====

    INTENT_KEYWORDS = {
        "monitor": ["采集", "指标", "CPU", "内存", "磁盘", "使用率", "监控", "monitor",
                     "cpu usage", "memory usage", "disk usage", "collect metric"],
        "diagnostic": ["故障", "诊断", "排查", "报错", "异常", "崩溃", "不响应", "卡",
                       "diagnose", "debug", "troubleshoot", "error", "crash", "slow"],
        "remediation": ["修复", "重启", "恢复", "执行命令", "restart", "recover",
                        "repair", "fix", "remediate"],
        "alert_analyzer": ["告警", "报警", "alert", "alarm", "通知"],
        "log_analyzer": ["日志", "log", "journal"],
        "compliance_checker": ["合规", "安全", "检查", "compliance", "security check"],
        "doc_generator": ["文档", "报告", "生成", "document", "report"],
    }

    def _detect_intent(self, input_text: str) -> str:
        """基于关键词匹配检测最合适的Agent类型"""
        text_lower = input_text.lower()
        best_match = "generic"
        best_score = 0
        for agent_type, keywords in self.INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > best_score:
                best_score = score
                best_match = agent_type
        return best_match


async def trigger_auto_remediation(alert_id: str, alert_labels: dict, server_id: str = None, triggered_by: str = "auto"):
    """根据告警标签匹配修复策略，自动触发AI修复（供 alerts.py / schedulers.py 调用）"""
    import json as _json
    try:
        async with AsyncSessionLocal() as db:
            policies = (await db.execute(
                select(RemediationPolicy).where(RemediationPolicy.enabled == True)
            )).scalars().all()

        matched = []
        for p in policies:
            try:
                labels = _json.loads(p.match_labels) if p.match_labels else {}
            except (_json.JSONDecodeError, TypeError):
                continue
            if not labels:
                continue
            if all(alert_labels.get(k) == v for k, v in labels.items()):
                matched.append(p)

        if not matched:
            return

        executor = AgentExecutor()
        for policy in matched:
            if policy.repair_mode == "ai" and not policy.requires_approval:
                logger.info(f"[自动修复] alert={alert_id} policy={policy.name}")
                await executor.remediate_alert(
                    alert_id=alert_id, server_id=server_id, triggered_by=triggered_by
                )
            elif policy.repair_mode == "ai" and policy.requires_approval:
                async with AsyncSessionLocal() as db2:
                    log_entry = RemediationLog(
                        alert_id=alert_id, server_id=server_id,
                        action=f"待审批: {policy.name}",
                        triggered_by=triggered_by, status="pending",
                        input_text=f"策略「{policy.name}」匹配，等待管理员审批后执行AI修复",
                    )
                    db2.add(log_entry)
                    await db2.commit()
    except Exception:
        pass

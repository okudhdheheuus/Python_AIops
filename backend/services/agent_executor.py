import asyncio
import logging
import re
import time as time_module

from sqlalchemy import select

from ..database import AsyncSessionLocal
from ..models import Alert, RemediationLog, Server
from .knowledge_service import build_rag_context
from .llm_service import call_llm
from .ssh_pool import pool

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

    def __init__(self, user_llm_config=None):
        self.user_llm_config = user_llm_config

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

    # 各Agent的"命令生成"角色Prompt —— 强分化，每个Agent的命令完全不重叠
    CMD_GEN_PROMPTS = {
        "monitor": (
            "You are a METRICS COLLECTION machine — you ONLY output numbers, nothing else.\n"
            "Generate commands to capture these 6 metrics exactly (one command per metric):\n"
            "1. CPU usage %: top -bn1 | awk '/Cpu\\(s\\)/{print $2+$4}'\n"
            "2. Memory usage %: free | awk '/Mem:/{printf \"%.1f\", $3/$2*100}'\n"
            "3. Disk usage % for /: df / | awk 'NR==2{print $5}' | tr -d '%'\n"
            "4. Load average (1min): uptime | awk -F'load average:' '{print $2}' | awk '{print $1}'\n"
            "5. Top CPU process: ps aux --sort=-%cpu | head -2 | tail -1 | awk '{print $11,$3\"%\"}'\n"
            "6. Connection states: ss -s | head -1\n"
            "Use ONLY: top, free, df, uptime, ps, ss. NO sensors, iostat, sar, vmstat.\n"
            "Each command on its own line. NO comments, NO echo, NO explanations.\n"
            "Your output will be parsed by a machine — keep it clean."
        ),
        "diagnostic": (
            "You are a ROOT CAUSE INVESTIGATOR — you hunt down WHY something is broken.\n"
            "You do NOT collect metrics (monitor does that). You do NOT fix (remediation does that).\n"
            "Read the user's symptom description. Pick ONE investigation strategy:\n"
            "  SLOW RESPONSE: top -bn1 -o %CPU | head -5 → iostat -x 1 2 → ss -s → free -h\n"
            "  CRASH/OOM: dmesg | tail -30 → journalctl -p err -n 50 --no-pager → grep -i oom /var/log/messages | tail -10\n"
            "  SERVICE DOWN: systemctl status <service> → journalctl -u <service> -n 30 --no-pager → ls -la /etc/systemd/system/<service>*\n"
            "  HIGH LOAD: uptime → ps aux --sort=-%cpu | head -6 → vmstat 1 3 → ss -tlnp\n"
            "  UNKNOWN: uptime && echo '---' && free -h && echo '---' && df -h / && echo '---' && dmesg | tail -15\n"
            "Structure your commands as: 1 quick symptom check → 1 drill-down → 1 confirmation.\n"
            "MAX 4 commands. Read-only. Each command MUST directly relate to the described symptom."
        ),
        "remediation": (
            "You are a REPAIR OPERATOR — you are the ONLY agent authorized to change things.\n"
            "You will receive diagnostic findings. Your job: generate a SAFE fix.\n"
            "EVERY response MUST follow this exact 3-command structure:\n"
            "  1. PRE-CHECK: verify the problem still exists (e.g., ps aux | grep <process>, systemctl is-active <svc>)\n"
            "  2. REPAIR: the actual fix (systemctl restart <svc>, kill <pid> only if restart fails, du -sh /var/log to suggest cleanup)\n"
            "  3. VERIFY: confirm the fix worked (systemctl is-active <svc>, ps aux | grep <process>)\n"
            "RULES: Never kill -9 as first resort. Never rm -rf. Never reboot. Never iptables -F.\n"
            "If the repair could be dangerous, output: echo 'BLOCKED:' followed by the reason.\n"
            "For EVERY repair command, add a comment starting with # ROLLBACK: explaining how to undo."
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
            "You are a LOG EXTRACTION SPECIALIST — you ONLY pull log entries, nothing else.\n"
            "You are FORBIDDEN from: checking metrics, diagnosing problems, suggesting fixes.\n"
            "Based on the user's input, pick the right log source:\n"
            "  If user mentions a SERVICE: journalctl -u <service> -n 100 --no-pager\n"
            "  If user mentions ERRORS: journalctl -p err -n 100 --no-pager\n"
            "  If user mentions a TIME: journalctl --since '2 hours ago' -n 100 --no-pager\n"
            "  If user mentions SECURITY: grep -E 'Failed|Invalid|refused' /var/log/secure | tail -50\n"
            "  If user mentions APP CRASH: dmesg | tail -50 && journalctl -p err -n 50 --no-pager\n"
            "  DEFAULT (no hints): journalctl -p warning -n 80 --no-pager\n"
            "MAX 2 log commands. Always limit to 100 lines max per command (-n 100).\n"
            "Use --no-pager to avoid interactive mode. NO grep on journalctl output (use journalctl filters)."
        ),
        "compliance_checker": (
            "You are a SECURITY AUDITOR — you produce a formal compliance checklist.\n"
            "Generate EXACTLY these 8 read-only check commands, one per security item:\n"
            "1. SSH_ROOT: grep '^PermitRootLogin' /etc/ssh/sshd_config\n"
            "2. SSH_PASS: grep '^PasswordAuthentication' /etc/ssh/sshd_config\n"
            "3. FIREWALL: systemctl is-active firewalld 2>/dev/null || ufw status 2>/dev/null || echo 'none'\n"
            "4. SELINUX: getenforce 2>/dev/null || echo 'not installed'\n"
            "5. EMPTY_PW: awk -F: '($2==\"\"){print $1}' /etc/shadow | wc -l\n"
            "6. PASS_POLICY: grep -E '^PASS_MAX_DAYS|^PASS_MIN_LEN' /etc/login.defs 2>/dev/null || echo 'no policy found'\n"
            "7. WORLD_WRITABLE: find /etc /var -perm -0002 -type f 2>/dev/null | wc -l\n"
            "8. LISTENING: ss -tlnp 2>/dev/null | awk 'NR>1{print $4}' | awk -F: '{print $NF}' | sort -n | uniq\n"
            "NO other commands. Each check outputs exactly one value. NO analysis within the commands.\n"
            "The output of each command will be scored PASS/FAIL by the analysis step."
        ),
    }

    # 各Agent的"输出分析"角色Prompt —— 输出格式完全不同，一眼就能看出是哪个 Agent 的产物
    ANALYSIS_PROMPTS = {
        "monitor": (
            "You are a METRICS REPORT formatter. You MUST output ONLY this table format, no other text:\n"
            "| 指标 | 当前值 | 阈值 | 状态 |\n"
            "| CPU | xx% | 80% | 正常/警告/危险 |\n"
            "| 内存 | xx% | 80% | 正常/警告/危险 |\n"
            "| 磁盘 | xx% | 85% | 正常/警告/危险 |\n"
            "| 负载 | x.xx | 核心数 | 正常/偏高 |\n"
            "| 进程 | xxx个 | - | - |\n"
            "| 连接 | xxx | - | - |\n"
            "End with one line: 综合评估: [健康/需关注/异常], 原因: xxx\n"
            "No analysis, no recommendations, no diagnosis. JUST the table."
        ),
        "diagnostic": (
            "You are a ROOT CAUSE ANALYZER. Output MUST follow this structure:\n"
            "## 故障现象\n[1 句话复述用户报告的故障]\n"
            "## 根因假设\n[最可能的根因] (置信度: 高/中/低)\n"
            "## 证据链\n1. [来自命令输出的具体证据 1]\n2. [来自命令输出的具体证据 2]\n"
            "## 排除项\n- [已排除的可能性及原因]\n"
            "## 建议方向\n[下一步应该由 remediation Agent 执行的修复操作]\n"
            "If evidence is insufficient, say 证据不足 and list what additional info is needed."
        ),
        "remediation": (
            "You are a REPAIR VERIFICATION reporter. Output MUST be:\n"
            "## 修复报告\n"
            "| 步骤 | 操作 | 结果 |\n"
            "| 预检 | [命令] | 成功/失败 |\n"
            "| 修复 | [修复操作描述] | 成功/失败 |\n"
            "| 验证 | [验证操作描述] | 成功/失败 |\n"
            "## 当前状态\n[服务/进程当前状态]\n"
            "## 回滚方案\n[如果修复失败，如何回滚]\n"
            "Be concise — no more than 8 lines total."
        ),
        "log_analyzer": (
            "You are a LOG FORENSICS ANALYST. Output MUST be:\n"
            "## 日志分析结果\n"
            "| 时间 | 级别 | 来源 | 摘要 |\n"
            "| --:-- | 严重/警告/信息 | [进程/服务] | [20字内摘要] |\n"
            "(list up to 10 most important entries, ranked by severity)\n"
            "## 异常模式\n[是否有暴力破解、异常登录、循环报错等模式，没有则写 无异常模式]\n"
            "## 建议\n[1-2 条后续行动建议]\n"
            "Do NOT diagnose root cause. Do NOT suggest fixes. ONLY log forensics."
        ),
        "compliance_checker": (
            "You are a COMPLIANCE AUDITOR. Output MUST be a formal audit table:\n"
            "## 安全合规审计报告\n"
            "| 检查项 | 结果 | 风险 | 说明 |\n"
            "| SSH Root登录 | 通过/不通过 | 高/中/低 | [简要说明] |\n"
            "| SSH 密码认证 | 通过/不通过 | 高/中/低 | [简要说明] |\n"
            "| 防火墙 | 通过/不通过 | 高/中/低 | [简要说明] |\n"
            "| SELinux | 通过/不通过 | 中 | [简要说明] |\n"
            "| 空密码账户 | 通过/不通过 | 高/中/低 | [简要说明] |\n"
            "| 密码策略 | 通过/不通过 | 中 | [简要说明] |\n"
            "| 全局可写文件 | 通过/不通过 | 中 | [简要说明] |\n"
            "| 监听端口 | 通过/不通过 | 中 | [简要说明] |\n"
            "## 合规评分: X/8 (XX%)\n"
            "## 优先修复项 (按风险排序)\n"
            "1. [最紧急的修复项 + 具体命令]\n"
            "2. [次紧急的]\n"
            "End with: 审计完成 — 以上结果均来自服务器实际配置检查，非评估猜测。"
        ),
    }

    # ===== 对外入口 =====

    async def execute(
        self, agent_type: str, input_text: str,
        server_id: str | None = None, server_msg: str | None = None, timeout: int = 30
    ) -> dict:
        try:
            handler = getattr(self, f"_handle_{agent_type}", None)
            if handler:
                return await handler(input_text, server_id, server_msg, timeout)
            answer = await call_llm(input_text, temperature=0.7, user_llm_config=self.user_llm_config)
            return {"output": answer, "agent": agent_type}
        except Exception as e:
            logger.exception(f"Agent执行失败 [{agent_type}]")
            return {"status": "error", "output": f"Agent执行失败: {e!s}", "agent": agent_type, "error": str(e)}

    async def remediate_alert(
        self, alert_id: str, server_id: str | None = None, triggered_by: str = "auto"
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
        exit_code: int | None = None, duration_ms: int | None = None,
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
        llm_response = await call_llm(gen_full_prompt, temperature=0.2, max_tokens=4096, user_llm_config=self.user_llm_config)
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
                "output": f"SSH执行失败: {e!s}\n\n执行命令:\n```bash\n{commands}\n```",
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
        analysis = await call_llm(analysis_full_prompt, temperature=0.4, max_tokens=4096, user_llm_config=self.user_llm_config)

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

        result: dict = {"agent": "monitor", "status": "failed"}
        metrics_collected = False

        # 先采集结构化指标（直接从 /proc/stat、free、df 提取数值）
        try:
            metrics_cmd = (
                "cpu=$(grep '^cpu ' /proc/stat | awk "
                "'{idle=$5; total=$2+$3+$4+$5+$6+$7+$8; printf \"%.1f\", (total-idle)*100/total}');"
                "echo \"CPU:${cpu:-0}\";"
                "mem=$(free | awk '/Mem:/{printf \"%.1f\", $3/$2*100}');"
                "echo \"MEM:${mem:-0}\";"
                "disk=$(df / | awk 'NR==2{gsub(/%/,\"\"); print $5}');"
                "echo \"DISK:${disk:-0}\""
            )
            async with pool.get_connection(
                host=server_result.host, port=server_result.port,
                username=server_result.username,
                password=server_result.password if not server_result.use_ssh_key else None,
                private_key=server_result.private_key if server_result.use_ssh_key else None,
            ) as conn:
                metrics_output = await asyncio.wait_for(
                    conn.run(metrics_cmd, check=False, timeout=15),
                    timeout=20,
                )
                for line in (metrics_output.stdout or "").strip().split("\n"):
                    line = line.strip()
                    if line.startswith("CPU:"):
                        try:
                            result["cpu"] = float(line.split(":", 1)[1])
                        except ValueError:
                            pass
                    elif line.startswith("MEM:"):
                        try:
                            result["memory"] = float(line.split(":", 1)[1])
                        except ValueError:
                            pass
                    elif line.startswith("DISK:"):
                        try:
                            result["disk"] = float(line.split(":", 1)[1])
                        except ValueError:
                            pass
                metrics_collected = True
        except asyncio.TimeoutError:
            result["ssh_error"] = f"SSH 连接超时 ({server_result.host}:{server_result.port})"
        except Exception as e:
            result["ssh_error"] = f"SSH 连接失败 ({server_result.host}:{server_result.port}): {e!s}"

        # 再运行 AI 管道生成分析报告
        try:
            ai_result = await self._ai_execute_on_server(
                "monitor", input_text or "采集全部系统指标", server_result, timeout
            )
            result.update(ai_result)
        except Exception:
            if not metrics_collected:
                ssh_err = result.get("ssh_error", "")
                result["output"] = (
                    f"指标采集失败。\n\n"
                    f"目标: {server_result.host}:{server_result.port}\n"
                    f"{'SSH: ' + ssh_err if ssh_err else '未配置 LLM API Key，无法生成分析报告'}\n\n"
                    f"请检查:\n"
                    f"1. 服务器管理中是否配置了 SSH 密码或密钥\n"
                    f"2. 用户设置中是否配置了 LLM API Key\n"
                    f"3. 服务器端口 {server_result.port} 是否可达"
                )
            else:
                result["status"] = "partial"
                result["output"] = "结构化指标采集成功，但 AI 分析失败（LLM API Key 未配置或调用出错）"

        return result

    async def _handle_diagnostic(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        server_result = await self._get_server(server_id, server_msg)
        if isinstance(server_result, dict):
            return server_result
        cred_error = self._validate_server_credential(server_result)
        if cred_error:
            return {"status": "failed", "output": cred_error, "agent": "diagnostic"}

        result: dict = {"agent": "diagnostic"}

        # 先采集快速诊断数据（不依赖 LLM）
        try:
            quick_diag_cmd = (
                "echo '=== UPTIME ===' && uptime && "
                "echo '=== LOAD ===' && cat /proc/loadavg && "
                "echo '=== MEMORY ===' && free -h && "
                "echo '=== DISK ===' && df -h / && "
                "echo '=== TOP_CPU ===' && ps aux --sort=-%cpu | head -4 && "
                "echo '=== DMESG_TAIL ===' && dmesg --level=err,warn | tail -10"
            )
            async with pool.get_connection(
                host=server_result.host, port=server_result.port,
                username=server_result.username,
                password=server_result.password if not server_result.use_ssh_key else None,
                private_key=server_result.private_key if server_result.use_ssh_key else None,
            ) as conn:
                raw_output = await asyncio.wait_for(
                    conn.run(quick_diag_cmd, check=False, timeout=15),
                    timeout=20,
                )
                result["quick_diag"] = (raw_output.stdout or "")[:5000]
        except Exception:
            pass

        # 再走 AI 管道做深度分析
        try:
            ai_result = await self._ai_execute_on_server(
                "diagnostic", input_text or "诊断当前服务器状态", server_result, timeout
            )
            result.update(ai_result)
        except Exception:
            if "status" not in result:
                result["status"] = "partial"
                result["output"] = (
                    f"AI 分析失败，以下为快速诊断数据：\n\n```\n{result.get('quick_diag', '采集失败')}\n```"
                )

        return result

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
        answer = await call_llm(f"{context}\n\nAlert to analyze: {input_text}", system_prompt, temperature=0.4, user_llm_config=self.user_llm_config)
        return {"output": answer, "agent": "alert_analyzer"}

    async def _handle_change_executor(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        system_prompt = (
            "You are a change execution expert. Based on the request, generate a detailed change plan "
            "that includes: pre-change checks, step-by-step execution commands, "
            "verification steps, and a rollback plan. "
            "At the end of your response, on a separate line starting with '## EXEC_COMMANDS', "
            "output ONLY the executable bash commands (one per line, no markdown) that are safe to run automatically."
        )
        plan = await call_llm(input_text, system_prompt, temperature=0.3, user_llm_config=self.user_llm_config)

        # 尝试提取可执行命令并在服务器上运行
        exec_section = plan.split("## EXEC_COMMANDS")[-1] if "EXEC_COMMANDS" in plan else ""
        commands = exec_section.strip() if exec_section else ""

        result: dict = {
            "output": plan,
            "agent": "change_executor",
        }

        if commands and server_id:
            server_result = await self._get_server(server_id, server_msg)
            if not isinstance(server_result, dict):
                cred_error = self._validate_server_credential(server_result)
                if not cred_error:
                    blocked_reason = self._check_dangerous(commands)
                    if blocked_reason:
                        result["exec_status"] = "blocked"
                        result["exec_reason"] = blocked_reason
                    else:
                        try:
                            async with pool.get_connection(
                                host=server_result.host, port=server_result.port,
                                username=server_result.username,
                                password=server_result.password if not server_result.use_ssh_key else None,
                                private_key=server_result.private_key if server_result.use_ssh_key else None,
                            ) as conn:
                                exec_result = await asyncio.wait_for(
                                    conn.run(commands, check=False, timeout=timeout),
                                    timeout=timeout + 5,
                                )
                                result["exec_status"] = "success" if (hasattr(exec_result, 'exit_status') and exec_result.exit_status == 0) else "partial"
                                result["exec_output"] = (exec_result.stdout or "")[:3000]
                                result["exec_stderr"] = (exec_result.stderr or "")[:1000]
                                result["commands"] = commands
                        except asyncio.TimeoutError:
                            result["exec_status"] = "timeout"
                        except Exception as e:
                            result["exec_status"] = "failed"
                            result["exec_reason"] = str(e)
                else:
                    result["exec_status"] = "skipped"
                    result["exec_reason"] = "服务器凭据未配置"

        return result

    async def _handle_doc_generator(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        server_info = ""
        server_result = None
        if server_id:
            async with AsyncSessionLocal() as db:
                result = await db.execute(select(Server).where(Server.id == server_id))
                server = result.scalar_one_or_none()
                if server:
                    server_info = f"Server: {server.name} ({server.host}:{server.port})\n"
                    server_result = server

        system_prompt = (
            "You are an IT operations documentation expert. Based on the provided data "
            "(server metrics, log analysis, monitoring results), generate a PROFESSIONAL "
            "operations report in Markdown. Follow this structure:\n"
            "## 1. 概述\nBrief summary of the system state in 2-3 sentences.\n"
            "## 2. 关键指标\n| 指标 | 当前值 | 阈值 | 状态 |\n"
            "Fill in actual numbers from the provided data — do NOT use placeholders.\n"
            "## 3. 异常与风险\nList any anomalies, warnings, or risks found.\n"
            "## 4. 建议措施\nSpecific, actionable recommendations (commands if applicable).\n\n"
            "CRITICAL: Use the actual data provided. If data is present, generate the report "
            "from it. NEVER output a template with placeholders like 'xx%' or '参考值'."
        )
        full_prompt = f"## 服务器信息\n{server_info}\n\n## 上游数据\n{input_text}\n\n请基于以上数据生成完整的运维巡检报告。"
        answer = await call_llm(full_prompt, system_prompt, temperature=0.5, user_llm_config=self.user_llm_config)

        result: dict = {
            "output": answer,
            "agent": "doc_generator",
        }

        # 如果有服务器，将文档保存为实际文件
        if server_result and hasattr(server_result, 'host'):
            cred_error = self._validate_server_credential(server_result)
            if not cred_error:
                ts = int(time_module.time())
                filename = f"/tmp/ops_report_{ts}.md"
                # 用 base64 安全写入含特殊字符的 Markdown
                import base64
                encoded = base64.b64encode(answer.encode("utf-8")).decode("ascii")
                write_cmd = f"echo '{encoded}' | base64 -d > {filename} && echo 'OK:{filename}'"
                try:
                    async with pool.get_connection(
                        host=server_result.host, port=server_result.port,
                        username=server_result.username,
                        password=server_result.password if not server_result.use_ssh_key else None,
                        private_key=server_result.private_key if server_result.use_ssh_key else None,
                    ) as conn:
                        save_result = await asyncio.wait_for(
                            conn.run(write_cmd, check=False, timeout=15),
                            timeout=20,
                        )
                        stdout = (save_result.stdout or "").strip()
                        if stdout.startswith("OK:"):
                            saved_path = stdout.split("OK:", 1)[1]
                            result["saved_file"] = saved_path
                            result["output"] = answer + f"\n\n---\n\n\x1b[32m文档已保存到服务器: {saved_path}\x1b[0m"
                        else:
                            result["save_error"] = stdout[:200]
                except Exception as e:
                    result["save_error"] = str(e)

        return result

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
        answer = await call_llm(full_prompt, system_prompt, temperature=0.7, user_llm_config=self.user_llm_config)
        return {"output": answer, "agent": "generic"}

    # ===== 实用操作节点（不依赖 LLM） =====

    async def _handle_shell_command(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        """直接执行 Shell 命令，跳过 LLM 生成步骤。prompt 字段 = 要执行的命令"""
        server_result = await self._get_server(server_id, server_msg)
        if isinstance(server_result, dict):
            return server_result
        cred_error = self._validate_server_credential(server_result)
        if cred_error:
            return {"status": "failed", "output": cred_error, "agent": "shell_command"}

        commands = (input_text or "").strip()
        if not commands:
            return {"status": "failed", "output": "未提供要执行的命令", "agent": "shell_command"}

        blocked_reason = self._check_dangerous(commands)
        if blocked_reason:
            return {"status": "blocked", "output": f"命令被安全策略拦截: {blocked_reason}",
                    "agent": "shell_command", "commands": commands}

        start = time_module.perf_counter()
        try:
            async with pool.get_connection(
                host=server_result.host, port=server_result.port,
                username=server_result.username,
                password=server_result.password if not server_result.use_ssh_key else None,
                private_key=server_result.private_key if server_result.use_ssh_key else None,
            ) as conn:
                result = await asyncio.wait_for(
                    conn.run(commands, check=False, timeout=timeout),
                    timeout=timeout + 5,
                )
                duration_ms = int((time_module.perf_counter() - start) * 1000)
                exit_code = result.exit_status if hasattr(result, "exit_status") else -1
                output = (result.stdout or "")[:4000]
                stderr = (result.stderr or "")[:1000]
                return {
                    "status": "success" if exit_code == 0 else "partial",
                    "output": output or stderr or f"(exit code {exit_code})",
                    "agent": "shell_command",
                    "commands": commands,
                    "exit_code": exit_code,
                    "duration_ms": duration_ms,
                    "stderr": stderr if exit_code != 0 else "",
                }
        except asyncio.TimeoutError:
            return {"status": "timeout", "output": f"命令超时({timeout}s)", "agent": "shell_command", "commands": commands}
        except Exception as e:
            return {"status": "failed", "output": f"SSH 执行失败: {e}", "agent": "shell_command", "commands": commands}

    async def _handle_health_check(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        """HTTP GET 健康检查，不依赖 SSH 和 LLM。prompt 字段 = URL"""
        import urllib.request

        url = (input_text or "").strip()
        if url.upper().startswith("GET "):
            url = url[4:].strip()
        if not url.startswith(("http://", "https://")):
            return {"status": "failed", "output": f"无效的 URL (需要 http/https): {url[:100]}", "agent": "health_check"}

        start = time_module.perf_counter()
        try:
            req = urllib.request.Request(url, method="GET")
            resp = await asyncio.to_thread(urllib.request.urlopen, req, None, min(timeout, 15))
            duration_ms = int((time_module.perf_counter() - start) * 1000)
            body = resp.read().decode("utf-8", errors="replace")[:400]
            ok = 200 <= resp.status < 400
            return {
                "status": "success" if ok else "partial",
                "output": f"HTTP {resp.status} {resp.reason} ({duration_ms}ms)\n{body}",
                "agent": "health_check",
                "status_code": resp.status,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time_module.perf_counter() - start) * 1000)
            return {"status": "failed", "output": f"健康检查失败: {e}", "agent": "health_check", "duration_ms": duration_ms}

    async def _handle_webhook(self, input_text: str, server_id: str, server_msg: str, timeout: int) -> dict:
        """POST 通知到 Webhook URL，用于告警/结果推送。prompt 字段 = URL"""
        import json as _json
        import urllib.request

        url = (input_text or "").strip()
        if not url.startswith(("http://", "https://")):
            return {"status": "failed", "output": f"无效的 Webhook URL: {url[:100]}", "agent": "webhook"}

        payload = _json.dumps({
            "source": "ITOps Workflow",
            "timestamp": time_module.strftime("%Y-%m-%d %H:%M:%S"),
            "message": input_text[:2000],
        }).encode("utf-8")

        start = time_module.perf_counter()
        try:
            req = urllib.request.Request(url, data=payload, method="POST")
            req.add_header("Content-Type", "application/json")
            resp = await asyncio.to_thread(urllib.request.urlopen, req, None, min(timeout, 10))
            duration_ms = int((time_module.perf_counter() - start) * 1000)
            return {
                "status": "success" if resp.status < 400 else "partial",
                "output": f"Webhook HTTP {resp.status} ({duration_ms}ms)",
                "agent": "webhook",
                "http_status": resp.status,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            duration_ms = int((time_module.perf_counter() - start) * 1000)
            return {"status": "failed", "output": f"Webhook 发送失败: {e}", "agent": "webhook", "duration_ms": duration_ms}

    # ===== 辅助方法 =====

    async def _get_server(self, server_id: str | None = None, server_msg: str | None = None):
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


async def trigger_auto_remediation(alert_id: str, alert_labels: dict, server_id: str | None = None, triggered_by: str = "auto"):
    """告警触发后直接走 AI 修复——LLM 分析告警内容，生成修复命令，SSH 执行，写入日志"""
    try:
        logger.info(f"[自动修复] alert={alert_id} severity={alert_labels.get('severity')} server={server_id}")
        executor = AgentExecutor()
        await executor.remediate_alert(
            alert_id=alert_id, server_id=server_id, triggered_by=triggered_by
        )
    except Exception:
        logger.exception(f"[自动修复] 执行失败 alert={alert_id}")

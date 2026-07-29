import asyncio
import logging
import time

from .agent_executor import AgentExecutor

logger = logging.getLogger("workflow")


class NodeResult:
    """单个节点的执行结果"""
    def __init__(self, node_id: str, status: str, output: str, duration_ms: int, retries: int = 0, error: str | None = None):
        self.node_id = node_id
        self.status = status  # pending/running/success/failed/timeout/skipped
        self.output = output
        self.duration_ms = duration_ms
        self.retries = retries
        self.error = error


class WorkflowEngine:
    """增强工作流引擎 —— 支持并行、条件分支、超时、重试"""

    def __init__(self, agent_executor: AgentExecutor):
        self.agent_executor = agent_executor

    async def run_workflow(
        self,
        workflow_def: dict,
        initial_input: str = "",
        node_timeout: int = 60,
        max_retries: int = 2,
    ) -> dict:
        nodes = workflow_def.get("nodes", [])
        edges = workflow_def.get("edges", [])

        if not nodes:
            return {"status": "skipped", "results": {}, "reason": "no nodes"}

        node_map = {n["id"]: n for n in nodes}
        execution_order = self._topological_sort(nodes, edges)

        results: dict[str, NodeResult] = {}
        node_inputs: dict[str, str] = {}

        for level in execution_order:
            if len(level) == 1:
                # 串行执行
                node_id = level[0]
                node = node_map[node_id]
                prev_input = self._resolve_input(node_id, edges, results, initial_input)
                result = await self._execute_node(
                    node, prev_input, node_timeout, max_retries
                )
                results[node_id] = result
                node_inputs[node_id] = prev_input
            else:
                # 并行执行同层级节点
                tasks = []
                for node_id in level:
                    node = node_map[node_id]
                    prev_input = self._resolve_input(node_id, edges, results, initial_input)
                    node_inputs[node_id] = prev_input
                    tasks.append(self._execute_node(node, prev_input, node_timeout, max_retries))
                parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
                for node_id, result in zip(level, parallel_results):
                    if isinstance(result, Exception):
                        results[node_id] = NodeResult(
                            node_id, "failed", str(result), 0, retries=max_retries, error=str(result)
                        )
                    else:
                        results[node_id] = result

        # 汇总状态
        overall_status = "completed"
        if any(r.status == "failed" for r in results.values()):
            overall_status = "partial_failure" if any(r.status == "success" for r in results.values()) else "failed"

        return {
            "status": overall_status,
            "results": {nid: {"status": r.status, "output": r.output, "duration_ms": r.duration_ms, "retries": r.retries, "error": r.error} for nid, r in results.items()},
            "node_count": len(nodes),
            "completed_count": sum(1 for r in results.values() if r.status == "success"),
            "failed_count": sum(1 for r in results.values() if r.status == "failed"),
        }

    async def _execute_node(
        self, node: dict, input_text: str, timeout: int, max_retries: int
    ) -> NodeResult:
        """执行单个节点，支持超时和重试"""
        node_id = node.get("id", "unknown")
        config = node.get("config", {})
        agent_type = node.get("agent_type") or config.get("agent_type", "generic")
        prompt = node.get("prompt") or config.get("prompt", input_text)
        server_id = node.get("server_id") or config.get("server_id")
        node_timeout = node.get("timeout") or config.get("timeout", timeout)
        node_max_retries = node.get("max_retries") or config.get("max_retries", max_retries)

        # 条件分支检查
        condition = node.get("condition")
        if condition and not self._evaluate_condition(condition, input_text):
            return NodeResult(node_id, "skipped", "条件不满足，跳过执行", 0)

        last_error = None
        for attempt in range(node_max_retries + 1):
            start = time.perf_counter()
            try:
                result = await asyncio.wait_for(
                    self.agent_executor.execute(
                        agent_type=agent_type,
                        input_text=prompt,
                        server_id=server_id,
                        timeout=node_timeout,
                    ),
                    timeout=node_timeout + 5,
                )
                duration_ms = int((time.perf_counter() - start) * 1000)
                status = result.get("status", "success") if isinstance(result, dict) else "success"
                output = result.get("output", str(result)) if isinstance(result, dict) else str(result)
                return NodeResult(node_id, status, output, duration_ms, retries=attempt)
            except asyncio.TimeoutError:
                last_error = f"超时({node_timeout}s)"
                logger.warning(f"[工作流] 节点 {node_id} 第{attempt+1}次执行超时")
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[工作流] 节点 {node_id} 第{attempt+1}次执行失败: {e}")

        duration_ms = int((time.perf_counter() - start) * 1000)
        return NodeResult(node_id, "failed", "", duration_ms, retries=node_max_retries, error=last_error)

    def _resolve_input(
        self, node_id: str, edges: list[dict], results: dict[str, NodeResult], initial_input: str
    ) -> str:
        """解析节点的输入来源"""
        incoming = [e for e in edges if e.get("target") == node_id]
        if not incoming:
            return initial_input
        # 取第一个上游节点的输出
        source_id = incoming[0].get("source")
        if source_id and source_id in results:
            return results[source_id].output
        return initial_input

    def _topological_sort(self, nodes: list[dict], edges: list[dict]) -> list[list[str]]:
        """拓扑排序，返回分层执行顺序（同层可并行）"""
        node_ids = {n["id"] for n in nodes}
        in_degree = {nid: 0 for nid in node_ids}
        adjacency = {nid: [] for nid in node_ids}

        for e in edges:
            src, tgt = e.get("source"), e.get("target")
            if src in node_ids and tgt in node_ids:
                adjacency[src].append(tgt)
                in_degree[tgt] = in_degree.get(tgt, 0) + 1

        # BFS 分层
        levels = []
        queue = [nid for nid in node_ids if in_degree.get(nid, 0) == 0]
        if not queue and node_ids:
            queue = [next(iter(node_ids))]

        while queue:
            levels.append(list(queue))
            next_level = []
            for nid in queue:
                for neighbor in adjacency.get(nid, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        next_level.append(neighbor)
            queue = next_level

        return levels

    def _evaluate_condition(self, condition: str, input_text: str) -> bool:
        """简单的条件表达式求值"""
        if not condition:
            return True
        condition_lower = condition.lower().strip()
        input_lower = input_text.lower()
        if "contains:" in condition_lower:
            keyword = condition.split(":", 1)[1].strip()
            return keyword.lower() in input_lower
        if "not_contains:" in condition_lower:
            keyword = condition.split(":", 1)[1].strip()
            return keyword.lower() not in input_lower
        if condition_lower in ("always", "true"):
            return True
        if condition_lower in ("never", "false"):
            return False
        # 默认：如果条件文本出现在输入中即满足
        return condition_lower in input_lower

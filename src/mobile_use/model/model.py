"""LLM 薄封装 — JSON 解析 + token 统计

消息构造在 agent 层完成，本模块只负责：
1. 调用 LangChain BaseChatModel.invoke()
2. 从响应中提取 JSON 并解析为 AgentOutput
3. 累计 token 消耗
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage
from loguru import logger
from pydantic import BaseModel

__all__ = ["LLMModel", "AgentOutput"]


class AgentOutput(BaseModel):
    """LLM 的结构化输出 — 推理过程 + 动作列表"""

    thinking: str = ""
    action: list[dict[str, Any]] = []


class LLMModel:
    """LLM 薄封装

    Args:
        llm: LangChain 兼容的聊天模型实例
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0

    @property
    def total_input_tokens(self) -> int:
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        return self._total_output_tokens

    @property
    def total_tokens(self) -> int:
        return self._total_input_tokens + self._total_output_tokens

    async def invoke(self, messages: list[BaseMessage]) -> AgentOutput:
        """调用 LLM 并解析响应为 AgentOutput

        Args:
            messages: LangChain 消息列表

        Returns:
            AgentOutput 解析后的结构化输出

        Raises:
            ValueError: 无法解析 LLM 输出
        """
        logger.debug("Invoking LLM with {} messages", len(messages))
        response = await self._llm.ainvoke(messages)

        # 提取文本内容
        raw_text = response.content if isinstance(response.content, str) else str(response.content)
        logger.debug("LLM raw response: {}", raw_text[:500])

        # 累计 token
        usage = getattr(response, "usage_metadata", None)
        if usage:
            input_tokens = usage.get("input_tokens", 0) or 0
            output_tokens = usage.get("output_tokens", 0) or 0
            self._total_input_tokens += input_tokens
            self._total_output_tokens += output_tokens

        return self.parse_response(raw_text)

    @staticmethod
    def parse_response(raw_text: str) -> AgentOutput:
        """从 LLM 输出中提取 JSON 并解析为 AgentOutput

        支持以下格式：
        - 纯 JSON: {"thinking": "...", "action": [...]}
        - Markdown 代码块: ```json ... ```
        - 混合文本中的 JSON 块

        Args:
            raw_text: LLM 原始输出文本

        Returns:
            AgentOutput

        Raises:
            ValueError: 无法提取或解析 JSON
        """
        json_str = LLMModel._extract_json(raw_text)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            # LLM 常在 thinking 字段中输出未转义引号，尝试修复
            data = LLMModel._try_repair_json(json_str)
            if data is None:
                # 修复失败，尝试用正则直接提取字段
                data = LLMModel._regex_extract(raw_text)
            if data is None:
                raise ValueError(
                    f"Failed to parse JSON from LLM output.\nRaw text: {raw_text[:500]}"
                )

        # 兼容 LLM 直接输出 action 对象而非列表的情况
        if isinstance(data.get("action"), dict):
            data["action"] = [data["action"]]

        try:
            return AgentOutput.model_validate(data)
        except Exception as e:
            raise ValueError(f"Failed to validate AgentOutput: {e}\nData: {data}") from e

    @staticmethod
    def _extract_json(text: str) -> str:
        """从文本中提取 JSON 字符串

        优先尝试 ```json 代码块，否则找第一个 { ... } 块。
        括号匹配时正确跳过字符串内的大括号。
        """
        # 1. 尝试 markdown 代码块
        code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
        if code_block:
            return code_block.group(1).strip()

        # 2. 尝试提取 { ... } 块（支持嵌套，跳过字符串内的括号）
        depth = 0
        start = -1
        in_string = False
        escape_next = False
        for i, ch in enumerate(text):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\":
                if in_string:
                    escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and start >= 0:
                    return text[start : i + 1]

        # 3. 全文当作 JSON 尝试
        return text.strip()

    @staticmethod
    def _try_repair_json(json_str: str) -> dict | None:
        """尝试修复 LLM 输出的常见 JSON 错误（如 thinking 中的未转义引号、重复输出）"""

        # 策略 1：修复 thinking 中未转义引号
        repaired = LLMModel._repair_thinking_quotes(json_str)
        if repaired is not None:
            return repaired

        # 策略 2：处理 LLM 重复输出（thinking 被拼接两次导致 action 断裂）
        # 原文形如：{"thinking":"...完整...","action":[{"action...重复的thinking...","action":[...]]}
        action_starts = list(re.finditer(r'"action"\s*:\s*\[', json_str))
        if action_starts:
            for match in reversed(action_starts):
                arr_start = match.end() - 1
                depth = 0
                arr_end = -1
                for i in range(arr_start, len(json_str)):
                    if json_str[i] == "[":
                        depth += 1
                    elif json_str[i] == "]":
                        depth -= 1
                        if depth == 0:
                            arr_end = i
                            break
                if arr_end < 0:
                    continue
                try:
                    actions = json.loads(json_str[arr_start : arr_end + 1])
                    before = json_str[: match.start()]
                    thinking_m = re.search(r'"thinking"\s*:\s*"(.*?)"', before, re.DOTALL)
                    if thinking_m:
                        return {"thinking": thinking_m.group(1).replace('\\"', '"'), "action": actions}
                except json.JSONDecodeError:
                    continue

        return None

    @staticmethod
    def _repair_thinking_quotes(json_str: str) -> dict | None:
        """修复 thinking 字段中的未转义双引号"""
        m = re.search(r'"thinking"\s*:\s*"', json_str)
        if not m:
            return None
        start = m.end()
        action_marker = re.search(r'",\s*"action"', json_str[start:])
        if not action_marker:
            return None
        thinking_raw = json_str[start : start + action_marker.start()]
        thinking_escaped = thinking_raw.replace('"', '\\"')
        repaired = json_str[:start] + thinking_escaped + json_str[start + action_marker.start() :]
        try:
            data = json.loads(repaired)
            if isinstance(data.get("action"), dict):
                data["action"] = [data["action"]]
            return data
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _regex_extract(raw_text: str) -> dict | None:
        """当 JSON 解析完全失败时，用正则直接提取 thinking 和 action 字段

        处理 LLM 常见的重复输出问题：thinking 文本被重复拼接导致 JSON 断裂。
        策略：找到最后一个完整的 "action":[...] 块（用括号计数处理嵌套），再从其前面提取 thinking。
        """
        # 找最后一个 "action":[...] 块，用括号计数处理嵌套数组
        action_matches = list(re.finditer(r'"action"\s*:\s*\[', raw_text))
        if not action_matches:
            return None

        actions = None
        for match in reversed(action_matches):
            # 从 [ 后开始，用括号计数找到匹配的 ]
            arr_start = match.end() - 1  # 指向 [
            depth = 0
            arr_end = -1
            for i in range(arr_start, len(raw_text)):
                if raw_text[i] == "[":
                    depth += 1
                elif raw_text[i] == "]":
                    depth -= 1
                    if depth == 0:
                        arr_end = i
                        break
            if arr_end < 0:
                continue
            try:
                actions = json.loads(raw_text[arr_start : arr_end + 1])
                break
            except json.JSONDecodeError:
                continue

        if actions is None:
            return None

        # 从 action 位置往前找最近的完整 "thinking":"..." 字段
        before_action = raw_text[: action_matches[-1].start()]
        thinking_matches = list(re.finditer(r'"thinking"\s*:\s*"(.*?)"', before_action, re.DOTALL))
        if not thinking_matches:
            return None
        thinking = thinking_matches[-1].group(1).replace('\\"', '"')

        return {"thinking": thinking, "action": actions}

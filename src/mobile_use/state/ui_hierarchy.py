"""UI 层级树数据模型"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ["UIElement"]


class UIElement(BaseModel):
    """UI 层级树中的单个元素节点"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    idx: int = -1  # 全局唯一编号（仅可交互元素分配 idx >= 0）
    class_name: str = ""
    resource_id: str = ""
    text: str = ""
    content_desc: str = ""
    package: str = ""
    checkable: bool = False
    checked: bool = False
    clickable: bool = False
    long_clickable: bool = False
    enabled: bool = False
    focusable: bool = False
    focused: bool = False
    scrollable: bool = False
    selected: bool = False
    index: int = -1  # XML 中的 sibling 顺序
    hint: str = ""
    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)  # (left, top, right, bottom)
    children: list[UIElement] = []

    @property
    def center(self) -> tuple[int, int]:
        """元素中心坐标"""
        left, top, right, bottom = self.bounds
        return ((left + right) // 2, (top + bottom) // 2)

    @property
    def is_interactive(self) -> bool:
        """是否为可交互元素（clickable 或 scrollable）"""
        return self.clickable or self.scrollable

    def to_llm_text(self) -> str:
        """输出带 idx 编号的紧凑文本，供 LLM 引用

        可交互元素（有 idx >= 0）带编号，非交互但有文本的元素无编号，格式示例：
            [0] TextView "确定" resource-id="btn_ok" clickable
            [1] EditText "请输入" resource-id="input_name"
            TextView "网络和互联网"
        """
        lines: list[str] = []
        self._collect_llm_lines(lines)
        return "\n".join(lines)

    def to_debug_text(self) -> str:
        """输出完整元素树（含非交互元素），用于调试"""
        lines: list[str] = []
        self._collect_debug_lines(lines)
        return "\n".join(lines)

    def _collect_debug_lines(self, lines: list[str], depth: int = 0) -> None:
        """递归收集调试文本行（所有元素）"""
        indent = "  " * depth
        short_class = self.class_name.rsplit(".", 1)[-1] if self.class_name else "Root"
        parts = [short_class]
        if self.idx >= 0:
            parts[0] = f"[{self.idx}] {parts[0]}"
        if self.text:
            parts.append(f'text="{self.text}"')
        if self.content_desc:
            parts.append(f'desc="{self.content_desc}"')
        if self.resource_id:
            short_id = self.resource_id.rsplit("/", 1)[-1] if "/" in self.resource_id else self.resource_id
            parts.append(f'id="{short_id}"')
        attrs = []
        if self.clickable:
            attrs.append("clickable")
        if self.long_clickable:
            attrs.append("long-clickable")
        if self.scrollable:
            attrs.append("scrollable")
        if self.enabled:
            attrs.append("enabled")
        if attrs:
            parts.append(" ".join(attrs))
        lines.append(indent + " ".join(parts))
        for child in self.children:
            child._collect_debug_lines(lines, depth + 1)

    def _collect_llm_lines(self, lines: list[str], depth: int = 0) -> None:
        """递归收集 LLM 文本行

        可交互元素（idx >= 0）带编号输出；非交互但有文本/描述的元素也输出，
        为 LLM 提供完整上下文（标签、标题、当前值等）。
        """
        # 判断是否应该输出此元素
        has_text = bool(self.text or self.content_desc)
        is_interactive = self.idx >= 0
        should_output = is_interactive or has_text

        if should_output:
            indent = "  " * depth
            parts: list[str] = []

            # 可交互元素带编号，非交互元素不带
            if is_interactive:
                parts.append(f"[{self.idx}]")

            # 简化类名（去掉包前缀）
            short_class = self.class_name.rsplit(".", 1)[-1] if self.class_name else "Unknown"
            parts.append(short_class)

            if self.text:
                parts.append(f'"{self.text}"')
            if self.content_desc:
                parts.append(f'desc="{self.content_desc}"')
            if self.resource_id:
                short_id = self.resource_id.rsplit("/", 1)[-1] if "/" in self.resource_id else self.resource_id
                parts.append(f'id="{short_id}"')
            if self.clickable:
                parts.append("clickable")
            if self.long_clickable:
                parts.append("long-clickable")
            if self.scrollable:
                parts.append("scrollable")

            lines.append(indent + " ".join(parts))

        for child in self.children:
            child._collect_llm_lines(lines, depth + (1 if should_output else 0))

"""文字输入动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["InputTextAction", "ClearTextAction"]


class InputTextAction(ActionModel):
    """在输入框中输入文字

    如指定 element_index，先点击该元素再输入；
    否则输入到当前焦点输入框。
    """

    text: str
    element_index: int | None = None


class ClearTextAction(ActionModel):
    """清空输入框文字

    如指定 element_index，先点击该元素再清空；
    否则清空当前焦点输入框。
    """

    element_index: int | None = None

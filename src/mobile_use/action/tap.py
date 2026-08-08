"""点击动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["TapAction"]


class TapAction(ActionModel):
    """点击屏幕上的元素

    可通过坐标 (x, y) 或元素索引 (element_index) 指定目标。
    """

    x: int | None = None
    y: int | None = None
    element_index: int | None = None

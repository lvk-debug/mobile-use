"""长按动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["LongPressAction"]


class LongPressAction(ActionModel):
    """长按屏幕坐标"""

    x: int
    y: int
    duration: float = 0.5

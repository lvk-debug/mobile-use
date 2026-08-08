"""滑动与滚动动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["SwipeAction", "ScrollAction"]


class SwipeAction(ActionModel):
    """滑动

    方式一：指定方向 (direction) + 可选距离比例 (distance)
    方式二：指定起止坐标 (sx, sy, ex, ey)
    """

    direction: str | None = None  # "up" | "down" | "left" | "right"
    distance: float = 1.0
    sx: int | None = None
    sy: int | None = None
    ex: int | None = None
    ey: int | None = None


class ScrollAction(ActionModel):
    """滚动页面

    distance 参数为屏幕比例倍数：
    - 1.0 = 滚动约半屏（默认）
    - 2.0 = 滚动约一整屏
    - 0.5 = 小幅滚动
    """

    direction: str  # "up" | "down" | "left" | "right"
    distance: float = 2.0

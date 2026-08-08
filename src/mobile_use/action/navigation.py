"""导航按键动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["PressKeyAction", "BackAction", "HomeAction"]


class PressKeyAction(ActionModel):
    """按下按键

    支持: back, home, enter, recent, power, volume_up, volume_down 等。
    """

    key_name: str


class BackAction(ActionModel):
    """按返回键（无参数）"""

    pass


class HomeAction(ActionModel):
    """按 Home 键（无参数）"""

    pass

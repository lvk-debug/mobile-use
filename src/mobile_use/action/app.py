"""应用管理动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["LaunchAppAction", "StopAppAction"]


class LaunchAppAction(ActionModel):
    """启动应用"""

    package_name: str
    activity: str | None = None


class StopAppAction(ActionModel):
    """停止应用"""

    package_name: str

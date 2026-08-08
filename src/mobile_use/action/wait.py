"""等待动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["WaitAction"]


class WaitAction(ActionModel):
    """等待指定秒数"""

    seconds: float = 1.0

"""错误报告动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["ErrorAction"]


class ErrorAction(ActionModel):
    """报告错误，表示当前步骤无法继续"""

    message: str = ""

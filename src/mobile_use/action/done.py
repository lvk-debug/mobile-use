"""任务完成动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["DoneAction"]


class DoneAction(ActionModel):
    """标记任务完成，返回结果"""

    answer: str = ""

"""动作注册与调度"""

from mobile_use.controller.controller import Controller
from mobile_use.controller.registry import ActionHandler, ActionInfo

__all__ = [
    "Controller",
    "ActionInfo",
    "ActionHandler",
]

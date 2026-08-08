"""动作参数模型"""

from mobile_use.action.app import LaunchAppAction, StopAppAction
from mobile_use.action.base import ActionModel, ActionResult
from mobile_use.action.done import DoneAction
from mobile_use.action.error import ErrorAction
from mobile_use.action.input_text import ClearTextAction, InputTextAction
from mobile_use.action.long_press import LongPressAction
from mobile_use.action.navigation import BackAction, HomeAction, PressKeyAction
from mobile_use.action.swipe import ScrollAction, SwipeAction
from mobile_use.action.tap import TapAction
from mobile_use.action.wait import WaitAction

__all__ = [
    "ActionModel",
    "ActionResult",
    "TapAction",
    "LongPressAction",
    "InputTextAction",
    "ClearTextAction",
    "SwipeAction",
    "ScrollAction",
    "PressKeyAction",
    "BackAction",
    "HomeAction",
    "LaunchAppAction",
    "StopAppAction",
    "WaitAction",
    "DoneAction",
    "ErrorAction",
]

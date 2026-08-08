"""动作注册表 — ActionInfo 数据结构与注册逻辑"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Coroutine

if TYPE_CHECKING:
    from mobile_use.action.base import ActionModel, ActionResult
    from mobile_use.driver.device import Device
    from mobile_use.state.device_state import DeviceState

# handler 签名: async (params, device, state, controller) -> ActionResult
ActionHandler = Callable[
    ["ActionModel", "Device", "DeviceState", Any],
    Coroutine[Any, Any, "ActionResult"],
]


@dataclass
class ActionInfo:
    """已注册动作的元数据"""

    name: str
    description: str
    param_model: type[ActionModel]
    handler: ActionHandler
    # 注册顺序（用于 prompt 排序）
    order: int = field(default=0)

"""动作控制器 — 注册表 + 执行调度"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from loguru import logger

from mobile_use.action.base import ActionModel, ActionResult
from mobile_use.controller.registry import ActionHandler, ActionInfo

if TYPE_CHECKING:
    from mobile_use.driver.device import Device
    from mobile_use.state.device_state import DeviceState

__all__ = ["Controller"]


class Controller:
    """动作注册表与执行调度器

    使用 @controller.action("描述") 装饰器注册动作 handler，
    通过 execute() 根据动作名查找并执行对应 handler。

    示例::

        controller = Controller()

        @controller.action("点击屏幕上的元素")
        async def tap(params: TapAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
            ...
    """

    def __init__(self, *, register_defaults: bool = True) -> None:
        self._actions: dict[str, ActionInfo] = {}
        self._order_counter: int = 0

        if register_defaults:
            from mobile_use.controller.default_actions import register_default_actions

            register_default_actions(self)

    # ── 装饰器 ────────────────────────────────────────────────────────────

    def action(
        self,
        description: str,
        *,
        name: str | None = None,
        param_model: type[ActionModel] | None = None,
    ) -> Callable[[ActionHandler], ActionHandler]:
        """注册动作 handler 的装饰器

        Args:
            description: 动作的自然语言描述（供 LLM 理解）
            name: 动作名，默认取函数名
            param_model: 参数模型类，默认从 handler 的 type hints 第一个参数推断

        Returns:
            原函数（不修改）
        """

        def decorator(fn: ActionHandler) -> ActionHandler:
            action_name = name or fn.__name__

            # 从 type hints 推断 param_model
            resolved_model = param_model
            if resolved_model is None:
                first_param = fn.__annotations__.get("params") if hasattr(fn, "__annotations__") else None
                # from __future__ import annotations 使注解变为字符串，需手动解析
                if isinstance(first_param, str):
                    first_param = fn.__globals__.get(first_param)
                if first_param and isinstance(first_param, type) and issubclass(first_param, ActionModel):
                    resolved_model = first_param
            if resolved_model is None:
                resolved_model = ActionModel

            self._actions[action_name] = ActionInfo(
                name=action_name,
                description=description,
                param_model=resolved_model,
                handler=fn,
                order=self._order_counter,
            )
            self._order_counter += 1
            logger.debug("Registered action: {} — {}", action_name, description)
            return fn

        return decorator

    # ── 执行 ──────────────────────────────────────────────────────────────

    async def execute(
        self,
        action_name: str,
        params: dict,
        device: Device,
        state: DeviceState,
    ) -> ActionResult:
        """查找并执行动作

        Args:
            action_name: 动作名称（如 "tap", "done"）
            params: 动作参数字典
            device: 设备实例
            state: 当前设备状态

        Returns:
            ActionResult 执行结果

        Raises:
            ValueError: 未知动作名
        """
        info = self._actions.get(action_name)
        if info is None:
            return ActionResult(
                success=False,
                message=f"Unknown action: {action_name!r}. Available: {list(self._actions.keys())}",
            )

        try:
            parsed_params = info.param_model.model_validate(params)
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Invalid params for {action_name!r}: {e}",
            )

        logger.info("Executing action: {} with {}", action_name, parsed_params.model_dump())
        try:
            result = await info.handler(parsed_params, device, state, self)
            return result
        except Exception as e:
            logger.error("Action {} failed: {}", action_name, e)
            return ActionResult(success=False, message=f"Action {action_name!r} failed: {e}")

    # ── 查询 ──────────────────────────────────────────────────────────────

    def get_action_info(self, name: str) -> ActionInfo | None:
        """获取已注册动作的信息"""
        return self._actions.get(name)

    def list_actions(self) -> list[ActionInfo]:
        """列出所有已注册动作，按注册顺序排列"""
        return sorted(self._actions.values(), key=lambda a: a.order)

    def get_action_descriptions(self) -> str:
        """获取所有动作的描述文本，供 prompt 使用

        返回格式:
            - tap: 点击屏幕上的元素 (params: x, y, element_index)
            - done: 标记任务完成 (params: answer)
        """
        lines: list[str] = []
        for info in self.list_actions():
            fields = info.param_model.model_fields
            param_names = ", ".join(fields.keys()) if fields else "无参数"
            lines.append(f"- {info.name}: {info.description} (params: {param_names})")
        return "\n".join(lines)

    def get_action_schemas(self) -> list[dict]:
        """获取所有动作的 JSON Schema，供 LLM 结构化输出使用"""
        schemas: list[dict] = []
        for info in self.list_actions():
            schema = info.param_model.model_json_schema()
            schemas.append({
                "name": info.name,
                "description": info.description,
                "parameters": schema,
            })
        return schemas

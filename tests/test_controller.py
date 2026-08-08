"""M3 Controller 单元测试"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mobile_use.action.base import ActionModel, ActionResult
from mobile_use.action.tap import TapAction
from mobile_use.controller.controller import Controller


class TestControllerRegistration:
    """动作注册测试"""

    def test_default_actions_registered(self):
        """Controller 默认注册内置动作"""
        ctrl = Controller()
        names = [info.name for info in ctrl.list_actions()]
        assert "tap" in names
        assert "done" in names
        assert "swipe" in names
        assert "launch_app" in names
        assert "back" in names
        assert "home" in names

    def test_no_defaults(self):
        """register_defaults=False 不注册内置动作"""
        ctrl = Controller(register_defaults=False)
        assert ctrl.list_actions() == []

    def test_custom_action_registration(self):
        """自定义动作注册"""
        ctrl = Controller(register_defaults=False)

        @ctrl.action("自定义测试动作", name="test_action")
        async def test_action(params: ActionModel, device, state, controller) -> ActionResult:
            return ActionResult(success=True)

        assert "test_action" in [info.name for info in ctrl.list_actions()]

    def test_action_name_from_function(self):
        """动作名默认取函数名"""
        ctrl = Controller(register_defaults=False)

        @ctrl.action("测试")
        async def my_action(params: ActionModel, device, state, controller) -> ActionResult:
            return ActionResult()

        assert "my_action" in [info.name for info in ctrl.list_actions()]

    def test_action_description(self):
        """动作描述正确存储"""
        ctrl = Controller()
        info = ctrl.get_action_info("tap")
        assert info is not None
        assert "点击" in info.description


class TestControllerExecute:
    """动作执行测试"""

    @pytest.fixture
    def mock_device(self):
        device = AsyncMock()
        device.tap = AsyncMock()
        return device

    @pytest.fixture
    def mock_state(self):
        from mobile_use.driver.device import AppInfo
        from mobile_use.state.device_state import DeviceState
        from mobile_use.state.ui_hierarchy import UIElement

        return DeviceState(
            ui_hierarchy=UIElement(idx=0, clickable=True, text="test"),
            screenshot=b"",
            current_app=AppInfo(package="com.test", activity=".Main"),
            width=1080,
            height=2400,
        )

    @pytest.mark.asyncio
    async def test_execute_tap_by_coords(self, mock_device, mock_state):
        """通过坐标执行 tap"""
        ctrl = Controller()
        result = await ctrl.execute("tap", {"x": 100, "y": 200}, mock_device, mock_state)
        assert result.success is True
        mock_device.tap.assert_called_once_with(100, 200)

    @pytest.mark.asyncio
    async def test_execute_tap_by_element_index(self, mock_device, mock_state):
        """通过元素索引执行 tap"""
        ctrl = Controller()
        result = await ctrl.execute("tap", {"element_index": 0}, mock_device, mock_state)
        assert result.success is True
        mock_device.tap.assert_called_once_with(0, 0)  # UIElement default bounds center

    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, mock_device, mock_state):
        """未知动作返回错误"""
        ctrl = Controller()
        result = await ctrl.execute("nonexistent", {}, mock_device, mock_state)
        assert result.success is False
        assert "Unknown action" in result.message

    @pytest.mark.asyncio
    async def test_execute_invalid_params(self, mock_device, mock_state):
        """无效参数返回错误"""
        ctrl = Controller()
        result = await ctrl.execute("long_press", {"x": "not_a_number"}, mock_device, mock_state)
        assert result.success is False
        assert "Invalid params" in result.message

    @pytest.mark.asyncio
    async def test_execute_done(self, mock_device, mock_state):
        """done 动作返回 final_answer"""
        ctrl = Controller()
        result = await ctrl.execute("done", {"answer": "完成了"}, mock_device, mock_state)
        assert result.success is True
        assert result.data["final_answer"] == "完成了"

    @pytest.mark.asyncio
    async def test_execute_custom_action(self, mock_device, mock_state):
        """自定义动作可执行"""
        ctrl = Controller()

        @ctrl.action("测试", name="custom")
        async def custom(params: ActionModel, device, state, controller) -> ActionResult:
            return ActionResult(success=True, message="custom executed")

        result = await ctrl.execute("custom", {}, mock_device, mock_state)
        assert result.success is True
        assert "custom executed" in result.message

    @pytest.mark.asyncio
    async def test_handler_exception_caught(self, mock_device, mock_state):
        """handler 抛异常时返回错误结果"""

        ctrl = Controller(register_defaults=False)

        @ctrl.action("会失败", name="fail")
        async def fail(params: ActionModel, device, state, controller) -> ActionResult:
            raise RuntimeError("boom")

        result = await ctrl.execute("fail", {}, mock_device, mock_state)
        assert result.success is False
        assert "boom" in result.message


class TestControllerDescriptions:
    """动作描述与 schema 测试"""

    def test_get_action_descriptions(self):
        ctrl = Controller()
        desc = ctrl.get_action_descriptions()
        assert "tap:" in desc
        assert "done:" in desc

    def test_get_action_schemas(self):
        ctrl = Controller()
        schemas = ctrl.get_action_schemas()
        tap_schema = next(s for s in schemas if s["name"] == "tap")
        assert "parameters" in tap_schema
        assert "description" in tap_schema

    def test_list_actions_ordered(self):
        """动作按注册顺序排列"""
        ctrl = Controller(register_defaults=False)

        @ctrl.action("第一个", name="first")
        async def first(params: ActionModel, device, state, controller) -> ActionResult:
            return ActionResult()

        @ctrl.action("第二个", name="second")
        async def second(params: ActionModel, device, state, controller) -> ActionResult:
            return ActionResult()

        names = [info.name for info in ctrl.list_actions()]
        assert names.index("first") < names.index("second")

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mobile_use.driver.device import AppInfo, Device, DeviceInfo
from mobile_use.state.device_state import DeviceState
from mobile_use.state.ui_hierarchy import UIElement


class TestDeviceInfo:
    """DeviceInfo 模型测试"""

    def test_fields(self):
        info = DeviceInfo(
            serial="emulator-5554",
            brand="Google",
            model="Pixel 7",
            sdk_version=34,
            android_version="14",
            screen_width=1080,
            screen_height=2400,
        )
        assert info.serial == "emulator-5554"
        assert info.brand == "Google"
        assert info.model == "Pixel 7"
        assert info.sdk_version == 34
        assert info.android_version == "14"
        assert info.screen_width == 1080
        assert info.screen_height == 2400


class TestAppInfo:
    """AppInfo 模型测试"""

    def test_fields(self):
        app = AppInfo(
            package="com.android.settings",
            activity="com.android.settings.Settings",
        )
        assert app.package == "com.android.settings"
        assert app.activity == "com.android.settings.Settings"


class TestDeviceBasicInfo:
    """Device 设备信息类接口测试"""

    @pytest.mark.asyncio
    async def test_info(self, device: Device, mock_u2_device: MagicMock):
        """info() 返回正确的 DeviceInfo"""
        result = await device.info()
        assert isinstance(result, DeviceInfo)
        assert result.serial == "emulator-5554"
        assert result.brand == "Google"
        assert result.model == "Pixel 7"
        assert result.sdk_version == 34
        assert result.android_version == "14"
        assert result.screen_width == 1080
        assert result.screen_height == 2400

    @pytest.mark.asyncio
    async def test_current_app(self, device: Device, mock_u2_device: MagicMock):
        """current_app() 返回正确的 AppInfo"""
        result = await device.current_app()
        assert isinstance(result, AppInfo)
        assert result.package == "com.android.launcher3"
        assert result.activity == "com.android.launcher3.Launcher"

    @pytest.mark.asyncio
    async def test_window_size(self, device: Device):
        """window_size() 返回屏幕分辨率"""
        w, h = await device.window_size()
        assert w == 1080
        assert h == 2400


class TestDeviceInteraction:
    """Device 交互类接口测试"""

    @pytest.mark.asyncio
    async def test_tap(self, device: Device, mock_u2_device: MagicMock):
        """tap() 调用底层 click"""
        await device.tap(100, 200)
        mock_u2_device.click.assert_called_once_with(100, 200)

    @pytest.mark.asyncio
    async def test_input_text(self, device: Device, mock_u2_device: MagicMock):
        """input_text() 调用底层 send_keys"""
        await device.input_text("Hello World")
        mock_u2_device.send_keys.assert_called_once_with("Hello World")

    @pytest.mark.asyncio
    async def test_swipe(self, device: Device, mock_u2_device: MagicMock):
        """swipe() 调用底层 swipe_ext"""
        await device.swipe("up", distance=0.8)
        mock_u2_device.swipe_ext.assert_called_once_with("up", scale=0.8)

    @pytest.mark.asyncio
    async def test_press_back(self, device: Device, mock_u2_device: MagicMock):
        """press_back() 调用底层 press('back')"""
        await device.press_back()
        mock_u2_device.press.assert_called_once_with("back")

    @pytest.mark.asyncio
    async def test_screenshot(self, device: Device):
        """screenshot() 返回 PNG bytes"""
        result = await device.screenshot()
        assert isinstance(result, bytes)
        # PNG 魔数
        assert result[:4] == b"\x89PNG"


class TestDeviceStateCollection:
    """Device M2 状态采集测试"""

    @pytest.mark.asyncio
    async def test_get_ui_hierarchy_returns_element_and_xml(self, device: Device):
        """get_ui_hierarchy() 返回 (UIElement, str)"""
        root, raw_xml = await device.get_ui_hierarchy()
        assert isinstance(root, UIElement)
        assert root.class_name == "android.widget.FrameLayout"
        assert isinstance(raw_xml, str)
        assert len(raw_xml) > 0

    @pytest.mark.asyncio
    async def test_get_state_returns_device_state(self, device: Device):
        """get_state() 返回完整 DeviceState"""
        state = await device.get_state()
        assert isinstance(state, DeviceState)
        assert isinstance(state.ui_hierarchy, UIElement)
        assert isinstance(state.ui_hierarchy_xml, str)
        assert len(state.ui_hierarchy_xml) > 0
        assert isinstance(state.screenshot, bytes)
        assert state.screenshot[:4] == b"\x89PNG"
        assert isinstance(state.current_app, AppInfo)
        assert state.width == 1080
        assert state.height == 2400

    @pytest.mark.asyncio
    async def test_get_state_current_app(self, device: Device):
        """get_state() 中 current_app 正确"""
        state = await device.get_state()
        assert state.current_app.package == "com.android.launcher3"

    @pytest.mark.asyncio
    async def test_get_ui_hierarchy_has_interactive_elements(self, device: Device):
        """get_ui_hierarchy() 解析出可交互元素"""
        root, _ = await device.get_ui_hierarchy()
        text = root.to_llm_text()
        assert "搜索" in text
        assert "设置" in text


class TestFindElement:
    """Device 元素定位测试"""

    @pytest.mark.asyncio
    async def test_find_by_text(self, device: Device):
        """按 text 查找元素"""
        elem = await device.find_element(text="搜索")
        assert elem is not None
        assert elem.text == "搜索"
        assert elem.class_name == "android.widget.TextView"

    @pytest.mark.asyncio
    async def test_find_by_resource_id(self, device: Device):
        """按 resource_id 查找元素"""
        elem = await device.find_element(resource_id="com.android.launcher3:id/search_bar")
        assert elem is not None
        assert elem.text == "搜索"

    @pytest.mark.asyncio
    async def test_find_by_resource_id_short(self, device: Device):
        """按短 resource_id 查找元素"""
        elem = await device.find_element(resource_id="search_bar")
        assert elem is not None
        assert elem.text == "搜索"

    @pytest.mark.asyncio
    async def test_find_by_content_desc(self, device: Device):
        """按 content_desc 查找元素"""
        elem = await device.find_element(content_desc="打开设置")
        assert elem is not None
        assert elem.text == "设置"

    @pytest.mark.asyncio
    async def test_find_by_xpath(self, device: Device):
        """按 xpath（类名）查找元素"""
        elem = await device.find_element(xpath="TextView")
        assert elem is not None
        assert elem.class_name == "android.widget.TextView"

    @pytest.mark.asyncio
    async def test_find_not_found(self, device: Device):
        """未找到返回 None"""
        elem = await device.find_element(text="不存在的文本")
        assert elem is None

    @pytest.mark.asyncio
    async def test_find_elements_multiple(self, device: Device):
        """find_elements 返回所有匹配的 TextView"""
        elements = await device.find_elements(xpath="TextView")
        assert len(elements) >= 2  # 搜索、设置、相机 都是 TextView
        texts = [e.text for e in elements]
        assert "搜索" in texts
        assert "设置" in texts
        assert "相机" in texts

    @pytest.mark.asyncio
    async def test_find_elements_empty(self, device: Device):
        """无匹配返回空列表"""
        elements = await device.find_elements(text="不存在")
        assert elements == []

    @pytest.mark.asyncio
    async def test_find_element_bounds(self, device: Device):
        """找到的元素有正确的 bounds"""
        elem = await device.find_element(text="搜索")
        assert elem is not None
        assert elem.bounds == (100, 200, 980, 280)

    @pytest.mark.asyncio
    async def test_find_element_center(self, device: Device):
        """找到的元素 center 属性正确"""
        elem = await device.find_element(text="搜索")
        assert elem is not None
        assert elem.center == (540, 240)

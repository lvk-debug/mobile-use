from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mobile_use.driver.connection import ConnectionConfig

# ── UI 层级测试用 XML ────────────────────────────────────────────────────

SAMPLE_UI_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
        package="com.android.launcher3" checkable="false" checked="false"
        clickable="false" enabled="true" focusable="false" focused="false"
        scrollable="false" selected="false" bounds="[0,0][1080,2400]">
    <node index="0" text="" resource-id="com.android.launcher3:id/workspace"
          class="android.widget.FrameLayout" package="com.android.launcher3"
          checkable="false" checked="false" clickable="true" enabled="true"
          focusable="false" focused="false" scrollable="true" selected="false"
          bounds="[0,0][1080,2400]">
      <node index="0" text="搜索" resource-id="com.android.launcher3:id/search_bar"
            class="android.widget.TextView" package="com.android.launcher3"
            checkable="false" checked="false" clickable="true" enabled="true"
            focusable="true" focused="false" scrollable="false" selected="false"
            bounds="[100,200][980,280]" />
      <node index="1" text="" resource-id="com.android.launcher3:id/icon_grid"
            class="android.view.ViewGroup" package="com.android.launcher3"
            checkable="false" checked="false" clickable="false" enabled="true"
            focusable="false" focused="false" scrollable="false" selected="false"
            bounds="[0,300][1080,2200]">
        <node index="0" text="设置" resource-id=""
              class="android.widget.TextView" package="com.android.launcher3"
              checkable="false" checked="false" clickable="true" enabled="true"
              focusable="true" focused="false" scrollable="false" selected="false"
              bounds="[50,400][250,500]" content-desc="打开设置" />
        <node index="1" text="相机" resource-id=""
              class="android.widget.TextView" package="com.android.launcher3"
              checkable="false" checked="false" clickable="true" enabled="true"
              focusable="true" focused="false" scrollable="false" selected="false"
              bounds="[280,400][480,500]" content-desc="打开相机" />
      </node>
    </node>
  </node>
</hierarchy>
"""


@pytest.fixture
def mock_u2_device() -> MagicMock:
    """模拟 uiautomator2.Device，不依赖真实设备"""
    device = MagicMock()

    # device_info — 直接赋值 dict（u2 中是属性，不是方法）
    device.device_info = {
        "brand": "Google",
        "model": "Pixel 7",
        "sdkInt": 34,
        "version": "14",
    }

    # window_size
    device.window_size.return_value = (1080, 2400)

    # app_current
    device.app_current.return_value = {
        "package": "com.android.launcher3",
        "activity": "com.android.launcher3.Launcher",
    }

    # screenshot → PIL Image
    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    device.screenshot.return_value = img

    # dump_hierarchy
    device.dump_hierarchy.return_value = SAMPLE_UI_XML

    # app_list
    device.app_list.return_value = [
        "com.android.settings",
        "com.android.chrome",
    ]

    return device


@pytest.fixture
def connection_config() -> ConnectionConfig:
    """默认连接配置"""
    return ConnectionConfig(serial="emulator-5554", connect_type="usb")


@pytest.fixture
def device(mock_u2_device: MagicMock, connection_config: ConnectionConfig):
    """创建 Device 实例，使用 mock u2 设备"""
    from mobile_use.driver.device import Device

    return Device(u2_device=mock_u2_device, config=connection_config)

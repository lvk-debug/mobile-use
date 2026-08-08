"""设备状态快照数据模型"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from mobile_use.driver.device import AppInfo
from mobile_use.state.ui_hierarchy import UIElement

__all__ = ["DeviceState"]


class DeviceState(BaseModel):
    """设备完整状态快照

    包含 UI 层级树、原始 XML、屏幕截图、当前应用信息和屏幕尺寸，
    供 Agent 在 observe 阶段使用。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    ui_hierarchy: UIElement
    ui_hierarchy_xml: str = ""  # 原始 XML，保留完整元素信息
    screenshot: bytes
    current_app: AppInfo
    width: int = 0
    height: int = 0

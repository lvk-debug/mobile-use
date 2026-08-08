from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import adbutils
import uiautomator2 as u2
from loguru import logger
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from mobile_use.driver.device import Device


class ConnectionConfig(BaseModel):
    """设备连接配置"""

    serial: str = Field(description="设备序列号或 IP 地址")
    connect_type: str = Field(default="usb", description="连接类型: usb | wifi")
    command_timeout: float = Field(default=10.0, description="命令超时时间(秒)")
    skip_waiting: bool = Field(default=False, description="跳过等待设备就绪")
    server_url: str | None = Field(default=None, description="atx-server 地址")


class ConnectionManager:
    """管理设备连接、断开、重连"""

    def __init__(self) -> None:
        self._connections: dict[str, u2.Device] = {}

    async def connect(self, config: ConnectionConfig) -> Device:
        """连接设备，返回 Device 实例"""
        from mobile_use.driver.device import Device

        serial = config.serial
        logger.info("Connecting to device: {}", serial)

        u2_device = await asyncio.to_thread(self._create_u2_device, config)
        self._connections[serial] = u2_device

        device = Device(u2_device=u2_device, config=config)
        logger.info("Connected to device: {}", serial)
        return device

    async def disconnect(self, device: Device) -> None:
        """断开设备连接"""
        serial = device.serial
        logger.info("Disconnecting device: {}", serial)

        if serial in self._connections:
            self._connections.pop(serial)
            logger.info("Disconnected device: {}", serial)

    async def reconnect(
        self,
        device: Device,
        max_retries: int = 3,
        delay: float = 2.0,
    ) -> Device:
        """断线重连，最多重试 max_retries 次"""
        config = device.config
        serial = config.serial
        logger.info("Reconnecting device: {} (max {} retries)", serial, max_retries)

        for attempt in range(1, max_retries + 1):
            try:
                await self.disconnect(device)
            except Exception:
                pass

            try:
                new_device = await self.connect(config)
                logger.info("Reconnected device: {} on attempt {}", serial, attempt)
                return new_device
            except Exception as e:
                logger.warning("Reconnect attempt {} failed: {}", attempt, e)
                if attempt < max_retries:
                    await asyncio.sleep(delay)

        raise ConnectionError(
            f"Failed to reconnect device {serial} after {max_retries} attempts"
        )

    async def list_devices(self) -> list[str]:
        """列出所有已连接的 ADB 设备序列号"""
        client = adbutils.AdbClient()
        devices = await asyncio.to_thread(client.device_list)
        return [d.serial for d in devices]

    def _create_u2_device(self, config: ConnectionConfig) -> u2.Device:
        """同步创建 u2 设备连接（在线程中运行）"""
        kwargs: dict = {
            "serial": config.serial,
        }
        if config.server_url:
            kwargs["server_url"] = config.server_url

        device = u2.connect(**kwargs)
        device.settings["wait_timeout"] = config.command_timeout
        return device

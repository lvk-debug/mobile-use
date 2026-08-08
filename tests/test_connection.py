from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from mobile_use.driver.connection import ConnectionConfig, ConnectionManager


class TestConnectionConfig:
    """ConnectionConfig 数据模型测试"""

    def test_default_values(self):
        """默认值：connect_type=usb, command_timeout=10, skip_waiting=False"""
        config = ConnectionConfig(serial="emulator-5554")
        assert config.serial == "emulator-5554"
        assert config.connect_type == "usb"
        assert config.command_timeout == 10.0
        assert config.skip_waiting is False
        assert config.server_url is None

    def test_custom_values(self):
        """自定义所有字段"""
        config = ConnectionConfig(
            serial="192.168.1.100:5555",
            connect_type="wifi",
            command_timeout=30.0,
            skip_waiting=True,
            server_url="http://localhost:7912",
        )
        assert config.serial == "192.168.1.100:5555"
        assert config.connect_type == "wifi"
        assert config.command_timeout == 30.0
        assert config.skip_waiting is True
        assert config.server_url == "http://localhost:7912"


class TestConnectionManager:
    """ConnectionManager 连接管理测试"""

    @pytest.mark.asyncio
    async def test_connect_returns_device(self, mock_u2_device: MagicMock):
        """连接成功后返回 Device 实例"""
        config = ConnectionConfig(serial="emulator-5554")

        with patch("mobile_use.driver.connection.u2") as mock_u2:
            mock_u2.connect.return_value = mock_u2_device
            manager = ConnectionManager()
            device = await manager.connect(config)

            assert device.serial == "emulator-5554"
            assert device.raw is mock_u2_device
            mock_u2.connect.assert_called_once_with(serial="emulator-5554")

    @pytest.mark.asyncio
    async def test_reconnect_success(self, mock_u2_device: MagicMock):
        """重连成功返回新 Device 实例"""
        config = ConnectionConfig(serial="emulator-5554")

        with patch("mobile_use.driver.connection.u2") as mock_u2:
            mock_u2.connect.return_value = mock_u2_device
            manager = ConnectionManager()

            # 先连接
            device = await manager.connect(config)

            # 重连
            new_device = await manager.reconnect(device, max_retries=3)
            assert new_device.serial == "emulator-5554"
            assert mock_u2.connect.call_count >= 2

    @pytest.mark.asyncio
    async def test_reconnect_exhausted(self, mock_u2_device: MagicMock):
        """重连次数耗尽后抛出 ConnectionError"""
        config = ConnectionConfig(serial="emulator-5554")

        with patch("mobile_use.driver.connection.u2") as mock_u2:
            # 第一次连接成功，后续全部失败
            mock_u2.connect.side_effect = [
                mock_u2_device,
                ConnectionError("fail"),
                ConnectionError("fail"),
                ConnectionError("fail"),
            ]
            mock_u2_device.service.return_value = MagicMock()

            manager = ConnectionManager()
            device = await manager.connect(config)

            with pytest.raises(ConnectionError, match="Failed to reconnect"):
                await manager.reconnect(device, max_retries=3)

    @pytest.mark.asyncio
    async def test_list_devices(self):
        """列出已连接的 ADB 设备"""
        with patch("mobile_use.driver.connection.u2") as mock_u2:
            mock_u2.Adb.devices.return_value = [
                ("emulator-5554", "device"),
                ("192.168.1.100:5555", "device"),
            ]

            manager = ConnectionManager()
            devices = await manager.list_devices()

            assert devices == ["emulator-5554", "192.168.1.100:5555"]


if __name__ == "__main__":
    pass

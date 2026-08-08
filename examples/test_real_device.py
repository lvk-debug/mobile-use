"""真机连接测试脚本

使用方法:
    python examples/test_real_device.py [serial]

不传 serial 则自动使用第一台 USB 设备。
"""

import asyncio
import sys

from mobile_use import ConnectionConfig, ConnectionManager


async def main(serial: str | None = None) -> None:
    manager = ConnectionManager()

    # 1. 列出已连接设备
    print("=" * 50)
    print("[1] list devices")
    devices = await manager.list_devices()
    print(f"    devices: {devices}")

    if not devices:
        print("    [FAIL] no device found, check USB and adb authorization")
        return

    serial = serial or devices[0]
    print(f"    using: {serial}")

    # 2. 连接设备
    print()
    print("[2] connect")
    config = ConnectionConfig(serial=serial, connect_type="usb")
    device = await manager.connect(config)
    print(f"    [OK] connected: {device.serial}")

    try:
        # 3. 获取设备信息
        print()
        print("[3] device info")
        info = await device.info()
        print(f"    brand:    {info.brand}")
        print(f"    model:    {info.model}")
        print(f"    android:  {info.android_version}")
        print(f"    sdk:      {info.sdk_version}")
        print(f"    screen:   {info.screen_width} x {info.screen_height}")

        # 4. 当前前台应用
        print()
        print("[4] current app")
        app = await device.current_app()
        print(f"    package:  {app.package}")
        print(f"    activity: {app.activity}")

        # 5. 截图
        print()
        print("[5] screenshot")
        png = await device.screenshot()
        path = "examples/screen.png"
        with open(path, "wb") as f:
            f.write(png)
        print(f"    [OK] saved: {path} ({len(png)} bytes)")

        # 6. 基础交互测试
        print()
        print("[6] interaction test")

        await device.input_text("hello world")
        await asyncio.sleep(0.5)
        print("    [OK] input done")



        # tap 屏幕中央
        w, h = await device.window_size()
        cx, cy = w // 2, h // 2
        print(f"    tap center: ({cx}, {cy})")
        await device.tap(cx, cy)
        await asyncio.sleep(0.5)
        print("    [OK] tap done")

        # swipe 上滑
        print("    swipe up")
        await device.swipe("up", distance=0.5)
        await asyncio.sleep(0.5)
        print("    [OK] swipe done")

        # press back
        print("    press back")
        await device.press_back()
        await asyncio.sleep(0.5)
        print("    [OK] press_back done")

        print()
        print("=" * 50)
        print("[OK] All tests passed! M1 verified.")

    finally:
        await manager.disconnect(device)
        print("    device disconnected")


if __name__ == "__main__":
    serial = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(serial))

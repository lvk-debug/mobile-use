"""交互状态测试脚本 — 验证 M2: UI 层级解析 + 状态采集 + 元素定位

使用方法:
    python examples/test_state.py [serial]

不传 serial 则自动使用第一台 USB 设备。

测试内容:
    1. 获取 UI 层级树并输出 LLM 可读文本
    2. 获取完整设备状态快照
    3. 按 text / resource_id / content_desc / xpath 查找元素
    4. 根据元素坐标执行点击
"""

import asyncio
import sys
import time

from mobile_use import ConnectionConfig, ConnectionManager


def print_element(elem, indent: str = "    ") -> None:
    """格式化打印 UIElement 信息"""
    print(f"{indent}[{elem.idx}] {elem.class_name.rsplit('.', 1)[-1]}")
    if elem.text:
        print(f"{indent}  text:    {elem.text!r}")
    if elem.resource_id:
        print(f"{indent}  id:      {elem.resource_id}")
    if elem.content_desc:
        print(f"{indent}  desc:    {elem.content_desc!r}")
    print(f"{indent}  bounds:  {elem.bounds}")
    print(f"{indent}  center:  {elem.center}")
    flags = []
    if elem.clickable:
        flags.append("clickable")
    if elem.scrollable:
        flags.append("scrollable")
    if elem.enabled:
        flags.append("enabled")
    if flags:
        print(f"{indent}  flags:   {', '.join(flags)}")


async def main(serial: str | None = None) -> None:
    manager = ConnectionManager()

    # ── 0. 连接设备 ──────────────────────────────────────────────────────
    print("=" * 60)
    print("[0] connect")
    devices = await manager.list_devices()
    print(f"    devices: {devices}")

    if not devices:
        print("    [FAIL] no device found, check USB and adb authorization")
        return

    serial = serial or devices[0]
    config = ConnectionConfig(serial=serial, connect_type="usb")
    device = await manager.connect(config)
    print(f"    [OK] connected: {device.serial}")

    try:
        # ── 1. UI 层级树 ─────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("[1] UI hierarchy → LLM text")
        root, raw_xml = await device.get_ui_hierarchy()
        print(f"    raw XML: {len(raw_xml)} chars")
        llm_text = root.to_llm_text()
        lines = llm_text.splitlines()
        print(f"    interactive elements ({len(lines)} total):")
        if lines:
            print()
            for line in lines:
                print(f"    {line}")
        else:
            print(f"    [WARN] no interactive elements found, root={root.class_name!r}")

        # ── 2. 完整设备状态 ──────────────────────────────────────────────
        print()
        print("=" * 60)
        print("[2] device state snapshot")
        state = await device.get_state()
        print(f"    screen:    {state.width} x {state.height}")
        print(f"    app:       {state.current_app.package}")
        print(f"    activity:  {state.current_app.activity}")
        print(f"    screenshot: {len(state.screenshot)} bytes")
        print(f"    hierarchy:  {state.ui_hierarchy.class_name}")

        # 保存截图
        png_path = "examples/screen_state.png"
        with open(png_path, "wb") as f:
            f.write(state.screenshot)
        print(f"    [OK] screenshot saved: {png_path}")

        # ── 3. 元素定位 — find_element ───────────────────────────────────
        # print()
        # print("=" * 60)
        # print("[3] find_element")

        # # 3a. 按 xpath（类名）查找第一个 TextView
        # print()
        # print("  [3a] find_element(xpath='TextView')")
        # elem = await device.find_element(xpath="TextView")
        # if elem:
        #     print_element(elem)
        # else:
        #     print("    [!] not found")

        # # 3b. 按 resource_id 查找
        # print()
        # print("  [3b] find_element by resource_id")
        # # 尝试查找常见的搜索栏 id
        # for rid in ["search_bar", "search_box", "search", "input"]:
        #     elem = await device.find_element(resource_id=rid)
        #     if elem:
        #         print(f"    found by id={rid!r}:")
        #         print_element(elem)
        #         break
        # else:
        #     print("    [!] no search input found by common ids")

        # # 3c. 按 content_desc 查找
        # print()
        # print("  [3c] find_element by content_desc")
        # # 遍历所有有 content_desc 的元素
        # desc_elems = [e for e in _walk_tree(root) if e.content_desc]
        # if desc_elems:
        #     print(f"    found {len(desc_elems)} elements with content_desc:")
        #     for e in desc_elems[:5]:
        #         print(f"      [{e.idx}] desc={e.content_desc!r}  center={e.center}")
        # else:
        #     print("    [!] no elements with content_desc")

        # # ── 4. 元素定位 — find_elements ──────────────────────────────────
        # print()
        # print("=" * 60)
        # print("[4] find_elements")

        # # 4a. 找所有 TextView
        # text_views = await device.find_elements(xpath="TextView")
        # print(f"    TextViews: {len(text_views)}")
        # for e in text_views[:10]:
        #     label = e.text or e.content_desc or "(empty)"
        #     print(f"      [{e.idx}] {label!r}  bounds={e.bounds}")

        # # 4b. 找所有可点击元素
        # clickable = [e for e in _walk_tree(root) if e.clickable]
        # print(f"\n    clickable total: {len(clickable)}")
        # for e in clickable[:10]:
        #     label = e.text or e.content_desc or e.resource_id or "(unnamed)"
        #     print(f"      [{e.idx}] {label!r}  center={e.center}")

        # # ── 5. 基于元素坐标的交互 ────────────────────────────────────────
        # print()
        # print("=" * 60)
        # print("[5] tap element by center")

        # # 找一个可点击的 TextView 并点击其中心
        # target = await device.find_element(xpath="TextView")
        # if target and target.clickable:
        #     cx, cy = target.center
        #     label = target.text or target.content_desc or target.class_name
        #     print(f"    target: [{target.idx}] {label!r}")
        #     print(f"    center: ({cx}, {cy})")
        #     print("    tapping...")
        #     await device.tap(cx, cy)
        #     time.sleep(1)
        #     print("    [OK] tap done")

        #     # 点击后再次获取状态，观察变化
        #     print("    state after tap:")
        #     new_state = await device.get_state()
        #     new_app = new_state.current_app
        #     print(f"      app: {new_app.package}")
        #     new_root = new_state.ui_hierarchy
        #     new_text = new_root.to_llm_text()
        #     new_count = new_text.count("\n") + 1
        #     print(f"      interactive elements: {new_count}")
        # else:
        #     print("    [!] no clickable TextView found, skipping tap test")
        #     # fallback: 点击屏幕中央
        #     w, h = await device.window_size()
        #     cx, cy = w // 2, h // 2
        #     print(f"    fallback: tap center ({cx}, {cy})")
        #     await device.tap(cx, cy)
        #     time.sleep(1)
        #     print("    [OK] tap done")

        # # ── 6. 按 text 查找并交互 ────────────────────────────────────────
        # print()
        # print("=" * 60)
        # print("[6] find by text → tap")

        # # 遍历当前页面所有有 text 的可点击元素
        # clickable_with_text = [
        #     e for e in _walk_tree(root) if e.clickable and e.text
        # ]
        # if clickable_with_text:
        #     target = clickable_with_text[0]
        #     print(f"    target: [{target.idx}] text={target.text!r}")
        #     cx, cy = target.center
        #     print(f"    center: ({cx}, {cy})")
        #     await device.tap(cx, cy)
        #     time.sleep(1)
        #     print("    [OK] tap done")
        # else:
        #     print("    [!] no clickable element with text found")

        # # ── 完成 ─────────────────────────────────────────────────────────
        # print()
        # print("=" * 60)
        # print("[OK] All M2 state tests passed!")
        # print("    - UI hierarchy parsing ✓")
        # print("    - Device state snapshot ✓")
        # print("    - Element location ✓")
        # print("    - Tap by element center ✓")

    finally:
        await manager.disconnect(device)
        print("    device disconnected")


def _walk_tree(elem):
    """递归遍历 UIElement 树，yield 所有节点"""
    yield elem
    for child in elem.children:
        yield from _walk_tree(child)


if __name__ == "__main__":
    serial = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(serial))

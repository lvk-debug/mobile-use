"""内置默认动作 — 随 Controller 自动注册"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from mobile_use.action.app import LaunchAppAction, StopAppAction
from mobile_use.action.base import ActionModel, ActionResult
from mobile_use.action.done import DoneAction
from mobile_use.action.error import ErrorAction
from mobile_use.action.input_text import ClearTextAction, InputTextAction
from mobile_use.action.long_press import LongPressAction
from mobile_use.action.navigation import BackAction, HomeAction, PressKeyAction
from mobile_use.action.swipe import ScrollAction, SwipeAction
from mobile_use.action.tap import TapAction
from mobile_use.action.wait import WaitAction
from mobile_use.controller.controller import Controller

if TYPE_CHECKING:
    from mobile_use.driver.device import Device
    from mobile_use.state.device_state import DeviceState


def register_default_actions(controller: Controller) -> None:
    """将所有内置动作注册到 Controller"""

    # ── tap ────────────────────────────────────────────────────────────────

    @controller.action("点击屏幕上的元素，可通过坐标 (x,y) 或元素索引 (element_index) 指定目标", name="tap")
    async def tap(params: TapAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
        if params.element_index is not None:
            elem = _find_element_by_idx(state, params.element_index)
            if elem is None:
                return ActionResult(success=False, message=f"Element with index {params.element_index} not found")
            cx, cy = elem.center
            await device.tap(cx, cy)
            return ActionResult(success=True, message=f"Tapped element [{params.element_index}] at ({cx}, {cy})")
        if params.x is not None and params.y is not None:
            await device.tap(params.x, params.y)
            return ActionResult(success=True, message=f"Tapped at ({params.x}, {params.y})")
        return ActionResult(success=False, message="Must provide either (x, y) or element_index")

    # ── long_press ─────────────────────────────────────────────────────────

    @controller.action("长按屏幕坐标", name="long_press")
    async def long_press(
        params: LongPressAction, device: Device, state: DeviceState, ctrl: Controller
    ) -> ActionResult:
        await device.long_press(params.x, params.y, params.duration)
        return ActionResult(success=True, message=f"Long pressed at ({params.x}, {params.y}) for {params.duration}s")

    # ── input_text ─────────────────────────────────────────────────────────

    @controller.action("在输入框中输入文字", name="input_text")
    async def input_text(
        params: InputTextAction, device: Device, state: DeviceState, ctrl: Controller
    ) -> ActionResult:
        if params.element_index is not None:
            elem = _find_element_by_idx(state, params.element_index)
            if elem is None:
                return ActionResult(
                    success=False, message=f"Element with index {params.element_index} not found"
                )
            cx, cy = elem.center
            await device.tap(cx, cy)
            await asyncio.sleep(0.3)
        await device.input_text(params.text)
        return ActionResult(success=True, message=f"Input text: {params.text!r}")

    # ── clear_text ─────────────────────────────────────────────────────────

    @controller.action("清空输入框文字", name="clear_text")
    async def clear_text(
        params: ClearTextAction, device: Device, state: DeviceState, ctrl: Controller
    ) -> ActionResult:
        if params.element_index is not None:
            elem = _find_element_by_idx(state, params.element_index)
            if elem is None:
                return ActionResult(
                    success=False, message=f"Element with index {params.element_index} not found"
                )
            cx, cy = elem.center
            await device.tap(cx, cy)
            await asyncio.sleep(0.3)
        await device.clear_text()
        return ActionResult(success=True, message="Cleared text")

    # ── swipe ──────────────────────────────────────────────────────────────

    @controller.action(
        "滑动屏幕，可指定方向 (up/down/left/right) 或起止坐标 (sx,sy,ex,ey)", name="swipe"
    )
    async def swipe(params: SwipeAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
        if params.sx is not None and params.sy is not None and params.ex is not None and params.ey is not None:
            await device.swipe_coords(params.sx, params.sy, params.ex, params.ey)
            return ActionResult(
                success=True,
                message=f"Swiped from ({params.sx},{params.sy}) to ({params.ex},{params.ey})",
            )
        if params.direction:
            await device.swipe(params.direction, params.distance)
            return ActionResult(
                success=True, message=f"Swiped {params.direction} (distance={params.distance})"
            )
        return ActionResult(success=False, message="Must provide direction or coordinates")

    # ── scroll ─────────────────────────────────────────────────────────────

    @controller.action("滚动页面", name="scroll")
    async def scroll(params: ScrollAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
        await device.swipe(params.direction, params.distance)
        return ActionResult(
            success=True, message=f"Scrolled {params.direction} (distance={params.distance})"
        )

    # ── press_key ──────────────────────────────────────────────────────────

    @controller.action("按下按键 (back/home/enter/recent/power 等)", name="press_key")
    async def press_key(
        params: PressKeyAction, device: Device, state: DeviceState, ctrl: Controller
    ) -> ActionResult:
        await device.press_key(params.key_name)
        return ActionResult(success=True, message=f"Pressed key: {params.key_name}")

    # ── back ───────────────────────────────────────────────────────────────

    @controller.action("按返回键", name="back")
    async def back(params: BackAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
        await device.press_back()
        return ActionResult(success=True, message="Pressed back")

    # ── home ───────────────────────────────────────────────────────────────

    @controller.action("按 Home 键回到桌面", name="home")
    async def home(params: HomeAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
        await device.press_home()
        return ActionResult(success=True, message="Pressed home")

    # ── launch_app ─────────────────────────────────────────────────────────

    @controller.action("启动应用", name="launch_app")
    async def launch_app(
        params: LaunchAppAction, device: Device, state: DeviceState, ctrl: Controller
    ) -> ActionResult:
        await device.app_start(params.package_name, params.activity)
        return ActionResult(success=True, message=f"Launched app: {params.package_name}")

    # ── stop_app ───────────────────────────────────────────────────────────

    @controller.action("停止应用", name="stop_app")
    async def stop_app(
        params: StopAppAction, device: Device, state: DeviceState, ctrl: Controller
    ) -> ActionResult:
        await device.app_stop(params.package_name)
        return ActionResult(success=True, message=f"Stopped app: {params.package_name}")

    # ── wait ───────────────────────────────────────────────────────────────

    @controller.action("等待指定秒数", name="wait")
    async def wait(params: WaitAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
        await asyncio.sleep(params.seconds)
        return ActionResult(success=True, message=f"Waited {params.seconds}s")

    # ── screenshot ─────────────────────────────────────────────────────────

    @controller.action("截图并返回（用于调试/确认）", name="screenshot")
    async def screenshot(
        params: ActionModel, device: Device, state: DeviceState, ctrl: Controller
    ) -> ActionResult:
        png = await device.screenshot()
        return ActionResult(
            success=True,
            message=f"Screenshot captured ({len(png)} bytes)",
            data={"screenshot_size": len(png)},
        )

    # ── get_ui_hierarchy ───────────────────────────────────────────────────

    @controller.action("获取当前 UI 元素树（调试用）", name="get_ui_hierarchy")
    async def get_ui_hierarchy(
        params: ActionModel, device: Device, state: DeviceState, ctrl: Controller
    ) -> ActionResult:
        root = state.ui_hierarchy
        llm_text = root.to_llm_text()
        if not llm_text:
            llm_text = root.to_debug_text() or "(空 UI 树)"
        return ActionResult(
            success=True,
            message=f"UI hierarchy:\n{llm_text}",
            data={"ui_text": llm_text},
        )

    # ── done ───────────────────────────────────────────────────────────────

    @controller.action("任务完成，返回结果", name="done")
    async def done(params: DoneAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
        return ActionResult(
            success=True,
            message=f"Task completed: {params.answer}",
            data={"final_answer": params.answer},
        )

    # ── error ──────────────────────────────────────────────────────────────

    @controller.action("报告错误，表示当前步骤无法继续", name="error")
    async def error(params: ErrorAction, device: Device, state: DeviceState, ctrl: Controller) -> ActionResult:
        return ActionResult(success=False, message=f"Error reported: {params.message}")


def _find_element_by_idx(state: DeviceState, idx: int):
    """在 UIElement 树中按 idx 查找元素"""

    def _walk(elem):
        if elem.idx == idx:
            return elem
        for child in elem.children:
            result = _walk(child)
            if result is not None:
                return result
        return None

    return _walk(state.ui_hierarchy)

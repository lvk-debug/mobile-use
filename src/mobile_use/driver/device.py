from __future__ import annotations

import asyncio
import io
from typing import TYPE_CHECKING

import uiautomator2 as u2
from loguru import logger
from PIL import Image
from pydantic import BaseModel

from mobile_use.driver.connection import ConnectionConfig

if TYPE_CHECKING:
    from mobile_use.state.device_state import DeviceState
    from mobile_use.state.ui_hierarchy import UIElement

__all__ = ["Device", "DeviceInfo", "AppInfo"]


# ── 数据模型 ────────────────────────────────────────────────────────────


class DeviceInfo(BaseModel):
    """设备基本信息"""

    serial: str
    brand: str = ""
    model: str = ""
    sdk_version: int = 0
    android_version: str = ""
    screen_width: int = 0
    screen_height: int = 0


class AppInfo(BaseModel):
    """当前前台应用信息"""

    package: str = ""
    activity: str = ""


# ── Device ──────────────────────────────────────────────────────────────


class Device:
    """单台 Android 设备的统一操作接口

    将 uiautomator2 的同步 API 封装为异步接口，
    所有阻塞操作通过 asyncio.to_thread 在线程池中执行。
    """

    def __init__(
        self,
        u2_device: u2.Device,
        config: ConnectionConfig,
    ) -> None:
        self._u2: u2.Device = u2_device
        self._config = config

    # ── 属性 ────────────────────────────────────────────────────────────

    @property
    def serial(self) -> str:
        return self._config.serial

    @property
    def config(self) -> ConnectionConfig:
        return self._config

    @property
    def raw(self) -> u2.Device:
        """底层 u2.Device，用于高级操作或调试"""
        return self._u2

    # ── 设备信息 ────────────────────────────────────────────────────────

    async def info(self) -> DeviceInfo:
        """获取设备基本信息"""
        # device_info 是属性（dict），不是方法
        info = self._u2.device_info
        size = self._u2.window_size()  # window_size 是方法
        return DeviceInfo(
            serial=self.serial,
            brand=info.get("brand", ""),
            model=info.get("model", ""),
            sdk_version=info.get("sdkInt", info.get("sdk", 0)),
            android_version=str(info.get("version", "")),
            screen_width=size[0],
            screen_height=size[1],
        )

    async def current_app(self) -> AppInfo:
        """获取当前前台应用信息"""
        # app_current 是方法，返回 dict
        app = self._u2.app_current()
        return AppInfo(
            package=app.get("package", ""),
            activity=app.get("activity", ""),
        )

    async def window_size(self) -> tuple[int, int]:
        """获取屏幕分辨率 (width, height)"""
        return await asyncio.to_thread(self._u2.window_size)

    # ── 基础交互 ────────────────────────────────────────────────────────

    async def tap(self, x: int, y: int) -> None:
        """点击屏幕坐标"""
        logger.debug("Tap: ({}, {})", x, y)
        await asyncio.to_thread(self._u2.click, x, y)

    async def long_press(self, x: int, y: int, duration: float = 0.5) -> None:
        """长按屏幕坐标"""
        logger.debug("Long press: ({}, {}) for {}s", x, y, duration)
        await asyncio.to_thread(self._u2.long_click, x, y, duration)

    async def double_tap(self, x: int, y: int) -> None:
        """双击屏幕坐标"""
        logger.debug("Double tap: ({}, {})", x, y)
        await asyncio.to_thread(self._u2.double_click, x, y)

    async def swipe(self, direction: str, distance: float = 0.5) -> None:
        """按方向滑动

        Args:
            direction: "up" | "down" | "left" | "right"
            distance: 滑动距离比例 (0~1)
        """
        logger.debug("Swipe: direction={}, distance={}", direction, distance)
        await asyncio.to_thread(self._u2.swipe_ext, direction, scale=distance)

    async def swipe_coords(
        self,
        sx: int,
        sy: int,
        ex: int,
        ey: int,
        duration: float = 0.5,
    ) -> None:
        """按坐标滑动"""
        logger.debug("Swipe coords: ({},{}) -> ({},{})", sx, sy, ex, ey)
        await asyncio.to_thread(self._u2.swipe, sx, sy, ex, ey, duration)

    async def drag(self, sx: int, sy: int, ex: int, ey: int) -> None:
        """拖拽"""
        logger.debug("Drag: ({},{}) -> ({},{})", sx, sy, ex, ey)
        await asyncio.to_thread(self._u2.drag, sx, sy, ex, ey)

    # ── 文本输入 ────────────────────────────────────────────────────────

    async def input_text(self, text: str) -> None:
        """向当前焦点输入框输入文字"""
        logger.debug("Input text: {!r}", text)
        await asyncio.to_thread(self._u2.send_keys, text)

    async def clear_text(self) -> None:
        """清空当前焦点输入框"""
        logger.debug("Clear text")
        await asyncio.to_thread(self._u2.clear_text)

    # ── 按键 ────────────────────────────────────────────────────────────

    async def press_key(self, key: str) -> None:
        """按下按键

        Args:
            key: "back" | "home" | "enter" | "recent" | "power" | ...
        """
        logger.debug("Press key: {}", key)
        await asyncio.to_thread(self._u2.press, key)

    async def press_back(self) -> None:
        """按返回键"""
        await self.press_key("back")

    async def press_home(self) -> None:
        """按 Home 键"""
        await self.press_key("home")

    # ── 应用管理 ────────────────────────────────────────────────────────

    async def app_start(
        self,
        package: str,
        activity: str | None = None,
    ) -> None:
        """启动应用"""
        logger.debug("App start: {} / {}", package, activity or "(default)")
        if activity:
            await asyncio.to_thread(self._u2.app_start, package, activity)
        else:
            await asyncio.to_thread(self._u2.app_start, package)

    async def app_stop(self, package: str) -> None:
        """停止应用"""
        logger.debug("App stop: {}", package)
        await asyncio.to_thread(self._u2.app_stop, package)

    async def app_install(self, apk_path: str) -> None:
        """安装 APK"""
        logger.debug("App install: {}", apk_path)
        await asyncio.to_thread(self._u2.app_install, apk_path)

    async def app_uninstall(self, package: str) -> None:
        """卸载应用"""
        logger.debug("App uninstall: {}", package)
        await asyncio.to_thread(self._u2.app_uninstall, package)

    async def app_list(self) -> list[str]:
        """列出已安装应用包名"""
        return await asyncio.to_thread(self._u2.app_list)

    # ── 状态采集 ────────────────────────────────────────────────────────

    async def screenshot(self) -> bytes:
        """截取屏幕，返回 PNG bytes"""
        logger.debug("Screenshot")
        img: Image.Image = await asyncio.to_thread(self._u2.screenshot)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    async def get_ui_hierarchy(self, max_retries: int = 3, retry_delay: float = 0.5) -> tuple[UIElement, str]:
        """获取 UI 层级树，返回 (UIElement 根节点, 原始 XML)

        dump_hierarchy() 偶尔会返回空层级（如界面正在切换时），此时自动重试。

        Args:
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        """
        from mobile_use.state.parser import parse_ui_hierarchy

        for attempt in range(max_retries + 1):
            logger.debug("Get UI hierarchy (attempt {})", attempt + 1)
            xml: str = await asyncio.to_thread(self._u2.dump_hierarchy)
            result, raw_xml = parse_ui_hierarchy(xml)

            # 空层级：无子节点且无类名，说明 dump_hierarchy() 返回了空内容
            if not result.children and not result.class_name:
                if attempt < max_retries:
                    logger.warning("UI hierarchy is empty, retrying ({}/{})", attempt + 1, max_retries)
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    logger.error("UI hierarchy still empty after {} retries", max_retries)

            # 有层级但无可交互元素，记录诊断信息
            if result.class_name and not result.to_llm_text():
                logger.warning(
                    "UI hierarchy has no interactive elements (clickable/scrollable), "
                    "root={!r}, children_count={}",
                    result.class_name,
                    len(result.children),
                )

            return result, raw_xml

    async def get_state(self, use_vision: bool = True) -> DeviceState:
        """获取设备完整状态（UI 层级 + 截图 + 当前应用 + 屏幕尺寸）

        Args:
            use_vision: 是否采集截图。为 False 时跳过截图以节省时间。
        """
        logger.debug("Get device state (use_vision={})", use_vision)
        from mobile_use.state.device_state import DeviceState

        # 并发采集状态数据，use_vision=False 时跳过截图
        tasks = [
            self.get_ui_hierarchy(),
            self.screenshot() if use_vision else self._empty_screenshot(),
            self.current_app(),
            self.window_size(),
            self.info(),
        ]
        (hierarchy, hierarchy_xml), screenshot_bytes, app_info, (width, height), dev_info = await asyncio.gather(*tasks)
        return DeviceState(
            ui_hierarchy=hierarchy,
            ui_hierarchy_xml=hierarchy_xml,
            screenshot=screenshot_bytes,
            current_app=app_info,
            device_info=dev_info,
            width=width,
            height=height,
        )

    @staticmethod
    async def _empty_screenshot() -> bytes:
        """返回空截图占位"""
        return b""

    # ── 元素定位 ────────────────────────────────────────────────────────

    def _find_in_tree(
        self,
        root: UIElement,
        *,
        first_only: bool = False,
        resource_id: str | None = None,
        text: str | None = None,
        content_desc: str | None = None,
        xpath: str | None = None,
    ) -> list[UIElement]:
        """在 UIElement 树中递归查找匹配的元素

        Args:
            root: 根节点
            first_only: 是否只返回第一个匹配
            resource_id: 按 resource-id 匹配（支持完整 id 或短 id）
            text: 按 text 精确匹配
            content_desc: 按 content-desc 精确匹配
            xpath: 按 xpath 表达式匹配（类名路径，如 ".//TextView"）

        Returns:
            匹配的 UIElement 列表
        """

        results: list[UIElement] = []

        def _match(elem: UIElement) -> bool:
            if resource_id is not None:
                # 支持完整 id 和短 id（/ 后面部分）
                if elem.resource_id != resource_id:
                    short = (
                        elem.resource_id.rsplit("/", 1)[-1]
                        if "/" in elem.resource_id
                        else elem.resource_id
                    )
                    if short != resource_id:
                        return False
            if text is not None and elem.text != text:
                return False
            if content_desc is not None and elem.content_desc != content_desc:
                return False
            if xpath is not None:
                # 简单 xpath 支持：按类名匹配，如 ".//TextView" 或 "TextView"
                target_class = xpath.lstrip("./")
                short_class = (
                    elem.class_name.rsplit(".", 1)[-1]
                    if "." in elem.class_name
                    else elem.class_name
                )
                if short_class != target_class:
                    return False
            return True

        def _walk(elem: UIElement) -> None:
            if first_only and results:
                return
            if _match(elem):
                results.append(elem)
            for child in elem.children:
                _walk(child)

        _walk(root)
        return results

    async def find_element(
        self,
        *,
        resource_id: str | None = None,
        text: str | None = None,
        content_desc: str | None = None,
        xpath: str | None = None,
    ) -> UIElement | None:
        """查找第一个匹配的 UI 元素

        Args:
            resource_id: 按 resource-id 匹配
            text: 按 text 精确匹配
            content_desc: 按 content-desc 精确匹配
            xpath: 按类名 xpath 匹配（如 ".//TextView"）

        Returns:
            匹配的 UIElement，未找到返回 None
        """
        hierarchy, _ = await self.get_ui_hierarchy()
        results = self._find_in_tree(
            hierarchy,
            first_only=True,
            resource_id=resource_id,
            text=text,
            content_desc=content_desc,
            xpath=xpath,
        )
        return results[0] if results else None

    async def find_elements(
        self,
        *,
        resource_id: str | None = None,
        text: str | None = None,
        content_desc: str | None = None,
        xpath: str | None = None,
    ) -> list[UIElement]:
        """查找所有匹配的 UI 元素

        Args:
            resource_id: 按 resource-id 匹配
            text: 按 text 精确匹配
            content_desc: 按 content-desc 精确匹配
            xpath: 按类名 xpath 匹配（如 ".//TextView"）

        Returns:
            匹配的 UIElement 列表
        """
        hierarchy, _ = await self.get_ui_hierarchy()
        return self._find_in_tree(
            hierarchy,
            resource_id=resource_id,
            text=text,
            content_desc=content_desc,
            xpath=xpath,
        )

"""M2 状态模块测试：UIElement、Parser、DeviceState"""

from __future__ import annotations

import pytest

from mobile_use.state.parser import parse_bounds, parse_ui_hierarchy
from mobile_use.state.ui_hierarchy import UIElement
from tests.conftest import SAMPLE_UI_XML


class TestParseBounds:
    """parse_bounds 解析测试"""

    def test_normal(self):
        assert parse_bounds("[0,0][1080,2400]") == (0, 0, 1080, 2400)

    def test_non_zero_origin(self):
        assert parse_bounds("[100,200][980,280]") == (100, 200, 980, 280)

    def test_same_point(self):
        assert parse_bounds("[50,50][50,50]") == (50, 50, 50, 50)

    def test_with_whitespace(self):
        assert parse_bounds("  [0,0][100,100]  ") == (0, 0, 100, 100)

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid bounds format"):
            parse_bounds("invalid")

    def test_partial_format(self):
        with pytest.raises(ValueError, match="Invalid bounds format"):
            parse_bounds("[0,0]")


class TestUIElement:
    """UIElement 模型测试"""

    def test_default_values(self):
        elem = UIElement()
        assert elem.idx == -1
        assert elem.class_name == ""
        assert elem.text == ""
        assert elem.clickable is False
        assert elem.bounds == (0, 0, 0, 0)
        assert elem.children == []

    def test_center(self):
        elem = UIElement(bounds=(100, 200, 300, 400))
        assert elem.center == (200, 300)

    def test_is_interactive_clickable(self):
        elem = UIElement(clickable=True)
        assert elem.is_interactive is True

    def test_is_interactive_scrollable(self):
        elem = UIElement(scrollable=True)
        assert elem.is_interactive is True

    def test_is_interactive_false(self):
        elem = UIElement()
        assert elem.is_interactive is False

    def test_to_llm_text_basic(self):
        elem = UIElement(
            idx=0,
            class_name="android.widget.TextView",
            text="确定",
            resource_id="com.example:id/btn_ok",
            clickable=True,
        )
        text = elem.to_llm_text()
        assert '[0] TextView "确定"' in text
        assert 'id="btn_ok"' in text
        assert "clickable" in text

    def test_to_llm_text_with_content_desc(self):
        elem = UIElement(
            idx=1,
            class_name="android.widget.ImageView",
            content_desc="搜索",
            resource_id="com.example:id/icon",
        )
        text = elem.to_llm_text()
        assert '[1] ImageView' in text
        assert 'desc="搜索"' in text

    def test_to_llm_text_skips_non_interactive(self):
        """非可交互元素（idx=-1）不出现在输出中"""
        root = UIElement(
            idx=-1,
            class_name="android.widget.FrameLayout",
            children=[
                UIElement(idx=0, class_name="TextView", text="Hello", clickable=True),
            ],
        )
        text = root.to_llm_text()
        assert "FrameLayout" not in text
        assert 'TextView "Hello"' in text

    def test_to_llm_text_nested(self):
        """嵌套元素正确缩进"""
        root = UIElement(
            idx=-1,
            children=[
                UIElement(
                    idx=0,
                    class_name="ViewGroup",
                    clickable=True,
                    children=[
                        UIElement(idx=1, class_name="TextView", text="item", clickable=True),
                    ],
                ),
            ],
        )
        text = root.to_llm_text()
        lines = text.split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("[0]")
        assert lines[1].startswith("  [1]")  # 缩进

    def test_to_llm_text_scrollable(self):
        elem = UIElement(idx=2, class_name="ListView", scrollable=True)
        text = elem.to_llm_text()
        assert "scrollable" in text


class TestParseUIHierarchy:
    """parse_ui_hierarchy XML 解析测试"""

    def _parse(self, xml: str) -> UIElement:
        """解析 XML 并返回 UIElement（忽略原始 XML）"""
        root, _ = parse_ui_hierarchy(xml)
        return root

    def test_returns_root_element(self):
        root = self._parse(SAMPLE_UI_XML)
        assert isinstance(root, UIElement)
        assert root.class_name == "android.widget.FrameLayout"

    def test_returns_raw_xml(self):
        """parse_ui_hierarchy 同时返回原始 XML"""
        root, raw_xml = parse_ui_hierarchy(SAMPLE_UI_XML)
        assert isinstance(raw_xml, str)
        assert len(raw_xml) > 0
        assert "hierarchy" in raw_xml

    def test_root_not_interactive(self):
        """根 FrameLayout 不可交互，idx 为 -1"""
        root = self._parse(SAMPLE_UI_XML)
        assert root.idx == -1

    def test_interactive_elements_get_idx(self):
        """可交互元素按顺序分配 idx"""
        root = self._parse(SAMPLE_UI_XML)
        # 收集所有有 idx 的元素
        interactive: list[UIElement] = []

        def collect(elem: UIElement):
            if elem.idx >= 0:
                interactive.append(elem)
            for child in elem.children:
                collect(child)

        collect(root)

        # workspace (scrollable), search_bar (clickable), 设置 (clickable), 相机 (clickable)
        assert len(interactive) == 4
        assert interactive[0].idx == 0  # workspace
        assert interactive[1].idx == 1  # 搜索
        assert interactive[2].idx == 2  # 设置
        assert interactive[3].idx == 3  # 相机

    def test_text_parsed(self):
        root = self._parse(SAMPLE_UI_XML)

        def find_by_text(elem: UIElement, text: str) -> UIElement | None:
            if elem.text == text:
                return elem
            for child in elem.children:
                result = find_by_text(child, text)
                if result:
                    return result
            return None

        search = find_by_text(root, "搜索")
        assert search is not None
        assert search.class_name == "android.widget.TextView"
        assert search.resource_id == "com.android.launcher3:id/search_bar"

    def test_content_desc_parsed(self):
        root = self._parse(SAMPLE_UI_XML)

        def find_by_desc(elem: UIElement, desc: str) -> UIElement | None:
            if elem.content_desc == desc:
                return elem
            for child in elem.children:
                result = find_by_desc(child, desc)
                if result:
                    return result
            return None

        settings = find_by_desc(root, "打开设置")
        assert settings is not None
        assert settings.text == "设置"
        assert settings.bounds == (50, 400, 250, 500)

    def test_bounds_parsed(self):
        root = self._parse(SAMPLE_UI_XML)
        assert root.bounds == (0, 0, 1080, 2400)

    def test_children_count(self):
        root = self._parse(SAMPLE_UI_XML)
        # root -> FrameLayout (1 child)
        assert len(root.children) == 1
        workspace = root.children[0]
        # workspace -> [搜索, icon_grid]
        assert len(workspace.children) == 2

    def test_bool_attrs(self):
        root = self._parse(SAMPLE_UI_XML)
        workspace = root.children[0]
        assert workspace.scrollable is True
        assert workspace.clickable is True
        assert workspace.checkable is False

    def test_new_fields_parsed(self):
        """新增的 long_clickable、index、hint 字段正确解析"""
        root = self._parse(SAMPLE_UI_XML)
        workspace = root.children[0]
        assert workspace.long_clickable is False
        assert workspace.index == 0
        assert workspace.hint == ""

    def test_to_llm_text_from_parsed(self):
        """解析后的树能正确输出 LLM 文本"""
        root = self._parse(SAMPLE_UI_XML)
        text = root.to_llm_text()
        # 应包含所有可交互元素
        assert '搜索' in text
        assert '设置' in text
        assert '相机' in text
        assert 'scrollable' in text

    def test_invalid_xml(self):
        with pytest.raises(Exception):
            parse_ui_hierarchy("<invalid>")

    def test_empty_hierarchy(self):
        xml = '<?xml version="1.0"?><hierarchy rotation="0"></hierarchy>'
        root, raw_xml = parse_ui_hierarchy(xml)
        assert root.idx == -1
        assert root.children == []
        assert raw_xml == xml


class TestDeviceState:
    """DeviceState 模型测试"""

    def test_construction(self):
        from mobile_use.driver.device import AppInfo
        from mobile_use.state.device_state import DeviceState

        root, raw_xml = parse_ui_hierarchy(SAMPLE_UI_XML)
        state = DeviceState(
            ui_hierarchy=root,
            ui_hierarchy_xml=raw_xml,
            screenshot=b"\x89PNG",
            current_app=AppInfo(package="com.test", activity=".Main"),
            width=1080,
            height=2400,
        )
        assert state.width == 1080
        assert state.height == 2400
        assert state.current_app.package == "com.test"
        assert state.screenshot == b"\x89PNG"
        assert isinstance(state.ui_hierarchy, UIElement)
        assert state.ui_hierarchy_xml == raw_xml

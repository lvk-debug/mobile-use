"""UI 层级 XML 解析器

将 uiautomator2 dump_hierarchy() 输出的 XML 解析为结构化的 UIElement 树，
并为可交互元素（clickable / scrollable）分配全局唯一 idx。
"""

from __future__ import annotations

import re

from loguru import logger
from lxml import etree

from mobile_use.state.ui_hierarchy import UIElement

__all__ = ["parse_bounds", "parse_ui_hierarchy"]

# 匹配 [left,top][right,bottom] 格式
_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def parse_bounds(bounds_str: str) -> tuple[int, int, int, int]:
    """解析 bounds 字符串为 (left, top, right, bottom) 元组

    Args:
        bounds_str: 格式为 "[left,top][right,bottom]"，如 "[0,0][1080,2400]"

    Returns:
        (left, top, right, bottom) 四元组

    Raises:
        ValueError: 格式不匹配
    """
    m = _BOUNDS_RE.match(bounds_str.strip())
    if not m:
        raise ValueError(f"Invalid bounds format: {bounds_str!r}")
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)))


def _bool_attr(node: etree._Element, attr: str) -> bool:
    """将 XML 节点属性转为 bool"""
    val = node.get(attr, "false")
    return val.lower() == "true"


def _build_element(
    node: etree._Element,
    counter: list[int],
) -> UIElement:
    """递归构建 UIElement 树

    Args:
        node: lxml Element 节点
        counter: 单元素列表，用于自增 idx 计数 [current_idx]
    """
    clickable = _bool_attr(node, "clickable")
    scrollable = _bool_attr(node, "scrollable")
    is_interactive = clickable or scrollable

    # 仅可交互元素分配 idx
    idx = -1
    if is_interactive:
        idx = counter[0]
        counter[0] += 1

    bounds_str = node.get("bounds", "[0,0][0,0]")
    try:
        bounds = parse_bounds(bounds_str)
    except ValueError:
        logger.warning("Failed to parse bounds: {}", bounds_str)
        bounds = (0, 0, 0, 0)

    resource_id = node.get("resource-id", "")

    # 解析 index 属性
    try:
        node_index = int(node.get("index", "-1"))
    except ValueError:
        node_index = -1

    element = UIElement(
        idx=idx,
        class_name=node.get("class", ""),
        resource_id=resource_id,
        text=node.get("text", ""),
        content_desc=node.get("content-desc", ""),
        package=node.get("package", ""),
        checkable=_bool_attr(node, "checkable"),
        checked=_bool_attr(node, "checked"),
        clickable=clickable,
        long_clickable=_bool_attr(node, "long-clickable"),
        enabled=_bool_attr(node, "enabled"),
        focusable=_bool_attr(node, "focusable"),
        focused=_bool_attr(node, "focused"),
        scrollable=scrollable,
        selected=_bool_attr(node, "selected"),
        index=node_index,
        hint=node.get("hint", ""),
        bounds=bounds,
        children=[],
    )

    # 递归处理子节点
    for child_node in node:
        if child_node.tag == "node":
            child_elem = _build_element(child_node, counter)
            element.children.append(child_elem)

    return element


def _count_xml_nodes(root: etree._Element) -> tuple[int, int, int]:
    """统计 XML 树中的 node 总数、clickable 数、scrollable 数"""
    total = 0
    clickable = 0
    scrollable = 0
    for node in root.iter("node"):
        total += 1
        if node.get("clickable", "false").lower() == "true":
            clickable += 1
        if node.get("scrollable", "false").lower() == "true":
            scrollable += 1
    return total, clickable, scrollable


def _sample_interactive_nodes(root: etree._Element, limit: int = 3) -> list[str]:
    """采样 XML 中的 clickable/scrollable 节点，返回诊断文本"""
    samples = []
    for node in root.iter("node"):
        if node.get("clickable", "false").lower() == "true" or node.get("scrollable", "false").lower() == "true":
            # 收集从 root 到该节点的路径
            path = []
            for ancestor in node.iterancestors():
                path.append(ancestor.tag)
            path.reverse()
            path.append(node.tag)

            attrs = dict(node.attrib)
            samples.append(f"  path={'/'.join(path)}, tag={node.tag}, attrs={attrs}")
            if len(samples) >= limit:
                break
    return samples


def parse_ui_hierarchy(xml_str: str) -> tuple[UIElement, str]:
    """将 uiautomator2 dump_hierarchy() 输出的 XML 解析为 UIElement 树

    uiautomator2 输出的 XML 以 <hierarchy> 为根节点，其下通常只有一个 <node> 子节点。
    本函数跳过 <hierarchy> 包装，返回其下 <node> 子树对应的 UIElement。
    若 <hierarchy> 下有多个 <node> 子节点，合并为一个虚拟根节点。

    Args:
        xml_str: 原始 XML 字符串

    Returns:
        (UIElement 根节点, 原始 XML 字符串) 元组

    Raises:
        etree.XMLSyntaxError: XML 格式错误
    """
    if not xml_str or not xml_str.strip():
        logger.warning("parse_ui_hierarchy: received empty xml_str")
        return UIElement(), xml_str or ""

    root = etree.fromstring(xml_str.encode("utf-8"))
    counter = [0]  # 全局 idx 计数器

    # 跳过 <hierarchy> 包装层，处理其下所有 <node> 子节点
    if root.tag == "hierarchy":
        node_children = [child for child in root if child.tag == "node"]

        if not node_children:
            child_tags = [child.tag for child in root]
            logger.warning(
                "parse_ui_hierarchy: <hierarchy> has no <node> children, "
                "root.tag={}, child_tags={}, xml_len={}",
                root.tag,
                child_tags,
                len(xml_str),
            )
            return UIElement(), xml_str

        # 通常只有一个 <node> 子节点；若有多个，合并为一个虚拟根节点
        if len(node_children) == 1:
            result = _build_element(node_children[0], counter)
        else:
            logger.debug("parse_ui_hierarchy: <hierarchy> has {} <node> children, merging", len(node_children))
            result = UIElement(class_name="hierarchy", children=[])
            for nc in node_children:
                child_elem = _build_element(nc, counter)
                result.children.append(child_elem)

        # 解析完成但无可交互元素时，记录 XML 层面的诊断信息
        if counter[0] == 0:
            total, clickable, scrollable = _count_xml_nodes(root)
            samples = _sample_interactive_nodes(root)
            logger.warning(
                "parse_ui_hierarchy: no interactive elements in result, "
                "xml_nodes={}, xml_clickable={}, xml_scrollable={}, xml_len={}, "
                "hierarchy_node_children={}\nsample interactive nodes:\n{}",
                total,
                clickable,
                scrollable,
                len(xml_str),
                len(node_children),
                "\n".join(samples) if samples else "  (none found by iter)",
            )

        return result, xml_str

    # 非 <hierarchy> 根节点，直接解析
    logger.debug("parse_ui_hierarchy: root tag is {!r}, not 'hierarchy', parsing directly", root.tag)
    return _build_element(root, counter), xml_str

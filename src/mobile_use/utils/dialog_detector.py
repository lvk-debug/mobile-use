"""弹窗检测工具 — 权限弹窗 / 登录弹窗等需要人工介入的场景"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mobile_use.state.ui_hierarchy import UIElement

# ── 权限弹窗 ──────────────────────────────────────────────────────────
_PERMISSION_KEYWORDS = [
    "允许", "禁止", "拒绝",
    "想使用", "请求权限", "权限",
    "定位", "相机", "麦克风", "存储", "通讯录", "电话",
    "Allow", "Deny", "Permission", "Location", "Camera",
]
_ALLOW_BUTTON_TEXTS = ["允许", "Allow", "始终允许", "仅在使用中允许", "仅在使用该应用时允许"]
_DENY_BUTTON_TEXTS = ["禁止", "拒绝", "Deny", "不允许"]

# ── 登录弹窗 ──────────────────────────────────────────────────────────
_LOGIN_KEYWORDS = [
    "登录", "登陆", "签到",
    "请登录", "请先登录", "立即登录",
    "账号", "用户名", "手机号", "邮箱",
    "密码", "验证码", "短信验证",
    "一键登录", "快速登录",
    "微信登录", "QQ登录", "支付宝登录", "Apple登录",
    "Login", "Sign in", "Log in",
    "账号密码登录", "手机号登录",
]
_LOGIN_BUTTON_TEXTS = [
    "登录", "登陆", "立即登录", "确认登录",
    "一键登录", "快速登录", "手机号登录",
    "Login", "Sign in", "Log in",
    "发送验证码", "获取验证码",
]


def detect_permission_dialog(root: UIElement) -> str | None:
    """检测是否存在权限弹窗"""
    return _detect_dialog(root, _PERMISSION_KEYWORDS, _ALLOW_BUTTON_TEXTS + _DENY_BUTTON_TEXTS)


def detect_login_dialog(root: UIElement) -> str | None:
    """检测是否存在登录弹窗/登录页面"""
    return _detect_dialog(root, _LOGIN_KEYWORDS, _LOGIN_BUTTON_TEXTS)


def detect人工介入弹窗(root: UIElement) -> str | None:
    """检测所有需要人工介入的弹窗（权限/登录等）

    Returns:
        弹窗描述文本，未检测到返回 None
    """
    result = detect_permission_dialog(root)
    if result:
        return result
    result = detect_login_dialog(root)
    return result


# ── 内部实现 ──────────────────────────────────────────────────────────

def _detect_dialog(root: UIElement, keywords: list[str], button_texts: list[str]) -> str | None:
    """通用弹窗检测

    判断条件：同时存在关键词描述文本和按钮文本
    """
    found_texts: list[str] = []
    found_buttons: list[str] = []

    def _walk(elem: UIElement) -> None:
        text = (elem.text or "").strip()
        desc = (elem.content_desc or "").strip()

        for kw in keywords:
            if kw in text or kw in desc:
                if text and text not in found_texts:
                    found_texts.append(text)
                break

        for btn in button_texts:
            if text == btn:
                found_buttons.append(text)
                break

        for child in elem.children:
            _walk(child)

    _walk(root)

    if found_texts and found_buttons:
        descriptions = [t for t in found_texts if t not in button_texts]
        if descriptions:
            return descriptions[0]
        return found_texts[0]

    return None

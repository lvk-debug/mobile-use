"""图片处理工具函数"""

from __future__ import annotations

import base64
import io

from PIL import Image

from mobile_use.utils.logger import logger

# 默认最大边长（像素），超过则等比缩放
_DEFAULT_MAX_SIDE = 1280
# 默认 JPEG 压缩质量
_DEFAULT_QUALITY = 80


def compress_screenshot(
    png_bytes: bytes,
    max_side: int = _DEFAULT_MAX_SIDE,
    quality: int = _DEFAULT_QUALITY,
) -> bytes:
    """压缩截图：先缩放到 max_side 以内，再转为 JPEG 压缩

    Args:
        png_bytes: 原始 PNG 截图字节
        max_side: 最大边长（宽或高），超过则等比缩放
        quality: JPEG 压缩质量 1-100

    Returns:
        压缩后的 JPEG 字节
    """
    if not png_bytes:
        return png_bytes

    img = Image.open(io.BytesIO(png_bytes))

    # 等比缩放
    w, h = img.size
    if max(w, h) > max_side:
        ratio = max_side / max(w, h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        logger.debug("Screenshot resized: {}x{} -> {}x{}", w, h, new_w, new_h)

    # 转 JPEG
    buf = io.BytesIO()
    # RGBA 模式需要先转 RGB
    if img.mode == "RGBA":
        img = img.convert("RGB")
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    result = buf.getvalue()

    logger.debug(
        "Screenshot compressed: {} -> {} bytes ({:.0f}%)",
        len(png_bytes),
        result,
        len(result) / len(png_bytes) * 100 if png_bytes else 0,
    )
    return result


def to_base64_data_url(image_bytes: bytes, fmt: str = "jpeg") -> str:
    """将图片字节编码为 base64 data URL，供 LLM 多模态消息使用

    Args:
        image_bytes: 图片字节
        fmt: 图片格式（jpeg / png）

    Returns:
        data:image/{fmt};base64,... 格式的字符串
    """
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/{fmt};base64,{b64}"

"""图片工具函数测试"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from mobile_use.utils.image import compress_screenshot, to_base64_data_url


def _make_png(width: int = 1920, height: int = 1080) -> bytes:
    """生成测试用 PNG 图片字节"""
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestCompressScreenshot:
    def test_empty_bytes(self):
        assert compress_screenshot(b"") == b""

    def test_resize_large_image(self):
        """超过 max_side 的图片应被缩放"""
        png = _make_png(2400, 1080)
        result = compress_screenshot(png, max_side=1280)
        img = Image.open(io.BytesIO(result))
        # 宽度应被缩到 1280，高度等比
        assert img.size[0] == 1280
        assert img.size[1] == 576  # 1280 * 1080/2400

    def test_no_resize_small_image(self):
        """未超过 max_side 的图片不缩放"""
        png = _make_png(800, 600)
        result = compress_screenshot(png, max_side=1280)
        img = Image.open(io.BytesIO(result))
        assert img.size == (800, 600)

    def test_output_is_jpeg(self):
        """输出应为 JPEG 格式"""
        png = _make_png(100, 100)
        result = compress_screenshot(png)
        # JPEG 文件头: FF D8
        assert result[:2] == b"\xff\xd8"

    def test_rgba_conversion(self):
        """RGBA 图片应被转为 RGB"""
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        rgba_png = buf.getvalue()

        result = compress_screenshot(rgba_png)
        # 不应报错，且输出为 JPEG
        assert result[:2] == b"\xff\xd8"

    def test_compressed_smaller_than_original(self):
        """压缩后应比原始 PNG 小"""
        png = _make_png(1920, 1080)
        result = compress_screenshot(png)
        assert len(result) < len(png)


class TestToBase64DataUrl:
    def test_jpeg_format(self):
        data = b"\xff\xd8\xff\xe0" + b"\x00" * 10
        url = to_base64_data_url(data, fmt="jpeg")
        assert url.startswith("data:image/jpeg;base64,")

    def test_png_format(self):
        data = b"\x89PNG" + b"\x00" * 10
        url = to_base64_data_url(data, fmt="png")
        assert url.startswith("data:image/png;base64,")

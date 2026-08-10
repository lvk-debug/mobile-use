"""查找并点击动作"""

from __future__ import annotations

from mobile_use.action.base import ActionModel

__all__ = ["FindAndTapAction"]


class FindAndTapAction(ActionModel):
    """通过文本或属性查找元素并点击，找不到时自动滚动重试

    至少指定 text / resource_id / content_desc 之一作为查找条件。
    """

    text: str | None = None
    resource_id: str | None = None
    content_desc: str | None = None
    max_scrolls: int = 5  # 找不到时最多滚动次数

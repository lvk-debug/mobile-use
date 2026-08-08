"""动作模型基类与执行结果"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = ["ActionModel", "ActionResult"]


class ActionModel(BaseModel):
    """所有动作参数模型的基类"""

    model_config = ConfigDict(extra="forbid")


class ActionResult(BaseModel):
    """动作执行结果"""

    success: bool = True
    message: str = ""
    data: dict | None = None

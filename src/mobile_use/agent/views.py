"""Agent 相关数据模型"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from mobile_use.action.base import ActionResult
    from mobile_use.state.device_state import DeviceState

__all__ = ["AgentConfig", "AgentResult", "AgentStep", "Task"]


class Task(BaseModel):
    """一个可执行的任务单元"""

    id: str = Field(default_factory=lambda: uuid4().hex[:8], description="任务唯一标识")
    name: str = Field(description="任务简短名称")
    description: str = Field(description="任务详细描述，发送给 LLM 的自然语言指令")


class AgentConfig(BaseModel):
    """Agent 配置"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    tasks: list[Task] = Field(default_factory=list, description="任务列表")
    max_steps: int = Field(default=30, description="每个任务的最大执行步数")
    max_errors: int = Field(default=3, description="连续错误容忍次数")
    max_repeated_actions: int = Field(
        default=3, description="相同动作连续重复次数上限，达到后强制停止任务"
    )
    use_vision: bool = Field(default=True, description="是否使用截图（多模态）")
    include_xml: bool = Field(default=False, description="是否在提示词中附带 UI 层级原始 XML")
    system_prompt: str | None = Field(
        default=None, description="自定义 system prompt（为空则用默认模板）"
    )
    log_file: str | None = Field(
        default=None,
        description="日志目录或文件路径。目录则自动生成唯一文件名；文件则直接用；None 不写日志",
    )
    on_permission_dialog: Callable[[str], None] | None = Field(
        default=None,
        description="弹窗通知回调（权限/登录等需要人工介入的场景）。参数为弹窗提示文本，回调应阻塞等待用户手动处理后返回",
    )


class AgentStep(BaseModel):
    """单步执行记录"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_number: int
    state: DeviceState | None = None
    action_name: str = ""
    action_params: dict[str, Any] = Field(default_factory=dict)
    result: ActionResult | None = None
    llm_response: str = ""
    thinking: str = ""
    timestamp: float = Field(default_factory=time.time)


class AgentResult(BaseModel):
    """Agent 执行结果"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task: str
    success: bool = False
    steps: list[AgentStep] = Field(default_factory=list)
    final_answer: str | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    duration: float = 0.0
    error: str | None = None


# ── 解析前向引用 ──────────────────────────────────────────────────────
# DeviceState 和 ActionResult 在 TYPE_CHECKING 中导入（避免循环依赖），
# 但 Pydantic 在运行时需要它们来构建模型。
# 延迟导入 + model_rebuild() 让 Pydantic 解析这些前向引用。


def _rebuild_models() -> None:
    from mobile_use.action.base import ActionResult  # noqa: F811
    from mobile_use.state.device_state import DeviceState  # noqa: F811

    AgentStep.model_rebuild(
        _types_namespace={
            "DeviceState": DeviceState,
            "ActionResult": ActionResult,
        }
    )
    AgentResult.model_rebuild()


_rebuild_models()

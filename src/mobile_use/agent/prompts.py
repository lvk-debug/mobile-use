"""Agent Prompt 构建"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

if TYPE_CHECKING:
    from mobile_use.agent.views import AgentStep
    from mobile_use.state.device_state import DeviceState

__all__ = ["SYSTEM_PROMPT_TEMPLATE", "build_prompt"]

SYSTEM_PROMPT_TEMPLATE = """\
你是 mobile-use Agent，一个通过自然语言操控 Android 手机的 AI 助手。

## 你的能力
你可以操控 Android 手机完成各种任务，包括但不限于：
- 打开/关闭应用
- 点击、滑动、输入文字
- 读取屏幕内容
- 截图确认操作结果
- 遇到权限弹窗或登录弹窗时，系统会暂停并提示用户手动处理，无需你操作

## 当前设备状态
屏幕尺寸: {screen_width} x {screen_height}
当前应用: {current_app}

### UI 元素树
可交互元素带 [N] 编号，非交互但有文本的元素（标签、标题等）无编号，仅作上下文参考。
{ui_elements}

{ui_hierarchy_xml_section}

## 可用的动作
{available_actions}

## 输出格式
请严格以 JSON 格式输出你的决策：
```json
{{
  "thinking": "你的推理过程：分析当前屏幕状态，确定下一步操作",
  "action": [
    {{"action_name": "动作名", "params": {{...}}}}
  ]
}}
```

## 规则
1. 每一步必须输出至少一个 action，不允许空 action 列表
2. 每一步只做一个或少量动作
3. 通过元素索引 [N] 引用可交互 UI 元素，使用 tap 的 element_index 参数
4. 无编号的元素（如标签、标题）仅作上下文参考，不可点击
5. 如果不确定元素位置，先获取 UI 树或截图
6. 如果任务已完成，使用 done 动作并附上 answer
7. 如果任务无法完成，使用 done 动作并说明原因
8. 避免无效重复操作

## 策略
- 在设置（Settings）等列表较长的应用中查找功能时，优先使用页面顶部的搜索框输入关键词定位，而非反复滚动浏览
- 操作顺序：点击搜索框 → 输入目标功能关键词 → 从搜索结果中点击对应项
- 需要滚动浏览列表时，使用 scroll 动作，distance=2.0 表示滚动一整屏，distance=1.0 表示半屏
"""

# XML 在 prompt 中的最大字符数，超出则截断
_XML_MAX_CHARS = 8000


def build_prompt(
    task: str,
    state: DeviceState,
    history: list[AgentStep],
    action_descriptions: str,
    use_vision: bool = True,
    custom_system_prompt: str | None = None,
) -> list:
    """构建发送给 LLM 的消息列表

    Args:
        task: 自然语言任务描述
        state: 当前设备状态
        history: 历史步骤记录
        action_descriptions: 可用动作描述文本
        use_vision: 是否附加截图
        custom_system_prompt: 自定义 system prompt（为空则用默认模板）

    Returns:
        LangChain 消息列表
    """
    messages: list = []

    # ── System Message ─────────────────────────────────────────────────
    system_text = custom_system_prompt or SYSTEM_PROMPT_TEMPLATE

    # 构造 XML 补充信息段
    xml_section = ""
    if state.ui_hierarchy_xml:
        xml = state.ui_hierarchy_xml
        if len(xml) > _XML_MAX_CHARS:
            xml = (
                xml[:_XML_MAX_CHARS]
                + f"\n... (truncated, total {len(state.ui_hierarchy_xml)} chars)"
            )
        xml_section = f"### UI 层级原始 XML\n```xml\n{xml}\n```"

    system_text = system_text.format(
        screen_width=state.width,
        screen_height=state.height,
        current_app=f"{state.current_app.package}/{state.current_app.activity}",
        ui_elements=state.ui_hierarchy.to_llm_text(),
        ui_hierarchy_xml_section=xml_section,
        available_actions=action_descriptions,
    )
    messages.append(SystemMessage(content=system_text))

    # ── Task ───────────────────────────────────────────────────────────
    task_content: list = [{"type": "text", "text": f"## 任务\n{task}"}]
    messages.append(HumanMessage(content=task_content))

    # ── History ────────────────────────────────────────────────────────
    for step in history:
        # Human: 设备状态文本
        state_text = f"## 步骤 {step.step_number} 的设备状态\n"
        if step.state:
            state_text += step.state.ui_hierarchy.to_llm_text()
        messages.append(HumanMessage(content=state_text))

        # AI: 动作决策
        ai_text = step.llm_response
        messages.append(AIMessage(content=ai_text))

    # ── Current State ──────────────────────────────────────────────────
    current_content: list = []
    current_content.append(
        {
            "type": "text",
            "text": f"## 当前设备状态\n{state.ui_hierarchy.to_llm_text()}",
        }
    )
    if use_vision and state.screenshot:
        b64 = base64.b64encode(state.screenshot).decode("utf-8")
        current_content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    messages.append(HumanMessage(content=current_content))

    return messages

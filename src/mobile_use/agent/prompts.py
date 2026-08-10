"""Agent Prompt 构建"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from mobile_use.utils.image import compress_screenshot, to_base64_data_url

if TYPE_CHECKING:
    from mobile_use.agent.views import AgentStep, Task
    from mobile_use.state.device_state import DeviceState

__all__ = ["SYSTEM_PROMPT_TEMPLATE", "SYSTEM_PROMPT_VISION_SUFFIX", "build_prompt"]

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
设备: {device_brand} {device_model} (Android {android_version}, SDK {sdk_version})
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
- 查找页面上某个文本/元素时，优先使用 find_and_tap 动作（按文本自动查找+滚动），避免反复手动 scroll+tap
- 如果 find_and_tap 找不到，再尝试搜索框：点击搜索框 → 输入关键词 → 从结果中点击
- 需要滚动浏览列表时，使用 scroll 动作，distance=2.0 表示滚动一整屏，distance=1.0 表示半屏
"""

# 当 use_vision=True 时追加的视觉引导段
SYSTEM_PROMPT_VISION_SUFFIX = """

## 截图分析
你同时会收到当前屏幕的截图。请结合截图和 UI 元素树进行分析：
- 截图用于理解屏幕整体布局、视觉位置和文本内容
- UI 元素树用于精确获取可交互元素的索引 [N]、控件类型和属性
- 如果 UI 树信息不够清晰，以截图内容为准来判断当前界面状态
- 如果截图中的文字或图标与 UI 树不一致，以截图为准
"""

# XML 在 prompt 中的最大字符数，超出则截断
_XML_MAX_CHARS = 8000


def build_prompt(
    task: Task,
    state: DeviceState,
    history: list[AgentStep],
    action_descriptions: str,
    use_vision: bool = True,
    include_xml: bool = False,
    custom_system_prompt: str | None = None,
) -> list:
    """构建发送给 LLM 的消息列表

    Args:
        task: 任务对象（包含 id/name/description）
        state: 当前设备状态
        history: 历史步骤记录
        action_descriptions: 可用动作描述文本
        use_vision: 是否附加截图
        include_xml: 是否附带 UI 层级原始 XML
        custom_system_prompt: 自定义 system prompt（为空则用默认模板）

    Returns:
        LangChain 消息列表
    """
    messages: list = []

    # ── System Message ─────────────────────────────────────────────────
    system_text = custom_system_prompt or SYSTEM_PROMPT_TEMPLATE

    # 视觉模式下追加截图分析引导
    if use_vision:
        system_text += SYSTEM_PROMPT_VISION_SUFFIX

    # 构造 XML 补充信息段
    xml_section = ""
    if include_xml and state.ui_hierarchy_xml:
        xml = state.ui_hierarchy_xml
        if len(xml) > _XML_MAX_CHARS:
            xml = (
                xml[:_XML_MAX_CHARS]
                + f"\n... (truncated, total {len(state.ui_hierarchy_xml)} chars)"
            )
        xml_section = f"### UI 层级原始 XML\n```xml\n{xml}\n```"

    system_text = system_text.format(
        device_brand=state.device_info.brand or "Unknown",
        device_model=state.device_info.model or "Unknown",
        android_version=state.device_info.android_version or "Unknown",
        sdk_version=state.device_info.sdk_version or "Unknown",
        screen_width=state.width,
        screen_height=state.height,
        current_app=f"{state.current_app.package}/{state.current_app.activity}",
        ui_elements=state.ui_hierarchy.to_llm_text(),
        ui_hierarchy_xml_section=xml_section,
        available_actions=action_descriptions,
    )
    messages.append(SystemMessage(content=system_text))

    # ── Task ───────────────────────────────────────────────────────────
    task_content: list = [{"type": "text", "text": f"## 任务\n{task.description}"}]
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
        # 压缩截图后再编码，减少 token 消耗
        compressed = compress_screenshot(state.screenshot)
        current_content.append(
            {
                "type": "image_url",
                "image_url": {"url": to_base64_data_url(compressed, fmt="jpeg")},
            }
        )
    messages.append(HumanMessage(content=current_content))

    return messages

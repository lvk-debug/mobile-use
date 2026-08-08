"""自定义动作示例 — 向 Controller 注册业务专属动作

使用方法:
    python examples/sdk_custom_action.py [serial]

展示如何：
    1. 创建自定义 Controller
    2. 用 @controller.action 装饰器注册自定义动作
    3. 将自定义 Controller 注入 Agent

自定义动作示例：发送微信消息（伪代码，需根据实际 UI 调整）
"""

import asyncio
import os
import sys

from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from mobile_use import (
    Agent,
    AgentConfig,
    ConnectionConfig,
    ConnectionManager,
    Controller,
)
from mobile_use.action.base import ActionModel, ActionResult


# ── 定义自定义动作参数模型 ────────────────────────────────────────────


class SendWechatMessage(ActionModel):
    """发送微信消息的参数"""

    contact: str  # 联系人名称
    message: str  # 消息内容


class ReadNotifications(ActionModel):
    """读取通知栏消息的参数"""

    max_count: int = 5  # 最多读取条数


# ── 创建自定义 Controller ────────────────────────────────────────────


def create_custom_controller() -> Controller:
    """创建带自定义动作的 Controller"""
    ctrl = Controller()  # 默认动作会自动注册

    @ctrl.action("打开微信并发送消息给指定联系人", name="send_wechat_message")
    async def send_wechat_message(
        params: SendWechatMessage, device, state, controller
    ) -> ActionResult:
        """自定义动作：发送微信消息

        实际实现需要根据具体 UI 调整，这里展示的是框架用法。
        """
        # 示例逻辑（伪代码）：
        # 1. 启动微信
        await device.app_start("com.tencent.mm")
        # 2. 等待加载
        await asyncio.sleep(2)
        # 3. 搜索联系人（实际需根据 UI 元素定位）
        # 4. 输入消息并发送
        return ActionResult(
            success=True,
            message=f"已向 {params.contact} 发送消息: {params.message}",
        )

    @ctrl.action("读取通知栏消息", name="read_notifications")
    async def read_notifications(
        params: ReadNotifications, device, state, controller
    ) -> ActionResult:
        """自定义动作：下拉通知栏并读取消息"""
        # 下拉通知栏
        await device.swipe("down", distance=0.8)
        await asyncio.sleep(1)
        # 获取 UI 树分析通知内容
        new_state = await device.get_state()
        elements = new_state.ui_hierarchy.to_llm_text()
        return ActionResult(
            success=True,
            message=f"通知栏内容:\n{elements}",
            data={"ui_text": elements},
        )

    return ctrl


# ── 主流程 ────────────────────────────────────────────────────────────


async def main(serial: str | None = None) -> None:
    load_dotenv(".env")
    manager = ConnectionManager()
    devices = await manager.list_devices()
    print(f"已连接设备: {devices}")

    if not devices:
        print("[FAIL] 未发现设备")
        return

    serial = serial or devices[0]
    config = ConnectionConfig(serial=serial, connect_type="usb")
    device = await manager.connect(config)
    print(f"[OK] 已连接: {device.serial}")

    try:
        # 创建自定义 controller
        controller = create_custom_controller()

        # 打印所有已注册动作
        print("\n已注册动作:")
        for info in controller.list_actions():
            print(f"  - {info.name}: {info.description}")

        # 创建 LLM
        model_id = os.getenv("OPEN_LLM_MODEL_ID")
        if not model_id:
            print("[FAIL] 请设置环境变量 OPEN_LLM_MODEL_ID（如 gpt-4o、deepseek-chat 等）")
            return
        llm = ChatOpenAI(
            model=model_id,
            base_url=os.getenv("OPEN_LLM_BASE_URL"),
            api_key=os.getenv("OPEN_LLM_API_KEY"),
            temperature=0,
        )

        # 创建 Agent，注入自定义 controller
        task = "帮我给张三发一条微信消息，内容是：今天下午3点开会"
        agent = Agent(
            config=AgentConfig(task=task, max_steps=15, use_vision=False),
            llm=llm,
            device=device,
            controller=controller,
        )

        print(f"\n任务: {task}")
        print("=" * 50)

        result = await agent.run()

        print("=" * 50)
        print(f"成功: {result.success}")
        print(f"总步数: {len(result.steps)}")
        print(f"耗时: {result.duration:.1f}s")
        if result.final_answer:
            print(f"最终回答: {result.final_answer}")

    finally:
        await manager.disconnect(device)
        print("\n设备已断开")


if __name__ == "__main__":
    serial = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(serial))

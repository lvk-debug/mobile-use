"""SDK 基础用法 — 自然语言驱动 Android 设备

使用方法:
    python examples/sdk_basic.py [serial]

不传 serial 则自动使用第一台 USB 设备。

前提:
    pip install -e ".[llm]"
    配置好 LLM API Key（如 OPENAI_API_KEY）

示例使用 OpenAI，也可替换为其他 LangChain 兼容 LLM：
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(model="claude-sonnet-4-20250514")
"""

import asyncio, os
import sys
from pathlib import Path
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from mobile_use import Agent, AgentConfig, ConnectionConfig, ConnectionManager

# .env 在 examples/ 目录下，相对于本文件定位
load_dotenv(Path(__file__).parent / ".env")


async def main(serial: str | None = None, task: str | None = None) -> None:

    # ── 1. 连接设备 ────────────────────────────────────────────────────
    manager = ConnectionManager()
    devices = await manager.list_devices()
    print(f"已连接设备: {devices}")

    if not devices:
        print("[FAIL] 未发现设备，请检查 USB 连接和 adb 授权")
        return

    serial = serial or devices[0]
    config = ConnectionConfig(serial=serial, connect_type="usb")
    device = await manager.connect(config)
    print(f"[OK] 已连接: {device.serial}")

    try:
        # ── 2. 创建 LLM ─────────────────────────────────────────────────
        # 替换为你使用的 LLM，确保设置了对应的环境变量
        model_id = os.getenv("LLM_MODEL_ID")
        if not model_id:
            print("[FAIL] 请设置环境变量 LLM_MODEL_ID（如 gpt-4o、deepseek-chat 等）")
            return
        llm = ChatOpenAI(
            model=model_id,
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
            temperature=0,
        )

        # ── 3. 创建 Agent ────────────────────────────────────────────────
        task = task or "在桌面左右滑动切换页面"
        agent = Agent(
            config=AgentConfig(
                task=task,
                max_steps=30,
                max_errors=3,
                use_vision=False,  # 设为 True 需要 LLM 支持图片输入（如 GPT-4o、Claude）
                log_file="./logs",  # 日志目录，每条任务自动生成独立日志文件；传 None 关闭
            ),
            llm=llm,
            device=device,
        )

        print(f"\n任务: {task}")
        print("=" * 50)

        # ── 4. 执行任务 ──────────────────────────────────────────────────
        result = await agent.run()

        # ── 5. 输出结果 ──────────────────────────────────────────────────
        print("=" * 50)
        print(f"成功: {result.success}")
        print(f"总步数: {len(result.steps)}")
        print(f"耗时: {result.duration:.1f}s")
        print(
            f"Token 消耗: {result.total_tokens} (输入: {result.total_input_tokens}, 输出: {result.total_output_tokens})"
        )

        if result.final_answer:
            print(f"最终回答: {result.final_answer}")

        if result.error:
            print(f"错误: {result.error}")

        # 打印每步详情
        print("\n--- 执行步骤 ---")
        for step in result.steps:
            print(f"  [{step.step_number}] {step.action_name}({step.action_params})")
            if step.result:
                status = "✓" if step.result.success else "✗"
                print(f"       {status} {step.result.message}")

    finally:
        await manager.disconnect(device)
        print("\n设备已断开")


if __name__ == "__main__":
    serial = sys.argv[1] if len(sys.argv) > 1 else None
    task = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(main(serial, task))

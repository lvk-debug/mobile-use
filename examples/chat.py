"""多轮对话任务示例 — 控制台输入，逐个任务执行

每轮从控制台读取一条任务，执行完毕（成功/失败/用户中断）后才能输入下一条。
输入 quit / exit / q 退出。

使用方法:
    python examples/muti_task.py [serial]
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from mobile_use import Agent, AgentConfig, ConnectionConfig, ConnectionManager
from mobile_use.agent.views import Task

# .env 在 examples/ 目录下，相对于本文件定位
load_dotenv(Path(__file__).parent / ".env")

PROMPT = "\n📝 请输入任务（quit 退出）: "


async def main(serial: str | None = None) -> None:
    # ── 1. 连接设备（只连一次，多轮复用）──────────────────────────────
    manager = ConnectionManager()
    devices = await manager.list_devices()
    print(f"已连接设备: {devices}")

    if not devices:
        print("[FAIL] 未发现设备，请检查 USB 连接和 adb 授权")
        return

    serial = serial or devices[0]
    config = ConnectionConfig(serial=serial, connect_type="usb")
    device = await manager.connect(config)
    print(f"[OK] 已连接: {device.serial}\n")

    try:
        # ── 2. 创建 LLM ──────────────────────────────────────────────────
        model_id = os.getenv("LLM_MODEL_ID")
        llm = ChatOpenAI(
            model=model_id,
            base_url=os.getenv("LLM_BASE_URL"),
            api_key=os.getenv("LLM_API_KEY"),
            temperature=0,
        )

        # ── 3. 多轮对话循环 ──────────────────────────────────────────────
        task_count = 0
        all_results = []

        while True:
            try:
                user_input = input(PROMPT).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n退出。")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "q"):
                print("退出。")
                break

            task_count += 1
            task = Task(
                name=f"任务{task_count}",
                description=user_input,
            )

            # 每个任务创建独立 Agent（日志文件各自独立）
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            agent = Agent(
                config=AgentConfig(
                    tasks=[task],
                    max_steps=30,
                    max_errors=3,
                    use_vision=False,
                    log_file=f"./logs/{ts}_task{task_count}.log",
                ),
                llm=llm,
                device=device,
            )

            print(f"\n🚀 任务 {task_count}: {user_input}")
            print("=" * 50)

            results = await agent.run()

            if results:
                result = results[0]
                all_results.append(result)

                print("=" * 50)
                print(f"✅ 成功: {result.success}")
                print(f"   步数: {len(result.steps)}")
                print(f"   耗时: {result.duration:.1f}s")
                print(
                    f"   Tokens: {result.total_tokens}"
                    f" (输入: {result.total_input_tokens}, 输出: {result.total_output_tokens})"
                )
                if result.final_answer:
                    print(f"   最终回答: {result.final_answer}")
                if result.error:
                    print(f"   错误: {result.error}")

                # 打印每步摘要
                print("\n--- 执行步骤 ---")
                for step in result.steps:
                    print(
                        f"  [{step.step_number}] {step.action_name}({step.action_params})"
                    )
                    if step.result:
                        status = "✓" if step.result.success else "✗"
                        print(f"       {status} {step.result.message}")
            else:
                print("⚠️  无结果返回")

            agent.close()

        # ── 4. 总结 ─────────────────────────────────────────────────────
        if all_results:
            print(f"\n{'='*50}")
            print(f"📊 会话结束，共执行 {len(all_results)} 个任务")
            ok = sum(1 for r in all_results if r.success)
            print(f"   成功: {ok}  失败: {len(all_results) - ok}")

    finally:
        await manager.disconnect(device)
        print("\n设备已断开")


if __name__ == "__main__":
    serial = sys.argv[1] if len(sys.argv) > 1 else None
    asyncio.run(main(serial))

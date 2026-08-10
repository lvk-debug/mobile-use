"""Agent 主编排器 — 观察→思考→行动 循环"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage
from loguru import logger

from mobile_use.agent.prompts import build_prompt
from mobile_use.agent.views import AgentConfig, AgentResult, AgentStep, Task
from mobile_use.controller.controller import Controller
from mobile_use.model.model import AgentOutput, LLMModel
from mobile_use.utils.dialog_detector import detect人工介入弹窗

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from mobile_use.driver.device import Device

__all__ = ["Agent"]


class Agent:
    """mobile-use Agent — 自然语言驱动 Android 设备的主循环

    用法::

        from langchain_openai import ChatOpenAI

        agent = Agent(
            config=AgentConfig(tasks=[Task(name="打开设置", description="打开系统设置")], max_steps=10),
            llm=ChatOpenAI(model="gpt-4o"),
            device=device,
        )
        results = await agent.run()
    """

    def __init__(
        self,
        config: AgentConfig,
        llm: BaseChatModel,
        device: Device,
        controller: Controller | None = None,
    ) -> None:
        self._config = config
        self._device = device
        self._llm_model = LLMModel(llm)
        self._controller = controller or Controller()
        self._log_fh = None
        self._task_queue: list[Task] = list(config.tasks)

        if config.log_file:
            log_path = Path(config.log_file)
            if log_path.suffix:
                # 传了具体文件名，直接使用
                log_path.parent.mkdir(parents=True, exist_ok=True)
                log_file = log_path
            else:
                # 传了目录，自动生成唯一文件名
                log_path.mkdir(parents=True, exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                task_names = "+".join(t.name for t in config.tasks[:3]) or "task"
                task_slug = self._slugify(task_names, max_len=40)
                log_file = log_path / f"{task_slug}_{ts}.log"
            self._log_fh = open(log_file, "w", encoding="utf-8")
            self._log_fh.write(f"Tasks: {[t.name for t in config.tasks]}\n")
            self._log_fh.write(f"Time: {datetime.now().isoformat()}\n")
            self._log_fh.write(f"Log:  {log_file}\n")
            self._log_fh.write(f"{'═' * 60}\n\n")
            logger.info("Step log file: {}", log_file)

    @property
    def controller(self) -> Controller:
        return self._controller

    @property
    def llm_model(self) -> LLMModel:
        return self._llm_model

    def add_task(self, task: Task) -> None:
        """追加任务到队列尾部，下次 run() 时按顺序执行。

        Args:
            task: 任务对象
        """
        self._task_queue.append(task)
        logger.info("任务已加入队列: [{}] {}", task.id, task.name)

    @staticmethod
    def _slugify(text: str, max_len: int = 40) -> str:
        """将任务描述转为文件名安全的短标识"""
        safe = "".join(c if c.isalnum() or c in " _-" else "" for c in text)
        safe = safe.strip().replace(" ", "_")
        return safe[:max_len] if safe else "task"

    def _log_messages(self, messages: list) -> None:
        """记录发送给 LLM 的完整消息上下文"""
        if not self._log_fh:
            return
        try:
            self._log_fh.write("[LLM Context] Messages sent to LLM:\n")
            for i, msg in enumerate(messages):
                role = type(msg).__name__
                content = msg.content
                if isinstance(content, list):
                    # 多模态：文本直接记录，图片记 [image]
                    parts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                parts.append(item["text"])
                            elif item.get("type") == "image_url":
                                parts.append("[screenshot image]")
                            else:
                                parts.append(f"[{item.get('type', '?')}]")
                        else:
                            parts.append(str(item))
                    content = "\n".join(parts)
                self._log_fh.write(f"  ┌─ [{i}] {role}\n")
                for line in str(content).splitlines():
                    self._log_fh.write(f"  │  {line}\n")
                self._log_fh.write("  └\n\n")
            self._log_fh.flush()
        except Exception:
            pass

    def _log_step(
        self,
        step: AgentStep,
        agent_output: AgentOutput | None = None,
    ) -> None:
        """记录单步：LLM 响应 + 执行结果 + token 统计"""
        if not self._log_fh:
            return
        try:
            self._log_fh.write(f"{'─' * 60}\n")
            self._log_fh.write(f"Step {step.step_number}\n")
            self._log_fh.write(f"{'─' * 60}\n\n")

            # LLM 解析后的输出
            if agent_output:
                self._log_fh.write("[LLM Response]\n")
                self._log_fh.write("  Thinking:\n")
                for line in agent_output.thinking.splitlines():
                    self._log_fh.write(f"    {line}\n")
                self._log_fh.write("  Actions:\n")
                for action in agent_output.action:
                    name = action.get("action_name", "?")
                    params = action.get("params", {})
                    self._log_fh.write(f"    - {name}({json.dumps(params, ensure_ascii=False)})\n")
                self._log_fh.write("\n")

            # 执行结果
            self._log_fh.write("[Action Result]\n")
            self._log_fh.write(f"  {step.action_name}({json.dumps(step.action_params, ensure_ascii=False)})\n")
            if step.result:
                status = "✓ OK" if step.result.success else "✗ FAIL"
                self._log_fh.write(f"  Result: {status} | {step.result.message}\n")
                if step.result.data:
                    self._log_fh.write(f"  Data: {json.dumps(step.result.data, ensure_ascii=False, default=str)}\n")

            # Token 统计
            self._log_fh.write(f"\n[Tokens] input={self._llm_model.total_input_tokens} "
                               f"output={self._llm_model.total_output_tokens} "
                               f"total={self._llm_model.total_tokens}\n\n")
            self._log_fh.flush()
        except Exception:
            pass

    def _log_summary(self, success: bool, steps: int, duration: float,
                     final_answer: str | None, error_msg: str | None) -> None:
        """写入日志文件末尾的执行总结"""
        if not self._log_fh:
            return
        try:
            self._log_fh.write(f"\n{'═' * 60}\n")
            self._log_fh.write("Summary\n")
            self._log_fh.write(f"{'═' * 60}\n")
            self._log_fh.write(f"Success: {success}\n")
            self._log_fh.write(f"Steps:   {steps}\n")
            self._log_fh.write(f"Duration: {duration:.1f}s\n")
            self._log_fh.write(f"Tokens:  {self._llm_model.total_tokens} "
                               f"(in={self._llm_model.total_input_tokens}, "
                               f"out={self._llm_model.total_output_tokens})\n")
            if final_answer:
                self._log_fh.write(f"Answer:  {final_answer}\n")
            if error_msg:
                self._log_fh.write(f"Error:   {error_msg}\n")
            self._log_fh.flush()
        except Exception:
            pass

    def close(self) -> None:
        """关闭日志文件"""
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None

    async def run(self) -> list[AgentResult]:
        """按顺序执行任务队列中所有任务。

        每个任务独立运行 observe→think→act 循环。某个任务失败后停止后续任务（fail-fast）。

        Returns:
            每个任务的执行结果列表
        """
        results: list[AgentResult] = []

        while self._task_queue:
            task = self._task_queue.pop(0)
            logger.info("开始执行任务: [{}] {}", task.id, task.name)
            result = await self._run_single(task)
            results.append(result)

            if not result.success:
                logger.warning("任务 [{}] {} 失败，停止后续任务", task.id, task.name)
                break

        return results

    @staticmethod
    def _action_fingerprint(name: str, params: dict) -> str:
        """生成动作指纹，用于重复检测"""
        import json

        return f"{name}({json.dumps(params, sort_keys=True, ensure_ascii=False)})"

    async def _run_single(self, task: Task) -> AgentResult:
        """执行单个任务的 observe→think→act 循环。

        Args:
            task: 要执行的任务

        Returns:
            该任务的执行结果
        """
        start_time = time.time()
        steps: list[AgentStep] = []
        consecutive_errors = 0
        final_answer: str | None = None
        success = False
        error_msg: str | None = None

        # 重复动作检测状态
        last_action_fp: str | None = None
        repeat_count = 0

        logger.info("Task started: [{}] {!r}, max_steps={}", task.id, task.description, self._config.max_steps)

        try:
            for step_num in range(1, self._config.max_steps + 1):
                logger.info("Step {}/{}", step_num, self._config.max_steps)

                # 1. 获取设备状态
                try:
                    state = await self._device.get_state(use_vision=self._config.use_vision)
                except Exception as e:
                    logger.error("Failed to get device state: {}", e)
                    consecutive_errors += 1
                    if consecutive_errors >= self._config.max_errors:
                        error_msg = f"Failed to get device state after {consecutive_errors} attempts: {e}"
                        break
                    continue

                # 1.5 检测需要人工介入的弹窗（权限/登录等）— 暂停等待用户手动处理
                dialog_msg = detect人工介入弹窗(state.ui_hierarchy)
                if dialog_msg:
                    logger.warning("Dialog requiring manual intervention detected: {}", dialog_msg)
                    handler = self._config.on_permission_dialog
                    if handler:
                        try:
                            handler(dialog_msg)
                        except Exception as e:
                            logger.error("Dialog handler error: {}", e)
                    else:
                        # 默认：CLI 模式下用 input() 等待用户
                        print(f"\n⚠️  检测到需要手动处理的弹窗: {dialog_msg}")
                        print("请在设备上手动处理后，按 Enter 继续...")
                        input()
                    continue  # 跳过本轮，下一轮重新获取状态

                # 2. 构造 prompt
                action_descs = self._controller.get_action_descriptions()
                messages = build_prompt(
                    task=task,
                    state=state,
                    history=steps,
                    action_descriptions=action_descs,
                    use_vision=self._config.use_vision,
                    include_xml=self._config.include_xml,
                    custom_system_prompt=self._config.system_prompt,
                )

                # 2.5 重复动作检测 — 向 LLM 注入警告
                if last_action_fp and repeat_count >= 2:
                    warn = (
                        f"⚠️ 你已经连续 {repeat_count} 次执行完全相同的动作 "
                        f"[{last_action_fp}]，但界面没有任何变化。"
                        "这说明该动作无效，请立即换一种不同的策略！"
                        "如果确实找不到目标元素，使用 done 说明原因并结束任务。"
                    )
                    messages.append(HumanMessage(content=warn))
                    logger.warning("重复动作检测: {} 连续 {} 次", last_action_fp, repeat_count)

                # 记录 LLM 上下文到日志
                self._log_messages(messages)

                # 3. 调用 LLM（vision 失败时自动降级为纯文本）
                try:
                    agent_output = await self._llm_model.invoke(messages)
                except Exception as e:
                    if self._config.use_vision:
                        logger.warning("LLM with vision failed, retrying without vision: {}", e)
                        try:
                            messages = build_prompt(
                                task=task,
                                state=state,
                                history=steps,
                                action_descriptions=action_descs,
                                use_vision=False,
                                include_xml=self._config.include_xml,
                                custom_system_prompt=self._config.system_prompt,
                            )
                            agent_output = await self._llm_model.invoke(messages)
                            self._config.use_vision = False
                            logger.info("Vision disabled for this session (model does not support images)")
                        except Exception as e2:
                            logger.error("LLM invocation failed: {}", e2)
                            consecutive_errors += 1
                            if consecutive_errors >= self._config.max_errors:
                                error_msg = f"LLM invocation failed after {consecutive_errors} attempts: {e2}"
                                break
                            continue
                    else:
                        logger.error("LLM invocation failed: {}", e)
                        consecutive_errors += 1
                        if consecutive_errors >= self._config.max_errors:
                            error_msg = f"LLM invocation failed after {consecutive_errors} attempts: {e}"
                            break
                        continue

                logger.info("LLM thinking: {}", agent_output.thinking[:200])

                # 4. 检查动作列表是否为空
                if not agent_output.action:
                    logger.warning("LLM returned empty action list, injecting wait action")
                    from mobile_use.action.base import ActionResult as _AR

                    step = AgentStep(
                        step_number=step_num,
                        state=state,
                        action_name="(no_action)",
                        action_params={},
                        result=_AR(success=False, message="LLM did not produce any action"),
                        llm_response=agent_output.model_dump_json(),
                        thinking=agent_output.thinking,
                    )
                    steps.append(step)
                    self._log_step(step, agent_output)
                    consecutive_errors += 1
                    if consecutive_errors >= self._config.max_errors:
                        error_msg = f"LLM produced no actions for {consecutive_errors} consecutive steps"
                        break
                    continue

                # 5. 执行动作（支持批量）
                logger.info("LLM actions: {}", agent_output.action)

                for action_item in agent_output.action:
                    action_name = action_item.get("action_name", "")
                    action_params = action_item.get("params", {})

                    logger.info("Executing: {}({})", action_name, action_params)

                    result = await self._controller.execute(
                        action_name=action_name,
                        params=action_params,
                        device=self._device,
                        state=state,
                    )
                    logger.info("Action {}({}) result: {}", action_name, action_params, result)
                    step = AgentStep(
                        step_number=step_num,
                        state=state,
                        action_name=action_name,
                        action_params=action_params,
                        result=result,
                        llm_response=agent_output.model_dump_json(),
                        thinking=agent_output.thinking,
                    )
                    steps.append(step)

                    # 记录本步到日志
                    self._log_step(step, agent_output)

                    if result.success:
                        consecutive_errors = 0
                    else:
                        consecutive_errors += 1
                        logger.warning("Action failed: {}", result.message)

                    # 检查是否完成
                    if action_name == "done":
                        final_answer = result.data.get("final_answer", "") if result.data else ""
                        success = True
                        logger.info("Task done: {}", final_answer)
                        break

                    if action_name == "error":
                        logger.warning("Agent reported error: {}", result.message)

                    # 更新重复动作计数
                    fp = self._action_fingerprint(action_name, action_params)
                    if fp == last_action_fp:
                        repeat_count += 1
                    else:
                        last_action_fp = fp
                        repeat_count = 1

                # 如果 done 了就退出外层循环
                if success:
                    break

                # 重复动作超限 → 强制停止
                if repeat_count >= self._config.max_repeated_actions:
                    error_msg = (
                        f"连续 {repeat_count} 次执行相同动作 [{last_action_fp}]，"
                        f"界面无变化，判定为无效循环，强制停止"
                    )
                    logger.warning(error_msg)
                    break

                # 连续错误检查
                if consecutive_errors >= self._config.max_errors:
                    error_msg = f"Consecutive errors reached limit ({self._config.max_errors})"
                    break

            else:
                # 循环正常结束（达到 max_steps）
                error_msg = f"Reached max steps ({self._config.max_steps}) without completing task"

        except Exception as e:
            logger.error("Agent crashed: {}", e)
            error_msg = f"Agent crashed: {e}"

        duration = time.time() - start_time
        logger.info("Task finished: [{}] success={}, steps={}, duration={:.1f}s", task.id, success, len(steps), duration)

        # 写入日志总结并关闭文件
        self._log_summary(success, len(steps), duration, final_answer, error_msg)
        self.close()

        return AgentResult(
            task=task.name,
            success=success,
            steps=steps,
            final_answer=final_answer,
            total_input_tokens=self._llm_model.total_input_tokens,
            total_output_tokens=self._llm_model.total_output_tokens,
            total_tokens=self._llm_model.total_tokens,
            duration=duration,
            error=error_msg,
        )

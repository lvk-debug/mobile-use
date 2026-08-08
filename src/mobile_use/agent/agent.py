"""Agent 主编排器 — 观察→思考→行动 循环"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from mobile_use.agent.prompts import build_prompt
from mobile_use.agent.views import AgentConfig, AgentResult, AgentStep
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
            config=AgentConfig(task="打开设置", max_steps=10),
            llm=ChatOpenAI(model="gpt-4o"),
            device=device,
        )
        result = await agent.run()
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
                task_slug = self._slugify(config.task, max_len=40)
                log_file = log_path / f"{task_slug}_{ts}.log"
            self._log_fh = open(log_file, "w", encoding="utf-8")
            self._log_fh.write(f"Task: {config.task}\n")
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

    async def run(self) -> AgentResult:
        """执行主循环：获取状态 → 构造 prompt → 调用 LLM → 解析动作 → 执行 → 重复

        Returns:
            AgentResult 执行结果
        """
        start_time = time.time()
        steps: list[AgentStep] = []
        consecutive_errors = 0
        final_answer: str | None = None
        success = False
        error_msg: str | None = None

        logger.info("Agent started: task={!r}, max_steps={}", self._config.task, self._config.max_steps)

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
                    task=self._config.task,
                    state=state,
                    history=steps,
                    action_descriptions=action_descs,
                    use_vision=self._config.use_vision,
                    custom_system_prompt=self._config.system_prompt,
                )

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
                                task=self._config.task,
                                state=state,
                                history=steps,
                                action_descriptions=action_descs,
                                use_vision=False,
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
                    # 记录一步以避免 history 不增长导致无限循环
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

                # 如果 done 了就退出外层循环
                if success:
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
        logger.info("Agent finished: success={}, steps={}, duration={:.1f}s", success, len(steps), duration)

        # 写入日志总结并关闭文件
        self._log_summary(success, len(steps), duration, final_answer, error_msg)
        self.close()

        return AgentResult(
            task=self._config.task,
            success=success,
            steps=steps,
            final_answer=final_answer,
            total_input_tokens=self._llm_model.total_input_tokens,
            total_output_tokens=self._llm_model.total_output_tokens,
            total_tokens=self._llm_model.total_tokens,
            duration=duration,
            error=error_msg,
        )

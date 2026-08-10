"""M3 Agent 集成测试（全 mock）"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from mobile_use.agent.agent import Agent
from mobile_use.agent.views import AgentConfig, AgentResult, AgentStep, Task
from mobile_use.action.base import ActionResult
from mobile_use.driver.device import AppInfo
from mobile_use.state.device_state import DeviceState
from mobile_use.state.ui_hierarchy import UIElement


# ── 辅助 ──────────────────────────────────────────────────────────────


def _make_state() -> DeviceState:
    return DeviceState(
        ui_hierarchy=UIElement(idx=0, clickable=True, text="test"),
        screenshot=b"\x89PNG",
        current_app=AppInfo(package="com.test", activity=".Main"),
        width=1080,
        height=2400,
    )


def _make_llm_response(thinking: str, actions: list[dict]) -> AIMessage:
    return AIMessage(
        content=json.dumps({"thinking": thinking, "action": actions}),
        usage_metadata={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
    )


def _mock_device() -> AsyncMock:
    device = AsyncMock()
    device.get_state = AsyncMock(return_value=_make_state())
    device.tap = AsyncMock()
    device.press_back = AsyncMock()
    device.press_home = AsyncMock()
    return device


def _task(name: str = "测试", desc: str | None = None) -> Task:
    return Task(name=name, description=desc or name)


# ── 测试 ──────────────────────────────────────────────────────────────


class TestAgentRun:
    """Agent 主循环测试"""

    @pytest.mark.asyncio
    async def test_single_step_done(self):
        """单步完成任务"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("任务很简单", [{"action_name": "done", "params": {"answer": "完成了"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("测试")], max_steps=10, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()

        assert len(results) == 1
        result = results[0]
        assert isinstance(result, AgentResult)
        assert result.success is True
        assert result.final_answer == "完成了"
        assert len(result.steps) == 1
        assert result.total_input_tokens > 0

    @pytest.mark.asyncio
    async def test_multi_step(self):
        """多步执行"""
        device = _mock_device()
        llm = AsyncMock()

        # 第一步：tap，第二步：done
        llm.ainvoke = AsyncMock(
            side_effect=[
                _make_llm_response("先点击", [{"action_name": "tap", "params": {"x": 100, "y": 200}}]),
                _make_llm_response("完成", [{"action_name": "done", "params": {"answer": "搞定了"}}]),
            ]
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("多步测试")], max_steps=10, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()
        result = results[0]

        assert result.success is True
        assert len(result.steps) == 2
        assert result.steps[0].action_name == "tap"
        assert result.steps[1].action_name == "done"

    @pytest.mark.asyncio
    async def test_max_steps_reached(self):
        """达到最大步数后退出"""
        device = _mock_device()
        llm = AsyncMock()
        # 每步都返回 swipe（不 done），直到 max_steps
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("继续", [{"action_name": "scroll", "params": {"direction": "up"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("无限循环")], max_steps=3, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()
        result = results[0]

        assert result.success is False
        assert "max steps" in (result.error or "")
        assert len(result.steps) == 3

    @pytest.mark.asyncio
    async def test_consecutive_errors_exit(self):
        """连续错误超阈值后退出"""
        device = _mock_device()
        llm = AsyncMock()
        # LLM 返回无效 action（参数错误导致执行失败）
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("出错", [{"action_name": "long_press", "params": {"x": "bad"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("错误测试")], max_steps=10, max_errors=2, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()
        result = results[0]

        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_llm_error_recovery(self):
        """LLM 调用失败后恢复"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            side_effect=[
                Exception("API error"),  # 第一次失败
                _make_llm_response("恢复了", [{"action_name": "done", "params": {"answer": "ok"}}]),
            ]
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("恢复测试")], max_steps=10, max_errors=3, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()

        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_device_state_error(self):
        """获取设备状态失败"""
        device = _mock_device()
        device.get_state = AsyncMock(side_effect=Exception("device disconnected"))
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(return_value=_make_llm_response("...", [{"action_name": "done", "params": {}}]))

        agent = Agent(
            config=AgentConfig(tasks=[_task("设备断连")], max_steps=5, max_errors=2, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()

        assert results[0].success is False

    @pytest.mark.asyncio
    async def test_duration_recorded(self):
        """执行时间被记录"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("done", [{"action_name": "done", "params": {"answer": "ok"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("计时")], max_steps=1, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()

        assert results[0].duration >= 0

    @pytest.mark.asyncio
    async def test_token_stats(self):
        """token 统计正确累加"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            side_effect=[
                _make_llm_response("step1", [{"action_name": "tap", "params": {"x": 1, "y": 2}}]),
                _make_llm_response("step2", [{"action_name": "done", "params": {"answer": "ok"}}]),
            ]
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("token测试")], max_steps=10, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()
        result = results[0]

        assert result.total_input_tokens == 200  # 100 * 2 steps
        assert result.total_output_tokens == 100  # 50 * 2 steps
        assert result.total_tokens == 300


class TestAgentController:
    """Agent 与 Controller 集成测试"""

    @pytest.mark.asyncio
    async def test_custom_controller(self):
        """可传入自定义 controller"""
        from mobile_use.controller.controller import Controller

        ctrl = Controller()

        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("done", [{"action_name": "done", "params": {"answer": "ok"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("自定义controller")], max_steps=1, use_vision=False),
            llm=llm,
            device=device,
            controller=ctrl,
        )
        assert agent.controller is ctrl


class TestTaskQueue:
    """任务队列测试"""

    @pytest.mark.asyncio
    async def test_add_task_then_run(self):
        """追加任务后 run() 按顺序执行"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("完成", [{"action_name": "done", "params": {"answer": "ok"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("原始任务", "打开设置")], max_steps=10, use_vision=False),
            llm=llm,
            device=device,
        )
        agent.add_task(_task("追加任务", "打开WiFi"))
        results = await agent.run()

        assert len(results) == 2
        assert results[0].success is True
        assert results[0].task == "原始任务"
        assert results[1].success is True
        assert results[1].task == "追加任务"

    @pytest.mark.asyncio
    async def test_multiple_tasks_sequential(self):
        """多个任务按队列顺序执行"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("完成", [{"action_name": "done", "params": {"answer": "ok"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[], max_steps=5, use_vision=False),
            llm=llm,
            device=device,
        )
        agent.add_task(_task("任务A", "打开设置"))
        agent.add_task(_task("任务B", "打开WiFi"))
        agent.add_task(_task("任务C", "打开蓝牙"))
        results = await agent.run()

        assert len(results) == 3
        assert [r.task for r in results] == ["任务A", "任务B", "任务C"]
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_fail_fast_stops_queue(self):
        """某个任务失败后停止后续任务"""
        device = _mock_device()
        llm = AsyncMock()
        # 第一个任务失败（连续错误），第二个任务不应执行
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("出错", [{"action_name": "long_press", "params": {"x": "bad"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[], max_steps=5, max_errors=1, use_vision=False),
            llm=llm,
            device=device,
        )
        agent.add_task(_task("会失败", "无效操作"))
        agent.add_task(_task("不应执行", "打开设置"))
        results = await agent.run()

        assert len(results) == 1  # 只有第一个任务的结果
        assert results[0].success is False

    @pytest.mark.asyncio
    async def test_queue_cleared_after_run(self):
        """run() 消费后队列清空"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("done", [{"action_name": "done", "params": {"answer": "ok"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("任务A")], max_steps=5, use_vision=False),
            llm=llm,
            device=device,
        )
        agent.add_task(_task("任务B"))
        await agent.run()

        assert len(agent._task_queue) == 0

    @pytest.mark.asyncio
    async def test_add_task_between_runs(self):
        """第一次 run 结束后追加任务，第二次 run 执行新任务"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("done", [{"action_name": "done", "params": {"answer": "ok"}}])
        )

        agent = Agent(
            config=AgentConfig(tasks=[_task("第一轮")], max_steps=5, use_vision=False),
            llm=llm,
            device=device,
        )
        results1 = await agent.run()
        assert len(results1) == 1
        assert results1[0].success is True

        # 第二轮追加任务
        agent.add_task(_task("第二轮"))
        results2 = await agent.run()
        assert len(results2) == 1
        assert results2[0].success is True
        assert results2[0].task == "第二轮"

    @pytest.mark.asyncio
    async def test_empty_queue_returns_empty(self):
        """空队列返回空列表"""
        device = _mock_device()
        llm = AsyncMock()

        agent = Agent(
            config=AgentConfig(tasks=[], max_steps=5, use_vision=False),
            llm=llm,
            device=device,
        )
        results = await agent.run()

        assert results == []
        assert llm.ainvoke.call_count == 0

    @pytest.mark.asyncio
    async def test_task_description_in_prompt(self):
        """任务描述正确传递给 LLM"""
        device = _mock_device()
        llm = AsyncMock()
        llm.ainvoke = AsyncMock(
            return_value=_make_llm_response("done", [{"action_name": "done", "params": {"answer": "ok"}}])
        )

        agent = Agent(
            config=AgentConfig(
                tasks=[_task("打开WiFi", "进入设置页面，找到WiFi开关并打开")],
                max_steps=5,
                use_vision=False,
            ),
            llm=llm,
            device=device,
        )
        await agent.run()

        call_args = llm.ainvoke.call_args[0][0]
        task_msg = str(call_args[1].content)
        assert "进入设置页面，找到WiFi开关并打开" in task_msg

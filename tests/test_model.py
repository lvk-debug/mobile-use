"""M3 Model (LLM 封装) 单元测试"""

from __future__ import annotations

import json

import pytest

from mobile_use.model.model import AgentOutput, LLMModel


class TestAgentOutput:
    """AgentOutput 模型测试"""

    def test_basic(self):
        output = AgentOutput(
            thinking="分析屏幕",
            action=[{"action_name": "tap", "params": {"x": 100, "y": 200}}],
        )
        assert output.thinking == "分析屏幕"
        assert len(output.action) == 1

    def test_empty(self):
        output = AgentOutput()
        assert output.thinking == ""
        assert output.action == []

    def test_multiple_actions(self):
        output = AgentOutput(
            thinking="多步操作",
            action=[
                {"action_name": "tap", "params": {"x": 100, "y": 200}},
                {"action_name": "wait", "params": {"seconds": 1}},
            ],
        )
        assert len(output.action) == 2


class TestParseResponse:
    """LLM 输出 JSON 解析测试"""

    def test_pure_json(self):
        raw = json.dumps({
            "thinking": "我要点击搜索按钮",
            "action": [{"action_name": "tap", "params": {"x": 540, "y": 240}}],
        })
        output = LLMModel.parse_response(raw)
        assert output.thinking == "我要点击搜索按钮"
        assert output.action[0]["action_name"] == "tap"

    def test_markdown_code_block(self):
        raw = """这是我的思考：
```json
{
  "thinking": "点击设置",
  "action": [{"action_name": "tap", "params": {"element_index": 2}}]
}
```
"""
        output = LLMModel.parse_response(raw)
        assert output.thinking == "点击设置"
        assert output.action[0]["params"]["element_index"] == 2

    def test_mixed_text_with_json(self):
        raw = '''我分析了屏幕状态，决定执行以下操作：
{"thinking": "找到搜索框", "action": [{"action_name": "input_text", "params": {"text": "hello"}}]}
这是执行结果。'''
        output = LLMModel.parse_response(raw)
        assert output.action[0]["action_name"] == "input_text"

    def test_action_as_dict_converted_to_list(self):
        """LLM 可能输出 action 为单个 dict，应自动转为 list"""
        raw = json.dumps({
            "thinking": "单动作",
            "action": {"action_name": "done", "params": {"answer": "完成"}},
        })
        output = LLMModel.parse_response(raw)
        assert isinstance(output.action, list)
        assert output.action[0]["action_name"] == "done"

    def test_nested_json_extraction(self):
        """从复杂文本中提取嵌套 JSON"""
        raw = '''```json
{
  "thinking": "需要先上滑查看更多内容，然后点击 WiFi",
  "action": [
    {"action_name": "scroll", "params": {"direction": "up"}},
    {"action_name": "tap", "params": {"element_index": 5}}
  ]
}
```'''
        output = LLMModel.parse_response(raw)
        assert len(output.action) == 2

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError, match="Failed to parse"):
            LLMModel.parse_response("这不是 JSON 也没有大括号")

    def test_json_with_trailing_comma(self):
        """带尾逗号的 JSON 应该报错（标准 JSON 不支持）"""
        raw = '{"thinking": "test", "action": [],}'
        with pytest.raises(ValueError):
            LLMModel.parse_response(raw)


class TestJSONRepair:
    """LLM 输出 JSON 修复测试"""

    def test_unescaped_quotes_in_thinking(self):
        """thinking 中包含未转义的双引号"""
        raw = (
            '{"thinking":"我现在看到的是网络设置页面，有"修复连接"按钮'
            '和已连接的WiFi网络信息。我需要返回到设置主页面。",'
            '"action":[{"action_name":"back","params":{}}]}'
        )
        output = LLMModel.parse_response(raw)
        assert output.thinking
        assert output.action[0]["action_name"] == "back"

    def test_unescaped_chinese_quotes_in_thinking(self):
        """thinking 中包含中文引号"""
        raw = (
            '{"thinking":"点击"设置"按钮",'
            '"action":[{"action_name":"tap","params":{"element_index":0}}]}'
        )
        output = LLMModel.parse_response(raw)
        assert "设置" in output.thinking
        assert output.action[0]["action_name"] == "tap"

    def test_normal_json_still_works(self):
        """正常 JSON 不受影响"""
        raw = '{"thinking":"简单操作","action":[{"action_name":"done","params":{"answer":"完成"}}]}'
        output = LLMModel.parse_response(raw)
        assert output.thinking == "简单操作"
        assert output.action[0]["action_name"] == "done"

    def test_regex_fallback(self):
        """JSON 完全无法解析时，正则提取"""
        raw = '''broken prefix {"thinking":"找到WiFi","action":[{"action_name":"tap","params":{"x":1,"y":2}}]} broken suffix'''
        # 这个能被 _extract_json 提取出来，正常解析
        output = LLMModel.parse_response(raw)
        assert output.action[0]["action_name"] == "tap"


class TestLLMModelTokens:
    """Token 统计测试"""

    def test_initial_tokens_zero(self):
        """需要一个 mock LLM 来测试 token 统计"""
        from unittest.mock import MagicMock

        mock_llm = MagicMock()
        model = LLMModel(mock_llm)
        assert model.total_input_tokens == 0
        assert model.total_output_tokens == 0
        assert model.total_tokens == 0

    @pytest.mark.asyncio
    async def test_token_accumulation(self):
        """token 累计统计"""
        from unittest.mock import AsyncMock, MagicMock

        from langchain_core.messages import AIMessage

        # Mock LLM 返回带有 usage_metadata 的响应
        response = AIMessage(
            content=json.dumps({
                "thinking": "test",
                "action": [{"action_name": "done", "params": {"answer": "ok"}}],
            }),
            usage_metadata={
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
            },
        )

        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=response)

        model = LLMModel(mock_llm)
        await model.invoke([MagicMock()])

        assert model.total_input_tokens == 100
        assert model.total_output_tokens == 50
        assert model.total_tokens == 150

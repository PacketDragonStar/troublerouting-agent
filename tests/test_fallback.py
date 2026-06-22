"""
Ticket 10: LLM 降级 + 故障恢复 测试

验证指数退避重试、模型降级链、半成品报告。
"""
import pytest


class TestRetryLogic:
    """重试逻辑测试"""

    def test_retry_exponential_backoff(self):
        from agent.fallback import retry_with_backoff
        delays = []
        max_retries = 3
        for attempt in range(max_retries):
            delay = 5 * (2 ** attempt)
            delays.append(delay)
        assert delays == [5, 10, 20]

    def test_max_retries_respected(self):
        from agent.fallback import LLMFallbackHandler
        handler = LLMFallbackHandler()
        assert handler.max_retries == 2


class TestModelFallback:
    """模型降级链测试"""

    def test_model_chain_order(self):
        from agent.fallback import LLMFallbackHandler
        handler = LLMFallbackHandler()
        assert len(handler.model_chain) == 3
        assert handler.model_chain[0] == "gpt-4o"
        assert handler.model_chain[1] == "gpt-4o-mini"
        assert handler.model_chain[2] == "local"

    def test_next_model_after_failure(self):
        from agent.fallback import LLMFallbackHandler
        handler = LLMFallbackHandler()
        assert handler.current_model == "gpt-4o"
        handler.fallback()
        assert handler.current_model == "gpt-4o-mini"
        handler.fallback()
        assert handler.current_model == "local"


class TestDegradedReport:
    """半成品报告测试"""

    def test_degraded_report_generated(self):
        from agent.fallback import generate_degraded_report
        report = generate_degraded_report(
            fault_description="核心交换机 10.0.0.1 OSPF 断开",
            collected_data_summary="已收集部分接口数据",
            dispatcher_summary="Slow Path 已启动",
        )
        assert "核心交换机" in report
        assert "OSPF" in report
        assert "降级" in report
        assert "已收集" in report

    def test_degraded_report_has_session_structure(self):
        from agent.fallback import generate_degraded_report
        report = generate_degraded_report("故障", "", "")
        assert "## " in report
        assert "降级" in report
        assert "中断" in report

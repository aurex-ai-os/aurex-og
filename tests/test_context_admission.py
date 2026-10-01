"""
tests/test_context_admission.py  —  Phase 16
Tests for context admission, waterfall, and error classification.
"""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.context_engine.context_admission import (
    estimate_input_tokens, calculate_required_context,
    safe_context_limit, can_fit, admit_or_raise, ContextAdmissionError
)
from src.context_engine.context_waterfall import run_waterfall
from src.context_engine.error_recovery import ErrorClassifier, ErrorClass


def _msgs(n_words: int):
    return [{"role": "user", "content": " ".join(["word"] * n_words)}]


class TestContextAdmission:
    def test_short_message_fits_128k(self):
        msgs = _msgs(100)
        info = admit_or_raise(msgs, 128000, output_budget=4096, model_id="test")
        assert info["fits"] is True

    def test_exact_boundary_fits(self):
        # 50 words * ~1 token each = ~50 tokens; output=0; overhead=200; total=250
        # Use context_window=300 → safe=276 → 250 ≤ 276 → fits
        msgs = [{"role": "user", "content": "word " * 50}]
        info = admit_or_raise(msgs, 300, output_budget=0, model_id="boundary")
        assert info["fits"] is True


    def test_oversized_raises(self):
        msgs = _msgs(10000)  # ~10k tokens
        with pytest.raises(ContextAdmissionError) as exc_info:
            admit_or_raise(msgs, 4096, output_budget=4096, model_id="small")
        assert exc_info.value.required > exc_info.value.available

    def test_128k_model(self):
        msgs = _msgs(30000)  # ~30k tokens
        info = admit_or_raise(msgs, 128000, output_budget=4096, model_id="128k")
        assert info["fits"] is True

    def test_1m_model(self):
        msgs = _msgs(200000)  # ~200k tokens
        info = admit_or_raise(msgs, 1_000_000, output_budget=4096, model_id="1m")
        assert info["fits"] is True

    def test_safety_margin_applied(self):
        # 92% safety margin: a 1000-token window should only accept up to 920 tokens
        assert safe_context_limit(1000) == 920

    def test_can_fit_true(self):
        assert can_fit(128000, 10000) is True

    def test_can_fit_false(self):
        assert can_fit(4096, 10000) is False

    def test_estimate_tokens_fallback(self):
        msgs = [{"role": "user", "content": "Hello world this is a test"}]
        tokens = estimate_input_tokens(msgs)
        assert tokens > 0

    def test_calculate_required(self):
        required = calculate_required_context(1000, 4096, reasoning_budget=500)
        assert required == 1000 + 4096 + 500 + 200  # 200 = overhead


class TestContextWaterfall:
    def test_level_0_direct(self):
        msgs = _msgs(50)
        result = run_waterfall(msgs, context_window=128000, output_budget=4096)
        assert result.level_reached == 0
        assert result.strategy == "DIRECT"

    def test_level_1_dedup(self):
        msg = {"role": "user", "content": "repeated message"}
        msgs = [msg, msg, msg, {"role": "assistant", "content": "hi"}]
        result = run_waterfall(msgs, context_window=50, output_budget=0)
        assert result.level_reached <= 4  # handled by waterfall

    def test_huge_conversation_handled(self):
        msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": "word " * 500} for i in range(40)]
        result = run_waterfall(msgs, context_window=8192, output_budget=4096)
        assert result.level_reached >= 1  # waterfall kicked in
        assert not result.exhausted

    def test_split_flag_for_enormous(self):
        # Build something too big for even level 5 to handle
        msgs = [{"role": "user", "content": "x " * 50000}]
        result = run_waterfall(msgs, context_window=1000, output_budget=100)
        assert result.needs_split is True


class TestErrorClassifier:
    def test_classify_context_overflow_400(self):
        e = Exception("context length exceeded")
        assert ErrorClassifier.classify(e, 400) == ErrorClass.CONTEXT_OVERFLOW

    def test_classify_context_overflow_413(self):
        assert ErrorClassifier.classify(Exception("too large"), 413) == ErrorClass.CONTEXT_OVERFLOW

    def test_classify_rate_limit(self):
        assert ErrorClassifier.classify(Exception("too many"), 429) == ErrorClass.RATE_LIMIT

    def test_classify_auth(self):
        assert ErrorClassifier.classify(Exception("unauthorized"), 401) == ErrorClass.AUTH_FAILURE

    def test_classify_unavailable(self):
        assert ErrorClassifier.classify(Exception("bad gateway"), 502) == ErrorClass.PROVIDER_UNAVAILABLE

    def test_classify_timeout(self):
        assert ErrorClassifier.classify(Exception("read timeout"), 0) == ErrorClass.TIMEOUT

    def test_classify_network(self):
        assert ErrorClassifier.classify(Exception("connection reset"), 0) == ErrorClass.NETWORK_ERROR

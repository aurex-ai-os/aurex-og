"""
tests/test_token_ledger.py  —  Phase 16
"""
import pytest, sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.token_ledger import TokenLedger


@pytest.fixture
def ledger(tmp_path):
    db = f"sqlite:///{tmp_path}/test_ledger.db"
    return TokenLedger(db_url=db)


class TestTokenLedger:
    def test_record_and_retrieve(self, ledger):
        ledger.record(session_id="s1", model_id="gpt-4o", input_tokens=500, output_tokens=200)
        stats = ledger.get_stats(session_id="s1")
        assert stats["count"] == 1
        assert stats["input_tokens"] == 500

    def test_filter_by_model(self, ledger):
        ledger.record(model_id="gpt-4o", input_tokens=100)
        ledger.record(model_id="claude-3", input_tokens=200)
        stats = ledger.get_stats(model_id="gpt-4o")
        assert stats["count"] == 1
        assert stats["input_tokens"] == 100

    def test_filter_by_provider(self, ledger):
        ledger.record(provider_id="openrouter", input_tokens=300)
        ledger.record(provider_id="freellmapi", input_tokens=50)
        stats = ledger.get_stats(provider_id="openrouter")
        assert stats["input_tokens"] == 300

    def test_filter_by_pool(self, ledger):
        ledger.record(provider_pool="omniroute", input_tokens=400)
        ledger.record(provider_pool="direct", input_tokens=100)
        stats = ledger.get_stats(provider_pool="omniroute")
        assert stats["count"] == 1

    def test_no_secret_in_record(self, ledger):
        # The record method must not accept or store API keys
        import inspect
        sig = inspect.signature(ledger.record)
        params = list(sig.parameters.keys())
        assert "api_key" not in params
        assert "password" not in params
        assert "token" not in params

    def test_empty_stats(self, ledger):
        stats = ledger.get_stats(session_id="nonexistent")
        assert stats["count"] == 0

    def test_multiple_records_aggregated(self, ledger):
        for _ in range(5):
            ledger.record(session_id="batch", input_tokens=100, output_tokens=50)
        stats = ledger.get_stats(session_id="batch")
        assert stats["count"] == 5
        assert stats["input_tokens"] == 500
        assert stats["output_tokens"] == 250

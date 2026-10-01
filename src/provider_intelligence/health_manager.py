"""
health_manager.py

Tracks per-(provider, model) health state.
Persists health state to a JSON file so cold-start does not assume everything is HEALTHY.
"""

import time
import json
import logging
import os
from typing import Dict, Optional
from src.provider_intelligence.models import HealthState

logger = logging.getLogger(__name__)

_PERSIST_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "provider_health.json"
)


def _load_persisted() -> Dict:
    try:
        if os.path.exists(_PERSIST_PATH):
            with open(_PERSIST_PATH, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_persisted(data: Dict):
    try:
        os.makedirs(os.path.dirname(_PERSIST_PATH), exist_ok=True)
        with open(_PERSIST_PATH, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug(f"[HealthManager] Could not persist health state: {e}")


class HealthManager:
    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec

        # In-memory state
        self._health_state: Dict[str, str] = {}
        self._consecutive_failures: Dict[str, int] = {}
        self._last_failure_time: Dict[str, float] = {}
        self._last_success_time: Dict[str, float] = {}

        # Load persisted state from last run so cold-start reflects real history
        self._load_from_disk()

    def _load_from_disk(self):
        data = _load_persisted()
        now = time.time()
        for key, info in data.items():
            state = info.get("state", HealthState.UNKNOWN)
            last_fail = info.get("last_failure_time", 0)
            failures = info.get("consecutive_failures", 0)

            # If the persisted state was UNAVAILABLE but the timeout has expired, demote to DEGRADED
            if state in (HealthState.UNAVAILABLE, HealthState.RATE_LIMITED):
                if now - last_fail > self.recovery_timeout_sec * 3:
                    state = HealthState.DEGRADED

            self._health_state[key] = state
            self._consecutive_failures[key] = failures
            self._last_failure_time[key] = last_fail

    def _persist(self):
        data = {}
        for key in self._health_state:
            data[key] = {
                "state": self._health_state[key],
                "consecutive_failures": self._consecutive_failures.get(key, 0),
                "last_failure_time": self._last_failure_time.get(key, 0),
                "last_success_time": self._last_success_time.get(key, 0),
            }
        _save_persisted(data)

    def record_success(self, provider_id: str, model_id: str):
        key = f"{provider_id}::{model_id}"
        self._health_state[key] = HealthState.HEALTHY
        self._consecutive_failures[key] = 0
        self._last_success_time[key] = time.time()
        self._persist()

    def record_failure(self, provider_id: str, model_id: str, status_code: int = 500):
        key = f"{provider_id}::{model_id}"
        self._consecutive_failures[key] = self._consecutive_failures.get(key, 0) + 1
        self._last_failure_time[key] = time.time()

        if status_code == 429:
            self._health_state[key] = HealthState.RATE_LIMITED
        elif self._consecutive_failures[key] >= self.failure_threshold:
            self._health_state[key] = HealthState.UNAVAILABLE
        else:
            self._health_state[key] = HealthState.DEGRADED

        logger.warning(
            f"[HealthManager] {key} failure #{self._consecutive_failures[key]} "
            f"(HTTP {status_code}) → {self._health_state[key]}"
        )
        self._persist()

    def get_health(self, provider_id: str, model_id: str) -> HealthState:
        key = f"{provider_id}::{model_id}"
        state = self._health_state.get(key, HealthState.UNKNOWN)

        # Auto-recover if enough time has passed since last failure
        if state in (HealthState.UNAVAILABLE, HealthState.RATE_LIMITED):
            last_fail = self._last_failure_time.get(key, 0)
            if time.time() - last_fail > self.recovery_timeout_sec:
                logger.info(f"[HealthManager] {key}: auto-promoting to DEGRADED (probe state)")
                self._health_state[key] = HealthState.DEGRADED
                self._persist()
                return HealthState.DEGRADED

        return HealthState(state) if isinstance(state, str) else state

    def get_consecutive_failures(self, provider_id: str, model_id: str) -> int:
        key = f"{provider_id}::{model_id}"
        return self._consecutive_failures.get(key, 0)

    def reset(self, provider_id: str, model_id: str):
        """Fully reset a provider+model to UNKNOWN (e.g., after re-configuration)."""
        key = f"{provider_id}::{model_id}"
        self._health_state.pop(key, None)
        self._consecutive_failures.pop(key, None)
        self._last_failure_time.pop(key, None)
        self._persist()

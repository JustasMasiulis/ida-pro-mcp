"""Unit tests for ida_pro_mcp.worker_lifecycle.WorkerLifecycle.

These run outside IDA: the module imports nothing IDA-specific.
"""

import threading
import time

from ida_pro_mcp.worker_lifecycle import WorkerLifecycle


def test_check_returns_none_while_under_ttl():
    lc = WorkerLifecycle(idle_ttl_sec=60.0, poll_interval_sec=0.05)
    assert lc.check_shutdown_reason() is None


def test_check_fires_after_idle_ttl():
    lc = WorkerLifecycle(idle_ttl_sec=0.05, poll_interval_sec=0.05)
    time.sleep(0.10)
    reason = lc.check_shutdown_reason()
    assert reason is not None and "no requests" in reason


def test_touch_resets_idle_ttl():
    lc = WorkerLifecycle(idle_ttl_sec=0.10, poll_interval_sec=0.05)
    time.sleep(0.06)
    lc.touch()
    # Cumulative wait (0.06 + 0.06 = 0.12) is > ttl but each gap is < ttl.
    time.sleep(0.06)
    assert lc.check_shutdown_reason() is None
    time.sleep(0.10)
    assert lc.check_shutdown_reason() is not None


def test_watchdog_fires_callback_and_exits():
    fired: list[str] = []
    done = threading.Event()

    def on_shutdown(reason: str) -> None:
        fired.append(reason)
        done.set()

    lc = WorkerLifecycle(idle_ttl_sec=0.05, poll_interval_sec=0.02)
    lc.start(on_shutdown=on_shutdown)
    try:
        assert done.wait(timeout=2.0), "watchdog did not fire"
        assert fired and "no requests" in fired[0]
    finally:
        lc.stop()


def test_watchdog_does_not_fire_while_touched():
    fired: list[str] = []
    lc = WorkerLifecycle(idle_ttl_sec=0.10, poll_interval_sec=0.02)
    lc.start(on_shutdown=lambda reason: fired.append(reason))
    try:
        deadline = time.monotonic() + 0.30
        while time.monotonic() < deadline:
            lc.touch()
            time.sleep(0.03)
        assert fired == []
    finally:
        lc.stop()


def test_snapshot_exposes_idle_ttl():
    lc = WorkerLifecycle(idle_ttl_sec=42.0)
    snap = lc.snapshot()
    assert snap["idle_ttl_sec"] == 42.0
    assert isinstance(snap["last_request_age_sec"], float)

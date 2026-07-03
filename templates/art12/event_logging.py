"""
EU AI Act Article 12 — Event Logging (Record-Keeping)
Requirement: High-risk AI systems must automatically record events over their
lifetime to ensure traceability. Keep logs at least 6 months (Art. 19).

Usage: Wrap your AI calls with @log_ai_call, or use AILogger directly.
"""

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from pathlib import Path
from typing import Any

logger = logging.getLogger("compliance.art12")

DEFAULT_RETENTION_MONTHS = 6
TRUNCATE_CHARS = 1000  # keep logged payloads bounded; adjust to your privacy policy


class AILogger:
    """EU AI Act Article 12 compliant event logger.

    Writes one JSON object per line (JSONL) so logs stay grep-able and easy
    to ship to any log pipeline. Each record carries a `retention_until`
    stamp used by cleanup_expired().
    """

    def __init__(self, log_dir: str | Path = "ai_logs",
                 retention_months: int = DEFAULT_RETENTION_MONTHS):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "ai_events.jsonl"
        self.retention_months = retention_months

    def log_event(
        self,
        event_type: str,
        input_data: Any,
        output_data: Any,
        model: str,
        metadata: dict | None = None,
    ) -> dict:
        """Append one AI interaction event to the JSONL log and return it."""
        now = datetime.now(UTC)
        event = {
            "timestamp": now.isoformat(timespec="seconds"),
            "event_type": event_type,
            "model": model,
            # Truncate payloads: Art. 12 wants traceability, not full data dumps.
            "input": str(input_data)[:TRUNCATE_CHARS],
            "output": str(output_data)[:TRUNCATE_CHARS],
            "metadata": metadata or {},
            "retention_until": (now + timedelta(days=self.retention_months * 30)).isoformat(
                timespec="seconds"
            ),
        }
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def cleanup_expired(self) -> int:
        """Drop records past their retention date. Returns number removed.

        Rewrites the JSONL file keeping only unexpired records. Run this from
        a scheduled job (cron, celery beat, etc.).
        """
        if not self.log_file.is_file():
            return 0
        now_iso = datetime.now(UTC).isoformat(timespec="seconds")
        kept: list[str] = []
        removed = 0
        for line in self.log_file.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)  # never silently destroy unparseable evidence
                continue
            if record.get("retention_until", "") >= now_iso:
                kept.append(line)
            else:
                removed += 1
        self.log_file.write_text(
            "\n".join(kept) + ("\n" if kept else ""), encoding="utf-8"
        )
        return removed


def log_ai_call(
    func: Callable | None = None,
    *,
    ai_logger: AILogger | None = None,
) -> Callable:
    """Decorator that logs AI function calls for Article 12 compliance.

        @log_ai_call
        def ask(prompt: str, model: str = "gpt-4o") -> str: ...

    Pass a shared AILogger to avoid re-creating it per call:
        @log_ai_call(ai_logger=my_logger)
    """

    def decorator(inner: Callable) -> Callable:
        active_logger = ai_logger or AILogger()

        @wraps(inner)
        def wrapper(*args, **kwargs):
            result = inner(*args, **kwargs)
            active_logger.log_event(
                event_type="ai_call",
                input_data={"args": args, "kwargs": {k: v for k, v in kwargs.items()}},
                output_data=result,
                model=str(kwargs.get("model", "unknown")),
                metadata={"function": inner.__qualname__},
            )
            return result

        return wrapper

    # Support both @log_ai_call and @log_ai_call(ai_logger=...)
    if func is not None:
        return decorator(func)
    return decorator


if __name__ == "__main__":
    demo_logger = AILogger(log_dir="ai_logs_demo")

    @log_ai_call(ai_logger=demo_logger)
    def fake_completion(prompt: str, model: str = "demo-model") -> str:
        return f"echo: {prompt}"

    fake_completion("hello", model="demo-model")
    print(f"events logged to {demo_logger.log_file}")
    print(f"expired removed: {demo_logger.cleanup_expired()}")

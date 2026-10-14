"""Local execution records for the later workflow visualizer."""

import json
import os
import re
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marketpilot.storage import WorkflowStore

LOG_DIRECTORY = Path(__file__).resolve().parent.parent / "data" / "runs"


def utc_now() -> str:
    """Use UTC timestamps so logs are unambiguous across computers."""
    return datetime.now(timezone.utc).isoformat()


def redact(text: str) -> str:
    """Avoid storing API keys accidentally included in prompts or errors."""
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        text = text.replace(key, "[REDACTED]")
    return re.sub(r"sk-[A-Za-z0-9_-]+", "[REDACTED]", text)


class ExecutionLog:
    """One JSON file per run; save each transition, not invented plan steps."""

    def __init__(self, prompt: str, model: str, notify: Callable[[str], None] | None = None,
                directory: Path = LOG_DIRECTORY, store: "WorkflowStore | None" = None):
        self.model = model
        self.notify = notify
        self.store = store
        self.started = time.perf_counter()
        self.path = directory / f"{uuid4().hex}.json"
        self.record = {
            "schema_version": 1, "run_id": self.path.stem,
            "model": model, "prompt": prompt, "status": "running",
            "started_at": utc_now(), "ended_at": None,
            "duration_seconds": None, "steps": [], "final_output": None, "final_report": None, "error": None,
        }
        self.save()
        self.emit(f"[Log] {self.path}")

    def emit(self, message: str) -> None:
        if self.notify:
            self.notify(redact(message))

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Replace atomically so a future dashboard cannot read half-written JSON.
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(redact(json.dumps(self.record, indent=2, ensure_ascii=False)),
                            encoding="utf-8")
        temporary.replace(self.path)
        if self.store is not None:
            self.store.save_run(self.record)

    async def execute(self, name: str, inputs: dict, operation: Callable[[], Awaitable[dict]]) -> dict:
        """Wrap the actual operation with status, inputs, outputs, and duration."""
        step = {
            "step_id": uuid4().hex, "sequence": len(self.record["steps"]) + 1,
            "tool": name, "inputs": inputs, "outputs": None, "status": "running",
            "started_at": utc_now(), "ended_at": None, "duration_seconds": None, "error": None,
        }
        self.record["steps"].append(step)
        started = time.perf_counter()
        self.save()
        self.emit(f"[Running] {name}")
        try:
            output = await operation()
            step.update(status="completed", outputs=output)
            return output
        except BaseException as exc:
            # Cancellation must also leave an honest failure record.
            step.update(status="failed", error={"type": type(exc).__name__, "message": str(exc)})
            raise
        finally:
            step.update(ended_at=utc_now(), duration_seconds=round(time.perf_counter() - started, 3))
            self.save()
            self.emit(f"[{step['status'].capitalize()}] {name} — {step['duration_seconds']:.3f}s")

    def finish(self, output: str | None = None, error: BaseException | None = None,
               report: dict | None = None) -> None:
        self.record.update(
            status="failed" if error else "completed", ended_at=utc_now(),
            duration_seconds=round(time.perf_counter() - self.started, 3), final_output=output,
            final_report=report,
            error={"type": type(error).__name__, "message": str(error)} if error else None,
        )
        self.save()


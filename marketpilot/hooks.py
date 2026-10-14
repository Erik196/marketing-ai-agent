"""Real SDK lifecycle callbacks for main-model execution, separate from tool logging."""

import time

from agents import RunHooks

from marketpilot.execution import utc_now


class RuntimeHooks(RunHooks):
    def __init__(self):
        self.started = None

    async def on_llm_start(self, context, agent, system_prompt, input_items):
        self.started = time.perf_counter()
        calls = context.context.record["model_calls"]
        calls.append({"sequence": len(calls) + 1, "agent": agent.name, "status": "running",
                      "started_at": utc_now(), "ended_at": None, "duration_seconds": None,
                      "input_tokens": None, "output_tokens": None})
        context.context.save()
        context.context.emit(f"[Model] Call {len(calls)} running")

    async def on_llm_end(self, context, agent, response):
        call = context.context.record["model_calls"][-1]
        call.update(status="completed", ended_at=utc_now(),
                    duration_seconds=round(time.perf_counter() - self.started, 3),
                    input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)
        context.context.save()
        context.context.emit(f"[Model] Call {call['sequence']} completed — {call['duration_seconds']:.3f}s")

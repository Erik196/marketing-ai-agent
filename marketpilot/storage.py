"""SQLite persistence for workflow state and explicit retrieval of saved reports."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from marketpilot.execution import redact

DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "workflows.db"


class WorkflowStore:
    def __init__(self, path: Path = DATABASE_PATH):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY, model TEXT NOT NULL, prompt TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
                    started_at TEXT NOT NULL, ended_at TEXT, duration_seconds REAL,
                    final_output TEXT, final_report_json TEXT, error_json TEXT
                );
                CREATE TABLE IF NOT EXISTS tool_steps (
                    step_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(run_id),
                    sequence INTEGER NOT NULL, tool TEXT NOT NULL, status TEXT NOT NULL,
                    inputs_json TEXT NOT NULL, outputs_json TEXT, error_json TEXT,
                    started_at TEXT NOT NULL, ended_at TEXT, duration_seconds REAL,
                    UNIQUE(run_id, sequence)
                );
            """)

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        return db

    def save_run(self, record: dict) -> None:
        """Upsert a snapshot in one transaction so readers see consistent state."""
        record = json.loads(redact(json.dumps(record)))
        encode = lambda value: json.dumps(value) if value is not None else None
        with closing(self._connect()) as db, db:
            db.execute("""
                INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET status=excluded.status,
                    ended_at=excluded.ended_at, duration_seconds=excluded.duration_seconds,
                    final_output=excluded.final_output, final_report_json=excluded.final_report_json,
                    error_json=excluded.error_json
            """, (record["run_id"], record["model"], record["prompt"], record["status"],
                  record["started_at"], record["ended_at"], record["duration_seconds"],
                  record["final_output"], encode(record.get("final_report")), encode(record["error"])))
            for step in record["steps"]:
                # Bound parameters keep data separate from SQL code.
                db.execute("""
                    INSERT INTO tool_steps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(step_id) DO UPDATE SET status=excluded.status,
                        outputs_json=excluded.outputs_json, error_json=excluded.error_json,
                        ended_at=excluded.ended_at, duration_seconds=excluded.duration_seconds
                """, (step["step_id"], record["run_id"], step["sequence"], step["tool"], step["status"],
                      encode(step["inputs"]), encode(step["outputs"]), encode(step["error"]),
                      step["started_at"], step["ended_at"], step["duration_seconds"]))

    def list_runs(self, limit: int = 20) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Run list limit must be between 1 and 100.")
        with closing(self._connect()) as db:
            rows = db.execute("SELECT run_id, model, status, started_at, ended_at, duration_seconds "
                              "FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict:
        """Read a run and its ordered steps; never execute model-generated SQL."""
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise ValueError("Saved workflow run not found.")
            steps = db.execute("SELECT * FROM tool_steps WHERE run_id = ? ORDER BY sequence", (run_id,)).fetchall()
        result = dict(row)
        for field in ["final_report", "error"]:
            value = result.pop(f"{field}_json")
            result[field] = json.loads(value) if value else None
        result["steps"] = []
        for row in steps:
            step = dict(row)
            for field in ["inputs", "outputs", "error"]:
                value = step.pop(f"{field}_json")
                step[field] = json.loads(value) if value else None
            result["steps"].append(step)
        return result

    def read_report(self, run_id: str) -> dict:
        """Return a specific saved result as evidence; no automatic memory injection."""
        run = self.get_run(run_id)
        return {key: run[key] for key in ["run_id", "status", "started_at", "final_output", "final_report", "error"]}

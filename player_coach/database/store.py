from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from player_coach.database.schema import SCHEMA_SQL


class DatabaseStore:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        with self._connect() as conn:
            conn.executescript(SCHEMA_SQL)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ------------------------------------------------------------------ writes

    def save_exchange(self, artifact: dict[str, Any]) -> None:
        rounds = artifact.get("rounds", [])
        approved = 1 if artifact.get("outcome") == "APPROVE" else 0
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO exchanges
                    (run_id, timestamp, strategy_id, symbol, outcome,
                     rounds_taken, approved, total_tokens,
                     constraint_snapshot, portfolio_snapshot,
                     daily_pnl_at_time, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    artifact["run_id"],
                    artifact.get("timestamp"),
                    artifact.get("strategy_id"),
                    artifact.get("symbol"),
                    artifact.get("outcome"),
                    artifact.get("rounds_taken"),
                    approved,
                    artifact.get("total_tokens"),
                    json.dumps(artifact.get("constraint_snapshot")),
                    json.dumps(artifact.get("portfolio_snapshot")),
                    artifact.get("daily_pnl_at_time"),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.execute(
                "DELETE FROM rounds WHERE run_id = ?",
                (artifact["run_id"],),
            )
            for r in rounds:
                evaluation = r.get("evaluation", {})
                proposal = r.get("proposal", {})
                tokens = r.get("tokens_used", {})
                conn.execute(
                    """
                    INSERT INTO rounds
                        (run_id, round_number, proposal, verdict,
                         violations, critique, player_tokens, coach_tokens)
                    VALUES (?,?,?,?,?,?,?,?)
                    """,
                    (
                        artifact["run_id"],
                        r.get("round"),
                        json.dumps(proposal),
                        evaluation.get("decision"),
                        json.dumps(evaluation.get("violations", [])),
                        evaluation.get("feedback"),
                        tokens.get("player"),
                        tokens.get("coach"),
                    ),
                )

    def save_strategy(self, strategy: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO strategies
                    (strategy_id, name, description, constraint_schema,
                     player_prompt_override, created_at)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    strategy["strategy_id"],
                    strategy.get("name"),
                    strategy.get("description"),
                    json.dumps(strategy.get("constraint_schema")),
                    strategy.get("player_prompt_override"),
                    strategy.get("created_at", datetime.now(timezone.utc).isoformat()),
                ),
            )

    def save_portfolio_snapshot(self, snapshot: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_snapshots
                    (strategy_id, snapshot_date, capital, daily_pnl,
                     cumulative_pnl, drawdown_pct, consistency_pct,
                     open_positions, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    snapshot.get("strategy_id"),
                    snapshot.get("snapshot_date"),
                    snapshot.get("capital"),
                    snapshot.get("daily_pnl"),
                    snapshot.get("cumulative_pnl"),
                    snapshot.get("drawdown_pct"),
                    snapshot.get("consistency_pct"),
                    json.dumps(snapshot.get("open_positions", [])),
                    snapshot.get("created_at", datetime.now(timezone.utc).isoformat()),
                ),
            )

    def save_coach_memory(self, entry: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO coach_memory
                    (strategy_id, pattern_type, symbol, observation,
                     confidence, created_at)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    entry.get("strategy_id"),
                    entry.get("pattern_type"),
                    entry.get("symbol"),
                    entry.get("observation"),
                    entry.get("confidence"),
                    entry.get("created_at", datetime.now(timezone.utc).isoformat()),
                ),
            )

    def clear_exchanges(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM rounds")
            conn.execute("DELETE FROM exchanges")

    # ------------------------------------------------------------------ reads

    def get_exchange(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM exchanges WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_exchanges(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM exchanges ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_rounds(self, run_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM rounds WHERE run_id = ? ORDER BY round_number",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_strategies(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM strategies").fetchall()
        return [dict(r) for r in rows]

    def get_portfolio_snapshots(self, strategy_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM portfolio_snapshots WHERE strategy_id = ? ORDER BY snapshot_date",
                (strategy_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_coach_memory(self, strategy_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM coach_memory WHERE strategy_id = ? ORDER BY created_at",
                (strategy_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_memory_patterns(
        self,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions: list[str] = []
        params: list[Any] = []
        if symbol is not None:
            conditions.append("symbol = ?")
            params.append(symbol)
        if strategy_id is not None:
            conditions.append("strategy_id = ?")
            params.append(strategy_id)
        sql = "SELECT * FROM coach_memory"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY created_at"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_approved_runs(
        self, strategy_id: str | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM exchanges WHERE approved = 1"
        params: tuple = ()
        if strategy_id is not None:
            sql += " AND strategy_id = ?"
            params = (strategy_id,)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_patterns(
        self, strategy_id: str | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT symbol, confidence FROM coach_memory"
        params: tuple = ()
        if strategy_id is not None:
            sql += " WHERE strategy_id = ?"
            params = (strategy_id,)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

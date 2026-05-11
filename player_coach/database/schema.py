SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS exchanges (
    run_id              TEXT PRIMARY KEY,
    timestamp           TEXT NOT NULL,
    strategy_id         TEXT,
    symbol              TEXT,
    outcome             TEXT,
    rounds_taken        INTEGER,
    approved            INTEGER,
    total_tokens        INTEGER,
    constraint_snapshot TEXT,
    portfolio_snapshot  TEXT,
    daily_pnl_at_time   REAL,
    created_at          TEXT
);

CREATE TABLE IF NOT EXISTS rounds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT REFERENCES exchanges(run_id),
    round_number    INTEGER,
    proposal        TEXT,
    verdict         TEXT,
    violations      TEXT,
    critique        TEXT,
    player_tokens   INTEGER,
    coach_tokens    INTEGER
);

CREATE TABLE IF NOT EXISTS strategies (
    strategy_id             TEXT PRIMARY KEY,
    name                    TEXT,
    description             TEXT,
    constraint_schema       TEXT,
    player_prompt_override  TEXT,
    created_at              TEXT
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id     TEXT,
    snapshot_date   TEXT,
    capital         REAL,
    daily_pnl       REAL,
    cumulative_pnl  REAL,
    drawdown_pct    REAL,
    consistency_pct REAL,
    open_positions  TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS coach_memory (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id     TEXT,
    pattern_type    TEXT,
    symbol          TEXT,
    observation     TEXT,
    confidence      REAL,
    created_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_rounds_run_id
    ON rounds(run_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_strategy
    ON exchanges(strategy_id);
CREATE INDEX IF NOT EXISTS idx_exchanges_outcome
    ON exchanges(outcome);
CREATE INDEX IF NOT EXISTS idx_snapshots_strategy
    ON portfolio_snapshots(strategy_id);
CREATE INDEX IF NOT EXISTS idx_memory_strategy
    ON coach_memory(strategy_id);
"""

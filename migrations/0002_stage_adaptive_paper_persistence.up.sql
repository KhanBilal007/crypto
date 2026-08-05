CREATE TABLE paper_account_snapshots (
    id TEXT PRIMARY KEY,
    captured_at TEXT NOT NULL,
    market_data_source TEXT NOT NULL,
    cash TEXT NOT NULL,
    base_quantity TEXT NOT NULL,
    average_entry_price TEXT NOT NULL,
    realized_pnl TEXT NOT NULL,
    fees_paid TEXT NOT NULL,
    equity_history_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE paper_transactions (
    id TEXT PRIMARY KEY,
    order_intent_id TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity TEXT NOT NULL,
    price TEXT NOT NULL,
    fee_paid TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (order_intent_id, side, quantity, price, occurred_at)
);

CREATE TABLE paper_strategy_evaluations (
    id TEXT PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    signal_direction TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE paper_risk_decisions (
    id TEXT PRIMARY KEY,
    order_intent_id TEXT,
    status TEXT NOT NULL,
    evaluated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE paper_simulated_fills (
    id TEXT PRIMARY KEY,
    order_intent_id TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity TEXT NOT NULL,
    price TEXT NOT NULL,
    fee_paid TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (order_intent_id, side, quantity, price, occurred_at)
);

CREATE TABLE paper_operator_actions (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    reason TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE paper_preferences (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER paper_account_snapshots_no_update
BEFORE UPDATE ON paper_account_snapshots
BEGIN
    SELECT RAISE(ABORT, 'paper_account_snapshots are append-only');
END;

CREATE TRIGGER paper_account_snapshots_no_delete
BEFORE DELETE ON paper_account_snapshots
BEGIN
    SELECT RAISE(ABORT, 'paper_account_snapshots are append-only');
END;

CREATE TRIGGER paper_transactions_no_update
BEFORE UPDATE ON paper_transactions
BEGIN
    SELECT RAISE(ABORT, 'paper_transactions are append-only');
END;

CREATE TRIGGER paper_transactions_no_delete
BEFORE DELETE ON paper_transactions
BEGIN
    SELECT RAISE(ABORT, 'paper_transactions are append-only');
END;

CREATE TRIGGER paper_strategy_evaluations_no_update
BEFORE UPDATE ON paper_strategy_evaluations
BEGIN
    SELECT RAISE(ABORT, 'paper_strategy_evaluations are append-only');
END;

CREATE TRIGGER paper_strategy_evaluations_no_delete
BEFORE DELETE ON paper_strategy_evaluations
BEGIN
    SELECT RAISE(ABORT, 'paper_strategy_evaluations are append-only');
END;

CREATE TRIGGER paper_risk_decisions_no_update
BEFORE UPDATE ON paper_risk_decisions
BEGIN
    SELECT RAISE(ABORT, 'paper_risk_decisions are append-only');
END;

CREATE TRIGGER paper_risk_decisions_no_delete
BEFORE DELETE ON paper_risk_decisions
BEGIN
    SELECT RAISE(ABORT, 'paper_risk_decisions are append-only');
END;

CREATE TRIGGER paper_simulated_fills_no_update
BEFORE UPDATE ON paper_simulated_fills
BEGIN
    SELECT RAISE(ABORT, 'paper_simulated_fills are append-only');
END;

CREATE TRIGGER paper_simulated_fills_no_delete
BEFORE DELETE ON paper_simulated_fills
BEGIN
    SELECT RAISE(ABORT, 'paper_simulated_fills are append-only');
END;

CREATE TRIGGER paper_operator_actions_no_update
BEFORE UPDATE ON paper_operator_actions
BEGIN
    SELECT RAISE(ABORT, 'paper_operator_actions are append-only');
END;

CREATE TRIGGER paper_operator_actions_no_delete
BEFORE DELETE ON paper_operator_actions
BEGIN
    SELECT RAISE(ABORT, 'paper_operator_actions are append-only');
END;

INSERT INTO schema_migrations (version) VALUES ('0002_stage_adaptive_paper_persistence');

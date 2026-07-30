CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE candles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    pair TEXT NOT NULL,
    interval TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    closed_at TEXT NOT NULL,
    open TEXT NOT NULL,
    high TEXT NOT NULL,
    low TEXT NOT NULL,
    close TEXT NOT NULL,
    volume TEXT NOT NULL,
    data_quality_flags TEXT NOT NULL DEFAULT '{}',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (exchange, pair, interval, opened_at)
);

CREATE TABLE order_book_snapshots (
    id TEXT PRIMARY KEY,
    exchange TEXT NOT NULL,
    pair TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    bids_json TEXT NOT NULL,
    asks_json TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (exchange, pair, captured_at, source_ref)
);

CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    pair TEXT NOT NULL,
    trade_id TEXT NOT NULL,
    traded_at TEXT NOT NULL,
    price TEXT NOT NULL,
    quantity TEXT NOT NULL,
    side TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (exchange, trade_id)
);

CREATE TABLE feature_snapshots (
    id TEXT PRIMARY KEY,
    pair TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    feature_version TEXT NOT NULL,
    inputs_ref TEXT NOT NULL,
    values_json TEXT NOT NULL,
    data_quality_flags TEXT NOT NULL DEFAULT '{}',
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (pair, generated_at, feature_version)
);

CREATE TABLE indicator_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pair TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    indicator_name TEXT NOT NULL,
    indicator_value TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (pair, generated_at, indicator_name, source_ref)
);

CREATE TABLE predictions (
    id TEXT PRIMARY KEY,
    pair TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    horizon TEXT NOT NULL,
    model_version TEXT NOT NULL,
    features_ref TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE signals (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    pair TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    direction TEXT NOT NULL,
    confidence TEXT NOT NULL,
    inputs_ref TEXT NOT NULL,
    prediction_ref TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE risk_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_intent_id TEXT NOT NULL,
    status TEXT NOT NULL,
    allow INTEGER NOT NULL,
    reject INTEGER NOT NULL,
    max_position_size TEXT NOT NULL,
    stop_loss_required INTEGER NOT NULL,
    kill_switch_active INTEGER NOT NULL,
    evaluated_at TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    reasons_json TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_intents (
    id TEXT PRIMARY KEY,
    pair TEXT NOT NULL,
    side TEXT NOT NULL,
    order_type TEXT NOT NULL,
    quantity TEXT NOT NULL,
    limit_price TEXT,
    status TEXT NOT NULL,
    client_order_ref TEXT UNIQUE,
    created_at TEXT NOT NULL,
    signal_json TEXT NOT NULL,
    risk_decision_json TEXT,
    payload_json TEXT NOT NULL,
    created_at_db TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE order_lifecycle_events (
    id TEXT PRIMARY KEY,
    order_intent_id TEXT NOT NULL,
    status TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    realized_pnl TEXT,
    unrealized_pnl TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_intent_id) REFERENCES order_intents (id)
);

CREATE TABLE portfolio_snapshots (
    id TEXT PRIMARY KEY,
    captured_at TEXT NOT NULL,
    source_ref TEXT NOT NULL UNIQUE,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id TEXT NOT NULL,
    asset TEXT NOT NULL,
    quantity TEXT NOT NULL,
    valuation_quote TEXT NOT NULL,
    valuation TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES portfolio_snapshots (id),
    UNIQUE (snapshot_id, asset)
);

CREATE TABLE audit_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    causation_id TEXT,
    correlation_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER audit_events_no_update
BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;

CREATE TRIGGER audit_events_no_delete
BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'audit_events are append-only');
END;

CREATE TRIGGER risk_decisions_no_update
BEFORE UPDATE ON risk_decisions
BEGIN
    SELECT RAISE(ABORT, 'risk_decisions are append-only');
END;

CREATE TRIGGER risk_decisions_no_delete
BEFORE DELETE ON risk_decisions
BEGIN
    SELECT RAISE(ABORT, 'risk_decisions are append-only');
END;

CREATE TRIGGER order_intents_no_update
BEFORE UPDATE ON order_intents
BEGIN
    SELECT RAISE(ABORT, 'order_intents are append-only');
END;

CREATE TRIGGER order_intents_no_delete
BEFORE DELETE ON order_intents
BEGIN
    SELECT RAISE(ABORT, 'order_intents are append-only');
END;

CREATE TRIGGER order_lifecycle_events_no_update
BEFORE UPDATE ON order_lifecycle_events
BEGIN
    SELECT RAISE(ABORT, 'order_lifecycle_events are append-only');
END;

CREATE TRIGGER order_lifecycle_events_no_delete
BEFORE DELETE ON order_lifecycle_events
BEGIN
    SELECT RAISE(ABORT, 'order_lifecycle_events are append-only');
END;

INSERT INTO schema_migrations (version) VALUES ('0001_stage008_storage');

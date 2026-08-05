CREATE TABLE paper_open_orders (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    order_type TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    row_created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES paper_account_snapshots(id)
);

CREATE TABLE paper_alert_rules (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    threshold TEXT NOT NULL,
    expected_value TEXT NOT NULL,
    enabled TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    row_created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES paper_account_snapshots(id)
);

CREATE TABLE paper_journal_entries (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    journal_id TEXT NOT NULL,
    trade_ref TEXT NOT NULL,
    symbol TEXT NOT NULL,
    setup_type TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    row_created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES paper_account_snapshots(id)
);

CREATE TABLE paper_chart_drawings (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    drawing_id TEXT NOT NULL,
    drawing_type TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    start_time TEXT NOT NULL,
    start_price TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    row_created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES paper_account_snapshots(id)
);

CREATE TRIGGER paper_open_orders_no_update
BEFORE UPDATE ON paper_open_orders
BEGIN
    SELECT RAISE(ABORT, 'paper_open_orders are append-only');
END;

CREATE TRIGGER paper_open_orders_no_delete
BEFORE DELETE ON paper_open_orders
BEGIN
    SELECT RAISE(ABORT, 'paper_open_orders are append-only');
END;

CREATE TRIGGER paper_alert_rules_no_update
BEFORE UPDATE ON paper_alert_rules
BEGIN
    SELECT RAISE(ABORT, 'paper_alert_rules are append-only');
END;

CREATE TRIGGER paper_alert_rules_no_delete
BEFORE DELETE ON paper_alert_rules
BEGIN
    SELECT RAISE(ABORT, 'paper_alert_rules are append-only');
END;

CREATE TRIGGER paper_journal_entries_no_update
BEFORE UPDATE ON paper_journal_entries
BEGIN
    SELECT RAISE(ABORT, 'paper_journal_entries are append-only');
END;

CREATE TRIGGER paper_journal_entries_no_delete
BEFORE DELETE ON paper_journal_entries
BEGIN
    SELECT RAISE(ABORT, 'paper_journal_entries are append-only');
END;

CREATE TRIGGER paper_chart_drawings_no_update
BEFORE UPDATE ON paper_chart_drawings
BEGIN
    SELECT RAISE(ABORT, 'paper_chart_drawings are append-only');
END;

CREATE TRIGGER paper_chart_drawings_no_delete
BEFORE DELETE ON paper_chart_drawings
BEGIN
    SELECT RAISE(ABORT, 'paper_chart_drawings are append-only');
END;

INSERT INTO schema_migrations (version) VALUES ('0003_trader_dashboard_structured_state');

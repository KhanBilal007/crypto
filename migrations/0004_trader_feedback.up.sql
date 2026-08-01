CREATE TABLE paper_trader_feedback (
    id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    feedback_id TEXT NOT NULL,
    reviewer_role TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    resolution TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    row_created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (snapshot_id) REFERENCES paper_account_snapshots(id)
);

CREATE TRIGGER paper_trader_feedback_no_update
BEFORE UPDATE ON paper_trader_feedback
BEGIN
    SELECT RAISE(ABORT, 'paper_trader_feedback is append-only');
END;

CREATE TRIGGER paper_trader_feedback_no_delete
BEFORE DELETE ON paper_trader_feedback
BEGIN
    SELECT RAISE(ABORT, 'paper_trader_feedback is append-only');
END;

INSERT INTO schema_migrations (version) VALUES ('0004_trader_feedback');

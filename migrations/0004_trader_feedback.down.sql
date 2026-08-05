DROP TRIGGER IF EXISTS paper_trader_feedback_no_delete;
DROP TRIGGER IF EXISTS paper_trader_feedback_no_update;

DROP TABLE IF EXISTS paper_trader_feedback;

DELETE FROM schema_migrations WHERE version = '0004_trader_feedback';

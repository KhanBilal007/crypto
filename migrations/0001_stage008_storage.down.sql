DROP TRIGGER IF EXISTS order_lifecycle_events_no_delete;
DROP TRIGGER IF EXISTS order_lifecycle_events_no_update;
DROP TRIGGER IF EXISTS order_intents_no_delete;
DROP TRIGGER IF EXISTS order_intents_no_update;
DROP TRIGGER IF EXISTS risk_decisions_no_delete;
DROP TRIGGER IF EXISTS risk_decisions_no_update;
DROP TRIGGER IF EXISTS audit_events_no_delete;
DROP TRIGGER IF EXISTS audit_events_no_update;

DROP TABLE IF EXISTS audit_events;
DROP TABLE IF EXISTS positions;
DROP TABLE IF EXISTS portfolio_snapshots;
DROP TABLE IF EXISTS order_lifecycle_events;
DROP TABLE IF EXISTS order_intents;
DROP TABLE IF EXISTS risk_decisions;
DROP TABLE IF EXISTS signals;
DROP TABLE IF EXISTS predictions;
DROP TABLE IF EXISTS indicator_values;
DROP TABLE IF EXISTS feature_snapshots;
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS order_book_snapshots;
DROP TABLE IF EXISTS candles;

DELETE FROM schema_migrations WHERE version = '0001_stage008_storage';
DROP TABLE IF EXISTS schema_migrations;

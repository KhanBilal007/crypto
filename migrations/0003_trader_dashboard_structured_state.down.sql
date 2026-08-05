DROP TRIGGER IF EXISTS paper_chart_drawings_no_delete;
DROP TRIGGER IF EXISTS paper_chart_drawings_no_update;
DROP TRIGGER IF EXISTS paper_journal_entries_no_delete;
DROP TRIGGER IF EXISTS paper_journal_entries_no_update;
DROP TRIGGER IF EXISTS paper_alert_rules_no_delete;
DROP TRIGGER IF EXISTS paper_alert_rules_no_update;
DROP TRIGGER IF EXISTS paper_open_orders_no_delete;
DROP TRIGGER IF EXISTS paper_open_orders_no_update;

DROP TABLE IF EXISTS paper_chart_drawings;
DROP TABLE IF EXISTS paper_journal_entries;
DROP TABLE IF EXISTS paper_alert_rules;
DROP TABLE IF EXISTS paper_open_orders;

DELETE FROM schema_migrations WHERE version = '0003_trader_dashboard_structured_state';

DROP TRIGGER IF EXISTS paper_operator_actions_no_delete;
DROP TRIGGER IF EXISTS paper_operator_actions_no_update;
DROP TRIGGER IF EXISTS paper_simulated_fills_no_delete;
DROP TRIGGER IF EXISTS paper_simulated_fills_no_update;
DROP TRIGGER IF EXISTS paper_risk_decisions_no_delete;
DROP TRIGGER IF EXISTS paper_risk_decisions_no_update;
DROP TRIGGER IF EXISTS paper_strategy_evaluations_no_delete;
DROP TRIGGER IF EXISTS paper_strategy_evaluations_no_update;
DROP TRIGGER IF EXISTS paper_transactions_no_delete;
DROP TRIGGER IF EXISTS paper_transactions_no_update;
DROP TRIGGER IF EXISTS paper_account_snapshots_no_delete;
DROP TRIGGER IF EXISTS paper_account_snapshots_no_update;

DROP TABLE IF EXISTS paper_preferences;
DROP TABLE IF EXISTS paper_operator_actions;
DROP TABLE IF EXISTS paper_simulated_fills;
DROP TABLE IF EXISTS paper_risk_decisions;
DROP TABLE IF EXISTS paper_strategy_evaluations;
DROP TABLE IF EXISTS paper_transactions;
DROP TABLE IF EXISTS paper_account_snapshots;

DELETE FROM schema_migrations WHERE version = '0002_stage_adaptive_paper_persistence';

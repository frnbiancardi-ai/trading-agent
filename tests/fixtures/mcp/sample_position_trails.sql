-- Seed rows per test_mcp_trail_daemon.py
-- Schema: position_trails(position_id, symbol, direction, timeframe, atr_mult, last_sl, activated_at, last_update_at, active)
INSERT INTO position_trails VALUES (1001, 'EURUSD', 'BUY',  'M15', 2.0, 1.10000, '2026-05-01T08:00:00Z', NULL, 1);
INSERT INTO position_trails VALUES (1002, 'GBPUSD', 'SELL', 'M15', 1.5, 1.27000, '2026-05-01T09:00:00Z', NULL, 1);
INSERT INTO position_trails VALUES (1003, 'EURUSD', 'BUY',  'M15', 2.0, 1.10500, '2026-04-01T08:00:00Z', '2026-04-15T12:00:00Z', 0);

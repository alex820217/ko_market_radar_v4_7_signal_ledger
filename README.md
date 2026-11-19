# KO Market Radar V4.7.2
Main file: `app.py`

## SQLite compatibility fix
V4.7.2 migrates an existing V4.3/V4.4/V4.7 `trades` table in place. It preserves the historical `investment`, `signal_snapshot`, `product_snapshot` and `last_price` columns and adds only the missing Signal-Ledger fields: `signal_id`, `snapshot_verified`, `trade_source`.

Trade inserts use explicit column names discovered from the actual database schema, so older backups remain writable after restore.

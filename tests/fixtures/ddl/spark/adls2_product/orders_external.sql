CREATE EXTERNAL TABLE orders_external (
  id BIGINT NOT NULL COMMENT 'Order id',
  amount DECIMAL(18,2),
  is_active BOOLEAN,
  event_date DATE,
  event_ts TIMESTAMP,
  payload STRUCT<
    source: STRING,
    metrics: STRUCT<count: INT, score: DOUBLE>,
    labels: MAP<STRING, STRING>
  >,
  events ARRAY<STRUCT<event_id: STRING, event_ts: TIMESTAMP>>,
  attributes MAP<STRING, ARRAY<STRUCT<k: STRING, v: STRING>>>,
  raw BINARY
)
USING DELTA
LOCATION 'abfss://silver@mydatalake.dfs.core.windows.net/orders_external';

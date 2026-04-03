CREATE TABLE events (
  event_id STRING NOT NULL,
  event_date DATE,
  source STRING,
  CONSTRAINT pk_events PRIMARY KEY (event_id),
  CONSTRAINT uq_events UNIQUE (source)
)
USING DELTA
COMMENT 'Event fact table'
PARTITIONED BY (event_date);

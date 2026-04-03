CREATE TABLE orders (
  id BIGINT NOT NULL COMMENT 'Order id',
  amount DECIMAL(18,2),
  processed_at TIMESTAMP
)
USING DELTA
COMMENT 'Imported orders table';

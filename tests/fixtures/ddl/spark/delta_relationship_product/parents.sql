CREATE TABLE parents (
  id BIGINT NOT NULL,
  tenant STRING NOT NULL,
  code STRING NOT NULL,
  CONSTRAINT pk_parents PRIMARY KEY (id),
  CONSTRAINT uq_parents UNIQUE (tenant, code)
)
USING DELTA;

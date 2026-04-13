CREATE TABLE children (
  id BIGINT NOT NULL,
  parent_id BIGINT,
  parent_tenant STRING,
  parent_code STRING,
  inline_parent_id BIGINT REFERENCES parents(id),
  CONSTRAINT fk_parent FOREIGN KEY (parent_id) REFERENCES parents(id),
  CONSTRAINT fk_parent_composite FOREIGN KEY (parent_tenant, parent_code) REFERENCES parents(tenant, code)
)
USING DELTA;

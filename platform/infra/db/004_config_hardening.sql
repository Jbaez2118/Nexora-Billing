ALTER TABLE org_config_version ADD COLUMN IF NOT EXISTS snapshot jsonb;
UPDATE org_config_version p SET snapshot = r.result
  FROM recommendation_run r WHERE r.id = p.run_id AND p.snapshot IS NULL;
ALTER TABLE org_config_version ALTER COLUMN snapshot SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS one_proposed_per_run
  ON org_config_version (run_id) WHERE status = 'proposed';
CREATE INDEX IF NOT EXISTS ix_ocv_run ON org_config_version (run_id);

DROP POLICY IF EXISTS tenant_iso ON org_config_version;
CREATE POLICY tenant_iso ON org_config_version
  USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
  WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid);

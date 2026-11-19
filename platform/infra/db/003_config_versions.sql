CREATE TABLE IF NOT EXISTS org_config_version (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  run_id uuid NOT NULL REFERENCES recommendation_run(id),
  version int NOT NULL,
  status text NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','approved','rejected','superseded')),
  proposed_by text NOT NULL, decided_by text, decision_note text,
  created_at timestamptz NOT NULL DEFAULT now(), decided_at timestamptz,
  UNIQUE (tenant_id, version));
CREATE UNIQUE INDEX IF NOT EXISTS one_approved_per_tenant ON org_config_version (tenant_id) WHERE status = 'approved';
ALTER TABLE org_config_version ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_config_version FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_iso ON org_config_version;
CREATE POLICY tenant_iso ON org_config_version
  USING (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
GRANT SELECT, INSERT ON org_config_version TO nexora_app;
GRANT UPDATE (status, decided_by, decision_note, decided_at) ON org_config_version TO nexora_app;

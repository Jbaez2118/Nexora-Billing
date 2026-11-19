CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE ROLE nexora_app LOGIN NOSUPERUSER NOBYPASSRLS;
GRANT CONNECT ON DATABASE nexora TO nexora_app;
GRANT USAGE ON SCHEMA public TO nexora_app;

CREATE TABLE tenant (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE org_unit (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  parent_id uuid REFERENCES org_unit(id),
  kind text NOT NULL CHECK (kind IN ('department','team','branch')),
  name text NOT NULL,
  status text NOT NULL DEFAULT 'active'
);
CREATE INDEX ON org_unit (tenant_id, parent_id);

CREATE TABLE worker_assignment (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  worker_id uuid NOT NULL,
  org_unit_id uuid NOT NULL REFERENCES org_unit(id),
  position text NOT NULL,
  valid_during tstzrange NOT NULL,
  EXCLUDE USING gist (tenant_id WITH =, worker_id WITH =, org_unit_id WITH =, position WITH =, valid_during WITH &&)
);

CREATE TABLE outbox (
  id bigserial PRIMARY KEY, tenant_id uuid NOT NULL, topic text NOT NULL,
  payload jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), published_at timestamptz
);
CREATE INDEX ON outbox (id) WHERE published_at IS NULL;

CREATE TABLE audit_event (
  id bigserial, tenant_id uuid NOT NULL, actor text NOT NULL, action text NOT NULL,
  detail jsonb, at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (id, at)
) PARTITION BY RANGE (at);
CREATE TABLE audit_event_default PARTITION OF audit_event DEFAULT;

DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['org_unit','worker_assignment','outbox','audit_event'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY tenant_iso ON %I USING (tenant_id = current_setting(''app.tenant_id'')::uuid) WITH CHECK (tenant_id = current_setting(''app.tenant_id'')::uuid)', t);
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE, DELETE ON org_unit, worker_assignment, outbox TO nexora_app;
GRANT SELECT, INSERT ON audit_event, audit_event_default TO nexora_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO nexora_app;


CREATE TABLE IF NOT EXISTS capability (
  id text PRIMARY KEY, name text NOT NULL, module text NOT NULL, description text NOT NULL);
CREATE TABLE IF NOT EXISTS capability_dependency (
  capability_id text REFERENCES capability(id), requires_id text REFERENCES capability(id),
  PRIMARY KEY (capability_id, requires_id));
CREATE TABLE IF NOT EXISTS industry_template (
  id text NOT NULL, version int NOT NULL, name text NOT NULL, definition jsonb NOT NULL,
  PRIMARY KEY (id, version));

CREATE TABLE IF NOT EXISTS business_profile (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  industry text NOT NULL,
  workforce int NOT NULL CHECK (workforce >= 1),
  branches int NOT NULL DEFAULT 1 CHECK (branches >= 1),
  registers int NOT NULL DEFAULT 1,
  orders_per_day int NOT NULL DEFAULT 0,
  sku_count int NOT NULL DEFAULT 0,
  has_delivery boolean NOT NULL DEFAULT false,
  has_returns boolean NOT NULL DEFAULT false,
  has_production boolean NOT NULL DEFAULT false,
  perishables boolean NOT NULL DEFAULT false,
  risk_level text NOT NULL DEFAULT 'low' CHECK (risk_level IN ('low','medium','high')),
  growth_workforce_pct int, growth_branches int,
  created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS business_profile_tenant ON business_profile (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS recommendation_run (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id uuid NOT NULL REFERENCES tenant(id),
  profile_id uuid NOT NULL REFERENCES business_profile(id),
  ruleset_version text NOT NULL, template_id text NOT NULL, template_version int NOT NULL,
  result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS recommendation_run_tenant ON recommendation_run (tenant_id, created_at DESC);

DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['business_profile','recommendation_run'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS tenant_iso ON %I', t);
    EXECUTE format('CREATE POLICY tenant_iso ON %I USING (tenant_id = current_setting(''app.tenant_id'')::uuid) WITH CHECK (tenant_id = current_setting(''app.tenant_id'')::uuid)', t);
  END LOOP;
END $$;

INSERT INTO capability(id,name,module,description) VALUES
('pos','Punto de venta','sales','Cajas, turnos y ventas en mostrador'),
('billing','Facturación','sales','Facturas, cobros y recibos'),
('customers','Clientes','sales','Fichas de clientes y cuentas'),
('cash_close','Cierre de caja','sales','Apertura/cierre y arqueo'),
('inventory','Inventario','inventory','Artículos, stock y ajustes'),
('purchasing','Compras','procurement','Órdenes de compra y recepción'),
('suppliers','Proveedores','procurement','Fichas y evaluación de proveedores'),
('returns','Devoluciones','sales','Autorización, inspección y reembolso'),
('customer_service','Atención al cliente','crm','Casos y reclamos'),
('staff_scheduling','Turnos de personal','hr','Horarios y asistencia'),
('hr','Recursos humanos','hr','Registros de trabajadores y contratos'),
('payroll','Nómina','hr','Períodos, deducciones y aprobaciones'),
('accounting','Contabilidad','finance','Libro mayor, cuentas por pagar/cobrar'),
('treasury','Tesorería','finance','Bancos, flujo de caja y conciliación'),
('audit_controls','Auditoría y controles','governance','Revisiones y registro de excepciones'),
('multi_branch','Multi-sucursal','operations','Sucursales y alcance por sede'),
('stock_transfers','Transferencias de stock','inventory','Movimientos entre sedes y almacenes'),
('warehousing','Almacén','inventory','Recepción, picking y despacho'),
('delivery','Entrega a domicilio','logistics','Despacho, asignación y prueba de entrega'),
('fleet','Flota','logistics','Vehículos, conductores y mantenimiento'),
('quotes_orders','Cotizaciones y pedidos','sales','Cotizaciones, pedidos y precios por volumen'),
('traceability','Trazabilidad y lotes','inventory','Lotes, vencimientos y rastreo'),
('production','Producción','manufacturing','Órdenes de producción y consumo de materiales'),
('loyalty','Fidelización','crm','Promociones y programas de lealtad'),
('reporting','Reportes','analytics','Indicadores y reportes de gestión')
ON CONFLICT (id) DO NOTHING;

INSERT INTO capability_dependency(capability_id,requires_id) VALUES
('pos','billing'),('billing','customers'),('cash_close','pos'),('purchasing','suppliers'),
('purchasing','inventory'),('returns','inventory'),('returns','billing'),('stock_transfers','inventory'),
('stock_transfers','multi_branch'),('warehousing','inventory'),('delivery','billing'),('delivery','customers'),
('fleet','delivery'),('payroll','hr'),('staff_scheduling','hr'),('accounting','billing'),
('treasury','accounting'),('audit_controls','accounting'),('traceability','inventory'),
('production','inventory'),('quotes_orders','customers')
ON CONFLICT DO NOTHING;

INSERT INTO industry_template(id,version,name,definition) VALUES
('retail_general',1,'Comercio minorista general','{"required":["pos","billing","customers","inventory","cash_close"],"recommended":["purchasing","suppliers","returns","reporting"],"optional":["loyalty","delivery","customer_service","staff_scheduling"],"org_pattern":["Operaciones","Ventas y caja","Compras e inventario","Administración"]}'),
('wholesale',1,'Mayorista y distribución','{"required":["quotes_orders","billing","customers","inventory","purchasing","suppliers"],"recommended":["warehousing","accounting","returns","reporting"],"optional":["delivery","fleet","treasury","audit_controls"],"org_pattern":["Ventas comerciales","Compras","Almacén y logística","Finanzas"]}')
ON CONFLICT (id,version) DO NOTHING;

GRANT SELECT ON capability, capability_dependency, industry_template TO nexora_app;
GRANT SELECT, INSERT ON business_profile, recommendation_run TO nexora_app;

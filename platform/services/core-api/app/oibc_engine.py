RULESET = "oibc-rules-1.0.0"
RANK = {"future": 0, "optional": 1, "recommended": 2, "required": 3}

def evaluate(p, templates, caps, deps):
    items, assumptions = {}, []
    tid = p["industry"] if p["industry"] in templates else "retail_general"
    if tid != p["industry"]:
        assumptions.append(f"No existe plantilla para '{p['industry']}'; se usó '{tid}' como base.")
    tpl = templates[tid]
    d = tpl["definition"]

    def add(cap, cls, why, signal=None):
        if cap not in caps:
            return
        it = items.setdefault(cap, {"classification": cls, "rationale": [], "signals": []})
        if RANK[cls] > RANK[it["classification"]]:
            it["classification"] = cls
        if why not in it["rationale"]:
            it["rationale"].append(why)
        if signal and signal not in it["signals"]:
            it["signals"].append(signal)

    for cls in ("required", "recommended", "optional"):
        for c in d.get(cls, []):
            add(c, cls, f"Plantilla {tpl['name']} v{tpl['version']}", f"industry={tid}")

    w, br = p["workforce"], p["branches"]
    if w >= 9:
        add("staff_scheduling", "recommended", f"{w} trabajadores: conviene coordinar turnos", "workforce")
    if w >= 21:
        add("hr", "recommended", "Desde ~21 trabajadores conviene separar la gestión de personal", "workforce")
        add("accounting", "recommended", "El volumen administrativo justifica contabilidad", "workforce")
    if w >= 51:
        add("payroll", "recommended", "Con 51+ trabajadores la nómina formal reduce errores", "workforce")
        add("audit_controls", "recommended", "Estructura mayor: conviene revisión independiente", "workforce")
    if br >= 2:
        add("multi_branch", "required", f"{br} sucursales declaradas", "branches")
        add("stock_transfers", "required", "Varias sedes requieren mover stock entre ellas", "branches")
        add("reporting", "recommended", "Reportes consolidados por sucursal", "branches")
    if p["has_delivery"]:
        add("delivery", "required", "Declara entregas a domicilio", "has_delivery")
        if p["orders_per_day"] >= 100:
            add("fleet", "recommended", "Volumen alto de pedidos con entregas", "orders_per_day")
        else:
            add("fleet", "optional", "Evalúe flota si crece el volumen de entregas", "orders_per_day")
    if p["has_returns"]:
        add("returns", "required", "Declara devoluciones", "has_returns")
    if p["has_production"]:
        add("production", "required", "Declara producción", "has_production")
        add("traceability", "recommended", "La producción exige rastrear materiales y lotes", "has_production")
    if p["perishables"]:
        add("traceability", "required", "Productos perecederos: lotes y vencimientos", "perishables")
    if p["risk_level"] == "high":
        add("audit_controls", "required", "Riesgo alto: prevalece sobre el tamaño de la plantilla", "risk_level")
        add("accounting", "required", "Riesgo alto: se requieren controles financieros", "risk_level")
    elif p["risk_level"] == "medium":
        add("audit_controls", "recommended", "Riesgo medio: controles recomendados", "risk_level")
    if p["orders_per_day"] >= 200:
        add("warehousing", "recommended", "Alto volumen de pedidos diarios", "orders_per_day")
        add("reporting", "recommended", "Alto volumen: se necesita seguimiento", "orders_per_day")
    if p["registers"] >= 3:
        add("cash_close", "required", f"{p['registers']} cajas: cierre y arqueo por caja", "registers")

    gb = p.get("growth_branches") or 0
    gw = p.get("growth_workforce_pct") or 0
    if gb >= 1:
        for c in ("multi_branch", "stock_transfers"):
            if c not in items:
                add(c, "future", f"Plan de crecimiento: +{gb} sucursal(es)", "growth_branches")
    if gw >= 50:
        for c in ("hr", "payroll"):
            if c not in items:
                add(c, "future", f"Plan de crecimiento: +{gw}% de personal", "growth_workforce_pct")

    changed = True
    while changed:
        changed = False
        for cap, it in list(items.items()):
            if it["classification"] in ("optional", "future"):
                continue
            for r in deps.get(cap, []):
                before = items.get(r, {}).get("classification")
                add(r, it["classification"], f"Dependencia de {caps[cap]['name']}", f"dep:{cap}")
                if r in items and before != items[r]["classification"]:
                    changed = True

    out = []
    for cap, it in sorted(items.items(), key=lambda kv: (-RANK[kv[1]["classification"]], kv[0])):
        out.append({
            "capability_id": cap, "name": caps[cap]["name"], "module": caps[cap]["module"],
            "classification": it["classification"], "rationale": it["rationale"], "signals": it["signals"],
            "prerequisites": deps.get(cap, []),
            "in_current_proposal": it["classification"] in ("required", "recommended"),
            "requires_entitlement": True,
        })

    if p["orders_per_day"] == 0:
        assumptions.append("No se declaró volumen de pedidos por día; no se evaluó la carga operativa.")
    assumptions.append("Las recomendaciones son orientativas y no constituyen asesoría legal ni garantizan cumplimiento normativo.")
    assumptions.append("Activar cualquier capacidad requiere aprobación del cliente y derechos de uso vigentes.")

    if w <= 8:
        stage, note = "micro", "Estructura combinada: una persona puede asumir varias funciones; no se requieren departamentos separados."
    elif w <= 20:
        stage, note = "pequeña", "Propietario o gerente con uno o más responsables operativos."
    elif w <= 50:
        stage, note = "mediana", "Responsables funcionales separados (finanzas, personal, compras e inventario)."
    elif w <= 150:
        stage, note = "grande", "Departamentos formales y cadenas de aprobación."
    else:
        stage, note = "empresa", "Servicios compartidos y estructuras regionales o por sucursal."
    units, extra = _units(w, d)
    if br >= 2:
        units += [f"Sucursales ({br})", "Servicios compartidos (administración central)"]
    notes = [note, "Las bandas por personal son heurísticas; el riesgo y la complejidad pueden exigir más controles.", *extra]
    if w >= 21 or p["risk_level"] == "high":
        notes.append("Separe funciones sensibles: aprobar y ejecutar pagos, ajustes de inventario y nómina.")

    return {"ruleset_version": RULESET,
            "template": {"id": tid, "version": tpl["version"], "name": tpl["name"]},
            "items": out, "assumptions": assumptions,
            "org": {"stage": stage, "units": units, "notes": notes}}



def _units(w, d):
    pattern = d.get("org_pattern", [])
    if w <= 8:
        return ["Dirección y operación (funciones combinadas)"], []
    if w <= 20:
        return ["Dirección y administración", "Operación y ventas"], [
            "Las áreas de la plantilla (" + ", ".join(pattern) + ") pueden asignarse como responsabilidades, sin crear departamentos."]
    return list(pattern), []

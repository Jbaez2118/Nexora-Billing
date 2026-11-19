import json, os, uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from .auth import current_claims, current_tenant
from .db import tenant_tx

REQUIRE_FOUR_EYES = os.getenv("REQUIRE_FOUR_EYES", "false").lower() in ("1", "true", "yes")

router = APIRouter(prefix="/oibc", tags=["oibc-config"])

async def db(tenant=Depends(current_tenant)):
    async with tenant_tx(tenant) as s:
        yield s

class Decision(BaseModel):
    note: str | None = Field(None, max_length=500)

def actor(c: dict) -> str:
    return c.get("preferred_username") or c.get("sub", "desconocido")

def require_admin(c: dict = Depends(current_claims)) -> dict:
    if "org_admin" not in (c.get("realm_access") or {}).get("roles", []):
        raise HTTPException(403, "requiere el rol org_admin")
    return c

def _j(v):
    return json.loads(v) if isinstance(v, str) else v

def _iso(d):
    return d.isoformat() if d else None

async def _lock(s, tenant):
    # Serializa propuestas y decisiones por tenant; se libera al terminar la transacción
    await s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"ocv:{tenant}"})

async def audit(s, tenant, who, action, detail):
    await s.execute(text(
        "INSERT INTO audit_event(tenant_id, actor, action, detail) VALUES (:t, :a, :ac, CAST(:d AS jsonb))"),
        {"t": tenant, "a": who, "ac": action, "d": json.dumps(detail)})

@router.post("/runs/{run_id}/proposal")
async def propose(run_id: uuid.UUID, tenant=Depends(current_tenant), c=Depends(current_claims), s=Depends(db)):
    await _lock(s, tenant)
    if not (await s.execute(text("SELECT 1 FROM recommendation_run WHERE id=:r"), {"r": run_id})).first():
        raise HTTPException(404, "evaluación no encontrada")
    ex = (await s.execute(text(
        "SELECT id, version FROM org_config_version WHERE run_id=:r AND status='proposed'"), {"r": run_id})).first()
    if ex:
        return {"proposal_id": str(ex.id), "version": ex.version, "status": "proposed"}
    ver = (await s.execute(text("SELECT COALESCE(MAX(version),0)+1 FROM org_config_version"))).scalar_one()
    pid = (await s.execute(text(
        "INSERT INTO org_config_version(tenant_id, run_id, version, proposed_by, snapshot) "
        "SELECT CAST(:t AS uuid), id, CAST(:v AS int), CAST(:a AS text), result "
        "FROM recommendation_run WHERE id = :r RETURNING id"),
        {"t": str(tenant), "r": run_id, "v": ver, "a": actor(c)})).scalar_one()
    await audit(s, tenant, actor(c), "config.proposed", {"proposal_id": str(pid), "version": ver, "run_id": str(run_id)})
    return {"proposal_id": str(pid), "version": ver, "status": "proposed"}

async def _decide(pid, status, body, tenant, c, s):
    await _lock(s, tenant)
    row = (await s.execute(text(
        "SELECT id, status, version, proposed_by FROM org_config_version WHERE id=:p FOR UPDATE"), {"p": pid})).first()
    if not row:
        raise HTTPException(404, "propuesta no encontrada")
    if row.status != "proposed":
        raise HTTPException(409, f"la propuesta está en estado '{row.status}'")
    if REQUIRE_FOUR_EYES and row.proposed_by == actor(c):
        raise HTTPException(403, "el aprobador debe ser distinto del proponente")
    if status == "approved":
        await s.execute(text("UPDATE org_config_version SET status='superseded' WHERE status='approved'"))
    await s.execute(text(
        "UPDATE org_config_version SET status=:st, decided_by=:a, decided_at=now(), decision_note=:n WHERE id=:p"),
        {"st": status, "a": actor(c), "n": body.note if body else None, "p": pid})
    await audit(s, tenant, actor(c), f"config.{status}", {"proposal_id": str(pid), "version": row.version, "note": body.note if body else None})
    return {"proposal_id": str(pid), "version": row.version, "status": status, "entitlements_activated": False}

@router.post("/proposals/{pid}/approve")
async def approve(pid: uuid.UUID, body: Decision | None = None, tenant=Depends(current_tenant), c=Depends(require_admin), s=Depends(db)):
    return await _decide(pid, "approved", body, tenant, c, s)

@router.post("/proposals/{pid}/reject")
async def reject(pid: uuid.UUID, body: Decision | None = None, tenant=Depends(current_tenant), c=Depends(require_admin), s=Depends(db)):
    return await _decide(pid, "rejected", body, tenant, c, s)

def _row(r, with_result=False):
    d = {"id": str(r.id), "version": r.version, "status": r.status, "proposed_by": r.proposed_by,
         "decided_by": r.decided_by, "decision_note": r.decision_note,
         "created_at": _iso(r.created_at), "decided_at": _iso(r.decided_at)}
    if with_result:
        d["result"] = _j(r.result)
    return d

_Q = ("SELECT p.id, p.version, p.status, p.proposed_by, p.decided_by, p.decision_note, "
      "p.created_at, p.decided_at, p.snapshot AS result FROM org_config_version p ")

@router.get("/config")
async def current_config(s=Depends(db)):
    rows = (await s.execute(text(_Q + "WHERE p.status IN ('approved','proposed') ORDER BY p.version DESC"))).all()
    return {"approved": next((_row(r, True) for r in rows if r.status == "approved"), None),
            "proposed": [_row(r, True) for r in rows if r.status == "proposed"]}

@router.get("/config/history")
async def history(s=Depends(db)):
    rows = (await s.execute(text(_Q + "ORDER BY p.version DESC"))).all()
    return [_row(r) for r in rows]

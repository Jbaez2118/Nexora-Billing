import json
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from .auth import current_tenant
from .db import tenant_session
from .oibc_engine import evaluate, RULESET

router = APIRouter(prefix="/oibc", tags=["oibc"])

async def db(tenant=Depends(current_tenant)):
    async for s in tenant_session(tenant):
        yield s

class Profile(BaseModel):
    industry: str = Field(min_length=1, max_length=60)
    workforce: int = Field(ge=1, le=100000)
    branches: int = Field(1, ge=1, le=10000)
    registers: int = Field(1, ge=0, le=10000)
    orders_per_day: int = Field(0, ge=0, le=10000000)
    sku_count: int = Field(0, ge=0, le=100000000)
    has_delivery: bool = False
    has_returns: bool = False
    has_production: bool = False
    perishables: bool = False
    risk_level: Literal["low", "medium", "high"] = "low"
    growth_workforce_pct: int | None = Field(None, ge=0, le=1000)
    growth_branches: int | None = Field(None, ge=0, le=1000)

def _j(v):
    return json.loads(v) if isinstance(v, str) else v

async def _catalog(s):
    caps = {r.id: {"name": r.name, "module": r.module}
            for r in (await s.execute(text("SELECT id, name, module FROM capability"))).all()}
    deps = {}
    for r in (await s.execute(text("SELECT capability_id, requires_id FROM capability_dependency"))).all():
        deps.setdefault(r.capability_id, []).append(r.requires_id)
    templates = {r.id: {"version": r.version, "name": r.name, "definition": _j(r.definition)}
                 for r in (await s.execute(text(
                     "SELECT DISTINCT ON (id) id, version, name, definition FROM industry_template ORDER BY id, version DESC"))).all()}
    return caps, deps, templates

@router.post("/assessments")
async def create_assessment(p: Profile, tenant=Depends(current_tenant), s=Depends(db)):
    caps, deps, templates = await _catalog(s)
    data = p.model_dump()
    result = evaluate(data, templates, caps, deps)
    pid = (await s.execute(text(
        "INSERT INTO business_profile(tenant_id, industry, workforce, branches, registers, orders_per_day, sku_count,"
        " has_delivery, has_returns, has_production, perishables, risk_level, growth_workforce_pct, growth_branches)"
        " VALUES (:tenant, :industry, :workforce, :branches, :registers, :orders_per_day, :sku_count,"
        " :has_delivery, :has_returns, :has_production, :perishables, :risk_level, :growth_workforce_pct, :growth_branches)"
        " RETURNING id"), {**data, "tenant": tenant})).scalar_one()
    rid = (await s.execute(text(
        "INSERT INTO recommendation_run(tenant_id, profile_id, ruleset_version, template_id, template_version, result)"
        " VALUES (:tenant, :pid, :rv, :ti, :tv, CAST(:r AS jsonb)) RETURNING id"),
        {"tenant": tenant, "pid": pid, "rv": RULESET, "ti": result["template"]["id"],
         "tv": result["template"]["version"], "r": json.dumps(result)})).scalar_one()
    await s.flush()
    return {"profile_id": str(pid), "run_id": str(rid), "result": result}

@router.get("/assessments/latest")
async def latest(s=Depends(db)):
    row = (await s.execute(text(
        "SELECT id, profile_id, created_at, result FROM recommendation_run ORDER BY created_at DESC LIMIT 1"))).first()
    if not row:
        raise HTTPException(404, "sin evaluaciones")
    return {"run_id": str(row.id), "profile_id": str(row.profile_id),
            "created_at": row.created_at.isoformat(), "result": _j(row.result)}

from fastapi import FastAPI, Depends
from sqlalchemy import text
from .auth import current_tenant
from .db import tenant_session

app = FastAPI(title="NexoraBilling Core API", version="0.2.0")

async def db(tenant=Depends(current_tenant)):
    async for s in tenant_session(tenant):
        yield s

@app.get("/health")
async def health(): return {"status": "ok"}

@app.get("/org/units")
async def list_units(s=Depends(db)):
    rows = await s.execute(text("SELECT id, parent_id, kind, name FROM org_unit WHERE status='active'"))
    return [dict(r._mapping) for r in rows]

from .oibc import router as oibc_router
app.include_router(oibc_router)

from .oibc_config import router as oibc_config_router
app.include_router(oibc_config_router)


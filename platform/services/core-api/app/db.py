import os, uuid
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

# PgBouncer en modo transaction: sin cache de prepared statements
engine = create_async_engine(os.environ["DATABASE_URL"], pool_size=10, connect_args={"statement_cache_size": 0})
Session = async_sessionmaker(engine, expire_on_commit=False)

async def tenant_session(tenant_id: uuid.UUID):
    async with Session() as s, s.begin():
        await s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        yield s

from contextlib import asynccontextmanager

@asynccontextmanager
async def tenant_tx(tenant_id: uuid.UUID):
    """Como tenant_session, pero con rollback inmediato si la ruta lanza una excepción."""
    async with Session() as s, s.begin():
        await s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        yield s

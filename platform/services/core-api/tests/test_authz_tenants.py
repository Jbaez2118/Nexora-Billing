import os, subprocess, uuid
from pathlib import Path
import httpx, pytest

KC = os.getenv("KC_TOKEN_URL", "http://localhost:8081/realms/nexora/protocol/openid-connect/token")
API = os.getenv("API_URL", "http://localhost:8080/api")
INFRA = Path(__file__).resolve().parents[3] / "infra"

def _psql(*cmds):
    args = ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "nexora", "-tA"]
    for c in cmds:
        args += ["-c", c]
    return subprocess.run(args, cwd=INFRA, capture_output=True, text=True)

def _hd(user, pw_env):
    r = httpx.post(KC, data={"client_id": "nexora-app", "grant_type": "password",
                             "username": user, "password": os.environ[pw_env]})
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}

@pytest.fixture(scope="module")
def viewer():
    return _hd("viewer", "VIEWER_PASSWORD")

@pytest.fixture(scope="module")
def admin():
    return _hd(os.getenv("TEST_USER", "demo"), "TEST_PASSWORD")

def test_sin_token_da_401():
    assert httpx.get(f"{API}/oibc/config").status_code == 401

def test_viewer_no_puede_aprobar_ni_rechazar(viewer, admin):
    run = httpx.get(f"{API}/oibc/assessments/latest", headers=admin).json()["run_id"]
    r = httpx.post(f"{API}/oibc/runs/{run}/proposal", headers=admin)
    assert r.status_code == 200, r.text
    pid = r.json()["proposal_id"]
    assert httpx.post(f"{API}/oibc/proposals/{pid}/approve", headers=viewer).status_code == 403
    assert httpx.post(f"{API}/oibc/proposals/{pid}/reject", headers=viewer).status_code == 403

def test_aislamiento_entre_tenants():
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    try:
        r = _psql(f"INSERT INTO tenant(id, name) VALUES ('{a}','test-A'), ('{b}','test-B')")
        assert r.returncode == 0, r.stderr
        r = _psql("SET ROLE nexora_app",
                  f"SELECT set_config('app.tenant_id','{b}',false)",
                  "SELECT count(*) FROM org_config_version")
        assert r.stdout.strip().splitlines()[-1] == "0"
        r = _psql("SET ROLE nexora_app",
                  f"SELECT set_config('app.tenant_id','{a}',false)",
                  f"INSERT INTO audit_event(tenant_id, actor, action, detail) VALUES ('{b}','x','x','{{}}'::jsonb)")
        assert "row-level security" in r.stderr  # WITH CHECK impide escribir en otro tenant
    finally:
        _psql(f"DELETE FROM tenant WHERE id IN ('{a}','{b}')")

def test_audit_event_es_append_only():
    for sql in ("UPDATE audit_event SET actor='x'", "DELETE FROM audit_event"):
        assert "append-only" in _psql(sql).stderr


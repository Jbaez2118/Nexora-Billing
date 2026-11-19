import os, subprocess, concurrent.futures as cf
from pathlib import Path
import httpx, pytest

KC = os.getenv("KC_TOKEN_URL", "http://localhost:8081/realms/nexora/protocol/openid-connect/token")
API = os.getenv("API_URL", "http://localhost:8080/api")
INFRA = Path(__file__).resolve().parents[3] / "infra"

def _token():
    r = httpx.post(KC, data={"client_id": "nexora-app", "grant_type": "password",
                             "username": os.getenv("TEST_USER", "demo"), "password": os.environ["TEST_PASSWORD"]})
    r.raise_for_status()
    return r.json()["access_token"]

def _psql(*cmds):
    args = ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "nexora", "-tA"]
    for c in cmds:
        args += ["-c", c]
    return subprocess.run(args, cwd=INFRA, capture_output=True, text=True)

@pytest.fixture(scope="module")
def hd():
    return {"Authorization": f"Bearer {_token()}"}

@pytest.fixture()
def run_id(hd):
    r = httpx.get(f"{API}/oibc/assessments/latest", headers=hd)
    if r.status_code != 200:
        pytest.skip("genera una evaluación primero")
    return r.json()["run_id"]

def _propose(hd, run_id):
    r = httpx.post(f"{API}/oibc/runs/{run_id}/proposal", headers=hd)
    assert r.status_code == 200
    return r.json()["proposal_id"]

def test_propose_es_idempotente(hd, run_id):
    assert _propose(hd, run_id) == _propose(hd, run_id)

def test_doble_aprobacion_concurrente(hd, run_id):
    pid = _propose(hd, run_id)
    def go(_):
        return httpx.post(f"{API}/oibc/proposals/{pid}/approve", headers=hd, json={"note": "t"}, timeout=30).status_code
    with cf.ThreadPoolExecutor(2) as ex:
        codes = sorted(ex.map(go, range(2)))
    assert codes == [200, 409]

def test_una_sola_aprobada(hd):
    h = httpx.get(f"{API}/oibc/config/history", headers=hd).json()
    assert sum(v["status"] == "approved" for v in h) == 1

def test_decidir_dos_veces_da_409(hd, run_id):
    pid = _propose(hd, run_id)
    assert httpx.post(f"{API}/oibc/proposals/{pid}/reject", headers=hd, json={"note": "t"}).status_code == 200
    assert httpx.post(f"{API}/oibc/proposals/{pid}/reject", headers=hd).status_code == 409

def test_snapshot_inmutable_para_la_app():
    r = _psql("SET ROLE nexora_app", "UPDATE org_config_version SET snapshot='{}'::jsonb")
    assert "permission denied" in r.stderr

def test_rls_falla_cerrado_sin_tenant():
    r = _psql("SET ROLE nexora_app", "SELECT count(*) FROM org_config_version")
    assert r.stdout.strip().splitlines()[-1] == "0"

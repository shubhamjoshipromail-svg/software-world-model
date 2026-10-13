"""Invoice Ninja environment: API client, DB access, snapshot/restore."""
import os, subprocess, requests
from dotenv import dotenv_values

HERE = os.path.dirname(os.path.abspath(__file__))
# Multiple identical instances can run in parallel: SWM_IN_INST=1 (default) or 2
INST = os.environ.get("SWM_IN_INST", "1")
ENV_DIR = os.path.join(HERE, "..", "envs", "invoiceninja" if INST == "1" else f"invoiceninja{INST}")
CFG = dotenv_values(os.path.join(ENV_DIR, ".env"))
BASE = {"1": "http://localhost:8012", "2": "http://localhost:8014"}[INST]
DB_PORT = {"1": 33061, "2": 33063}[INST]
PROJECT = "swm-in" if INST == "1" else f"swm-in{INST}"


class API:
    def __init__(self):
        r = requests.post(f"{BASE}/api/v1/login",
                          json={"email": CFG["IN_USER_EMAIL"], "password": CFG["IN_PASSWORD"]},
                          headers={"X-Requested-With": "XMLHttpRequest", "Content-Type": "application/json"},
                          timeout=60)
        r.raise_for_status()
        self.token = r.json()["data"][0]["token"]["token"]
        self.h = {"X-API-TOKEN": self.token, "X-Requested-With": "XMLHttpRequest",
                  "Content-Type": "application/json"}

    def get(self, path, **params):
        r = requests.get(f"{BASE}/api/v1/{path}", headers=self.h, params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    def post(self, path, body, **params):
        r = requests.post(f"{BASE}/api/v1/{path}", headers=self.h, json=body, params=params, timeout=120)
        if not r.ok:
            raise RuntimeError(f"{path}: {r.status_code} {r.text[:300]}")
        return r.json()


def _mysql_args():
    return ["docker", "compose", "-p", PROJECT, "exec", "-T", "mysql"]


def sql(query):
    """Run a read query, return rows as list of dicts."""
    out = subprocess.run(_mysql_args() + ["mysql", "-u" + CFG["DB_USERNAME"], "-p" + CFG["DB_PASSWORD"],
                         CFG["DB_DATABASE"], "--batch", "-e", query],
                         cwd=ENV_DIR, capture_output=True, text=True, check=True).stdout
    lines = out.rstrip("\n").split("\n")
    if not lines or not lines[0]:
        return []
    cols = lines[0].split("\t")
    return [dict(zip(cols, l.split("\t"))) for l in lines[1:]]


SNAP_DIR = os.path.join(HERE, "..", "snapshots")


def _run(cmd, **kw):
    return subprocess.run(cmd, cwd=ENV_DIR, check=True, **kw)


def snapshot(name):
    """Dump the full DB to snapshots/<name>.sql.gz."""
    os.makedirs(SNAP_DIR, exist_ok=True)
    path = os.path.join(SNAP_DIR, f"in_{name}.sql.gz")
    with open(path, "wb") as f:
        dump = subprocess.Popen(_mysql_args() + ["sh", "-c",
            'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --skip-lock-tables "$MYSQL_DATABASE" | gzip -1'],
            cwd=ENV_DIR, stdout=f)
        assert dump.wait() == 0, "mysqldump failed"
    return path


def restore(name):
    """Restore DB from snapshot and flush redis cache so the app sees a clean state."""
    path = os.path.join(SNAP_DIR, f"in_{name}.sql.gz")
    with open(path, "rb") as f:
        p = subprocess.Popen(_mysql_args() + ["sh", "-c",
            'gunzip | mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"'],
            cwd=ENV_DIR, stdin=f)
        assert p.wait() == 0, "restore failed"
    _run(["docker", "compose", "-p", PROJECT, "exec", "-T", "redis", "redis-cli", "FLUSHALL"], capture_output=True)

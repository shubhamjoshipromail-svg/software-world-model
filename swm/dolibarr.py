"""Dolibarr 22 environment: API client, DB access, snapshot/restore."""
import os, subprocess, time, requests
from dotenv import dotenv_values

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_DIR = os.path.join(HERE, "..", "envs", "dolibarr")
CFG = dotenv_values(os.path.join(ENV_DIR, ".env"))
BASE = "http://localhost:8015"
PROJECT = "swm-dl"
DB_PORT = 33064
SNAP_DIR = os.path.join(HERE, "..", "snapshots")


class API:
    def __init__(self):
        r = requests.get(f"{BASE}/api/index.php/login", params={"login": CFG["DOLI_ADMIN_LOGIN"], "password": CFG["DOLI_ADMIN_PASSWORD"]},
                         headers={"Accept": "application/json"}, timeout=60)
        r.raise_for_status()
        self.h = {"DOLAPIKEY": r.json()["success"]["token"], "Accept": "application/json"}

    def _req(self, method, path, **kw):
        r = requests.request(method, f"{BASE}/api/index.php/{path}", headers=self.h, timeout=120, **kw)
        if not r.ok:
            raise RuntimeError(f"{method} {path}: {r.status_code} {r.text[:300]}")
        return r.json() if r.text else None

    def get(self, path, **params):
        return self._req("GET", path, params=params)

    def post(self, path, body=None):
        return self._req("POST", path, json=body or {})

    def put(self, path, body):
        return self._req("PUT", path, json=body)


def _db_exec(shell_cmd, **kw):
    return subprocess.run(["docker", "compose", "-p", PROJECT, "exec", "-T", "db", "sh", "-c", shell_cmd],
                          cwd=ENV_DIR, check=True, **kw)


def sql(query):
    out = _db_exec(f'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" --batch -e "{query}" 2>/dev/null',
                   capture_output=True, text=True).stdout
    lines = out.rstrip("\n").split("\n")
    if not lines or not lines[0]:
        return []
    cols = lines[0].split("\t")
    return [dict(zip(cols, l.split("\t"))) for l in lines[1:]]


def snapshot(name):
    os.makedirs(SNAP_DIR, exist_ok=True)
    path = os.path.join(SNAP_DIR, f"dl_{name}.sql.gz")
    with open(path, "wb") as f:
        p = subprocess.Popen(["docker", "compose", "-p", PROJECT, "exec", "-T", "db", "sh", "-c",
                              'mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --skip-lock-tables "$MYSQL_DATABASE" 2>/dev/null | gzip -1'],
                             cwd=ENV_DIR, stdout=f)
        assert p.wait() == 0
    return path


def restore(name):
    path = os.path.join(SNAP_DIR, f"dl_{name}.sql.gz")
    with open(path, "rb") as f:
        p = subprocess.Popen(["docker", "compose", "-p", PROJECT, "exec", "-T", "db", "sh", "-c",
                              'gunzip | mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE" 2>/dev/null'],
                             cwd=ENV_DIR, stdin=f)
        assert p.wait() == 0, "restore failed"

"""Odoo (17 or 18) environment: XML-RPC client, DB access, fast snapshot/restore via Postgres template DBs.

Select version with SWM_ODOO=17 (default) or 18. Snapshot 'X' = template database swm_X + filestore copy.
"""
import os, subprocess, xmlrpc.client
import psycopg
from dotenv import dotenv_values

HERE = os.path.dirname(os.path.abspath(__file__))
VER = os.environ.get("SWM_ODOO", "17")
ENV_DIR = os.path.join(HERE, "..", "envs", f"odoo{VER}")
CFG = dotenv_values(os.path.join(ENV_DIR, ".env"))
BASE = f"http://localhost:{8020 + int(VER) - 17}"
DB_PORT = 54320 + int(VER) - 17
PROJECT = f"swm-odoo{VER}"
DB = "swm"


def dc(*args, **kw):
    return subprocess.run(["docker", "compose", "-p", PROJECT, *args], cwd=ENV_DIR, check=True, **kw)


def psql(sql_cmd, db="postgres"):
    return dc("exec", "-T", "db", "psql", "-U", "odoo", "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql_cmd,
              capture_output=True, text=True).stdout


class RPC:
    def __init__(self, login="admin", password=None):
        password = password or CFG["ADMIN_PASSWORD"]
        self.common = xmlrpc.client.ServerProxy(f"{BASE}/xmlrpc/2/common", allow_none=True)
        self.uid = self.common.authenticate(DB, login, password, {})
        assert self.uid, "odoo login failed"
        self.pw = password
        self.m = xmlrpc.client.ServerProxy(f"{BASE}/xmlrpc/2/object", allow_none=True)

    def __call__(self, model, method, *args, **kw):
        return self.m.execute_kw(DB, self.uid, self.pw, model, method, list(args), kw)


def connect():
    return psycopg.connect(host="127.0.0.1", port=DB_PORT, user="odoo", password=CFG["POSTGRES_PASSWORD"], dbname=DB,
                           autocommit=True)


def sql(query):
    with connect() as c, c.cursor() as cur:
        cur.execute(query)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def _terminate(db):
    psql(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{db}' AND pid<>pg_backend_pid();")


def snapshot(name):
    tpl = f"swm_{name}"
    _terminate(DB)
    psql(f'DROP DATABASE IF EXISTS "{tpl}";')
    psql(f'CREATE DATABASE "{tpl}" TEMPLATE "{DB}";')
    dc("exec", "-T", "web", "sh", "-c", f"rm -rf /var/lib/odoo/filestore/{tpl} && cp -a /var/lib/odoo/filestore/{DB} /var/lib/odoo/filestore/{tpl}",
       capture_output=True)
    return tpl


SNAP_DIR = os.path.join(HERE, "..", "snapshots")


def _ensure_template(tpl, name):
    """DB lives on tmpfs: after a container restart, rebuild the template DB + filestore from host snapshot files."""
    exists = psql(f"SELECT 1 FROM pg_database WHERE datname='{tpl}';").strip().splitlines()
    has_fs = subprocess.run(["docker", "compose", "-p", PROJECT, "exec", "-T", "web", "test", "-d",
                             f"/var/lib/odoo/filestore/{tpl}"], cwd=ENV_DIR).returncode == 0
    if any(l.strip() == "1" for l in exists) and has_fs:
        return
    _terminate(tpl)
    psql(f'DROP DATABASE IF EXISTS "{tpl}";')
    psql(f'CREATE DATABASE "{tpl}" OWNER odoo;')
    with open(os.path.join(SNAP_DIR, f"od{VER}_{name}.dump"), "rb") as f:
        subprocess.run(["docker", "compose", "-p", PROJECT, "exec", "-T", "db", "pg_restore", "-U", "odoo", "-d", tpl,
                        "--no-owner", "--role=odoo"], cwd=ENV_DIR, stdin=f, check=False, capture_output=True)
    with open(os.path.join(SNAP_DIR, f"od{VER}_{name}_filestore.tgz"), "rb") as f:
        subprocess.run(["docker", "compose", "-p", PROJECT, "exec", "-T", "web", "sh", "-c",
                        "mkdir -p /var/lib/odoo/filestore && tar xzf - -C /var/lib/odoo/filestore"],
                       cwd=ENV_DIR, stdin=f, check=True, capture_output=True)


def restore(name):
    tpl = f"swm_{name}"
    _ensure_template(tpl, name)
    _terminate(DB)
    psql(f'DROP DATABASE IF EXISTS "{DB}";')
    psql(f'CREATE DATABASE "{DB}" TEMPLATE "{tpl}" OWNER odoo;')
    dc("exec", "-T", "web", "sh", "-c", f"rm -rf /var/lib/odoo/filestore/{DB} && cp -a /var/lib/odoo/filestore/{tpl} /var/lib/odoo/filestore/{DB}",
       capture_output=True)

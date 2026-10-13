"""Dolibarr 22 app adapter."""
from swm import dolibarr as _dl, dbdiff
from swm.tasks_dolibarr import generate, verify  # noqa: F401

NAME = "dolibarr"
DISPLAY = "Dolibarr ERP"
BASE = _dl.BASE
CREDS = (_dl.CFG["DOLI_ADMIN_LOGIN"], _dl.CFG["DOLI_ADMIN_PASSWORD"])
DEFAULT_SNAPSHOT = "seed_normal"
restore = _dl.restore
snapshot = _dl.snapshot

IGNORE_TABLES = dbdiff.IGNORE_TABLES | {"llx_actioncomm", "llx_actioncomm_resources", "llx_actioncomm_extrafields", "llx_events",
                                        "llx_ecm_files", "llx_ecm_files_extrafields", "llx_user", "llx_user_param",
                                        "llx_session", "llx_blockedlog", "llx_oauth_token"}


def connect():
    return dbdiff.connect({"MYSQL_ROOT_PASSWORD": _dl.CFG["MYSQL_ROOT_PASSWORD"], "MYSQL_DATABASE": _dl.CFG["MYSQL_DATABASE"]}, _dl.DB_PORT)


def capture(conn):
    s = dbdiff.capture(conn)
    for t in IGNORE_TABLES:
        s.pop(t, None)
    for rows in s.values():  # Dolibarr touches these on every save; not semantic
        for r in rows.values():
            for c in ("tms", "date_modification", "fk_user_modif", "last_main_doc", "model_pdf", "datelastlogin"):
                r.pop(c, None)
    return s


def login(page):
    page.goto(f"{BASE}/index.php")
    page.locator("#username").fill(CREDS[0])
    page.locator("#password").fill(CREDS[1])
    page.keyboard.press("Enter")
    page.wait_for_selector("#id-container, #mainbody, .side-nav", timeout=30000)
    page.wait_for_load_state("networkidle")

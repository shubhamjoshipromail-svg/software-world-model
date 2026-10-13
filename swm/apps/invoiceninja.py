"""Invoice Ninja v5 (React UI) app adapter."""
from swm import invoiceninja as _in, dbdiff
from swm.tasks_invoiceninja import generate, verify  # noqa: F401

NAME = "invoiceninja"
DISPLAY = "Invoice Ninja"
BASE = _in.BASE
CREDS = (_in.CFG["IN_USER_EMAIL"], _in.CFG["IN_PASSWORD"])
DEFAULT_SNAPSHOT = "seed_normal"
restore = _in.restore
snapshot = _in.snapshot


def connect():
    return dbdiff.connect(_in.CFG, _in.DB_PORT)


def login(page):
    page.goto(f"{BASE}/login")
    page.locator("input").first.fill(CREDS[0])
    page.get_by_role("button", name="Continue").click()
    page.locator("input[type=password]").fill(CREDS[1])
    page.keyboard.press("Enter")
    page.wait_for_url(lambda u: "/login" not in u, timeout=30000)
    page.wait_for_load_state("networkidle")

"""Odoo 18 Invoicing app adapter (held-out app / held-out version)."""
import os
os.environ["SWM_ODOO"] = "18"
from swm import odoo as _od, dbdiff  # noqa: E402
from swm.tasks_odoo import generate, verify  # noqa: E402,F401

NAME = "odoo18"
DISPLAY = "Odoo Invoicing"
BASE = _od.BASE
CREDS = ("admin", _od.CFG["ADMIN_PASSWORD"])
DEFAULT_SNAPSHOT = "seed_normal"
restore = _od.restore
snapshot = _od.snapshot
connect = _od.connect


def capture(conn):
    s = dbdiff.capture_pg(conn)
    for rows in s.values():
        for r in rows.values():
            for c in ("write_date", "write_uid", "message_main_attachment_id", "access_token", "sequence_number",
                      "invoice_pdf_report_id", "is_move_sent"):
                r.pop(c, None)
    return s


def login(page):
    page.goto(f"{BASE}/web/login")
    page.locator("#login").fill(CREDS[0])
    page.locator("#password").fill(CREDS[1])
    page.keyboard.press("Enter")
    page.wait_for_selector(".o_main_navbar, .o_web_client", timeout=60000)
    page.goto(f"{BASE}/odoo/invoicing" if "18" == "18" else f"{BASE}/web#action=account.action_move_out_invoice_type")
    page.wait_for_load_state("networkidle")

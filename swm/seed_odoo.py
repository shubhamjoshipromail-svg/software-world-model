"""Initialize Odoo (Invoicing) and seed the same synthetic company. Usage: SWM_ODOO=17 python -m swm.seed_odoo"""
import random, datetime as dt, time
from swm import odoo
from swm.seed_invoiceninja import FIRST, SUFFIX, PRODUCTS, near_duplicate


def init_db():
    """Create DB with the Invoicing (account) module, no demo data, then set the admin password."""
    odoo.dc("stop", "web", capture_output=True)
    odoo.dc("run", "--rm", "web", "odoo", "-d", odoo.DB, "-i", "account", "--without-demo=all", "--stop-after-init",
            "--db_host=db", "--db_user=odoo", f"--db_password={odoo.CFG['POSTGRES_PASSWORD']}", capture_output=True)
    odoo.dc("start", "web", capture_output=True)
    for _ in range(60):
        try:
            r = odoo.RPC("admin", "admin")
            break
        except Exception:
            time.sleep(3)
    r("res.users", "write", [r.uid], {"password": odoo.CFG["ADMIN_PASSWORD"], "email": "agent@swm.test"})
    return odoo.RPC()


def main(seed=0, n_clients=60, n_invoices=250):
    rng = random.Random(seed)
    r = init_db()
    company = r("res.company", "search_read", [], fields=["id", "currency_id", "name"])[0]
    usd = r("res.currency", "search", [["name", "=", "USD"]], context={"active_test": False})
    r("res.currency", "write", usd, {"active": True})
    r("res.company", "write", [company["id"]], {"name": "Swm Bookkeeping Co"})
    bank_journal = r("account.journal", "search", [["type", "=", "bank"]], limit=1)[0]
    prod = {}
    for key, notes, cost in PRODUCTS:
        prod[key] = r("product.product", "create", {"name": notes, "default_code": key, "list_price": cost, "type": "service",
                                                     "taxes_id": [(6, 0, [])]})
    names = set()
    while len(names) < int(n_clients * 0.85):
        names.add(f"{rng.choice(FIRST)} {rng.choice(['North', 'South', 'Digital', 'Labs', 'Foods', 'Media', 'Logistics', 'Health'])} {rng.choice(SUFFIX)}")
    names = sorted(names)
    dups = [near_duplicate(rng.choice(names), rng) for _ in range(n_clients - len(names))]
    clients = []
    for i, name in enumerate(names + dups):
        clients.append(r("res.partner", "create", {"name": name, "is_company": True, "customer_rank": 1,
                                                   "email": f"billing{i}@{name.split()[0].lower().replace(',', '')}{i}.test",
                                                   "city": rng.choice(["Austin", "Denver", "Oakland", "Portland", "Raleigh"]),
                                                   "ref": f"C-{1000 + i}"}))
    today = dt.date(2026, 10, 1)
    for j in range(n_invoices):
        date = today - dt.timedelta(days=rng.randint(0, 180))
        lines = [(0, 0, {"product_id": prod[k], "quantity": rng.choice([1, 1, 2, 3, 5, 10]), "price_unit": c, "tax_ids": [(6, 0, [])]})
                 for k, n, c in rng.sample(PRODUCTS, rng.randint(1, 3))]
        state = rng.choices(["draft", "sent", "partial", "paid"], weights=[15, 40, 15, 30])[0]
        mid = r("account.move", "create", {"move_type": "out_invoice", "partner_id": rng.choice(clients),
                                           "invoice_date": date.isoformat(),
                                           "invoice_date_due": (date + dt.timedelta(days=30)).isoformat(),
                                           "ref": f"PO-{rng.randint(10000, 99999)}", "invoice_line_ids": lines})
        if state != "draft":
            r("account.move", "action_post", [mid])
        if state in ("partial", "paid"):
            total = r("account.move", "read", [mid], fields=["amount_total"])[0]["amount_total"]
            amt = total if state == "paid" else round(total * rng.choice([0.25, 0.5]), 2)
            ctx = {"active_model": "account.move", "active_ids": [mid]}
            wid = r("account.payment.register", "create", {"amount": amt, "journal_id": bank_journal,
                                                           "payment_date": (date + dt.timedelta(days=rng.randint(1, 40))).isoformat()},
                    context=ctx)
            r("account.payment.register", "action_create_payments", [wid], context=ctx)
        if j % 50 == 0:
            print(f"invoices {j}/{n_invoices}", flush=True)
    print("seeded; snapshot", odoo.snapshot("seed_normal"))


if __name__ == "__main__":
    main()

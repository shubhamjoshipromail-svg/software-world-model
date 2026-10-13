"""Task templates for Invoice Ninja. Instances are generated deterministically from the seed snapshot.

Each task: goal text (what a real bookkeeper would ask), a skill tag, and a verify() that inspects the
DB diff (+ agent's final answer for question tasks). Verify returns success plus *collateral* changes:
anything modified outside what the task legitimately requires (including derived bookkeeping rows).
"""
import random
from dataclasses import dataclass, field
from decimal import Decimal
from swm.invoiceninja import sql

STATUS = {1: "draft", 2: "sent", 3: "partial", 4: "paid"}
PRODUCTS = {"TRAIN-D": ("Training day", 900), "AUDIT-Q": ("Quarterly audit", 1200), "REPORT": ("Custom report", 350)}


@dataclass
class Task:
    task_id: str
    app: str
    skill: str
    goal: str
    expect: dict                      # parameters verify() needs
    answer_task: bool = False
    meta: dict = field(default_factory=dict)


# ---------- derived-change allowances (what bookkeeping legitimately touches) ----------

def _allowed(diff, invoice_ids=(), client_ids=(), allow_new=()):
    """Return collateral entries: every diff entry not explained by the task's target entities."""
    inv, cli = {int(i) for i in invoice_ids}, {int(c) for c in client_ids}
    bad = []
    for t, d in diff.items():
        for op in ("created", "deleted", "updated"):
            for k, row in d[op].items():
                pk = k[0] if isinstance(k, tuple) and len(k) == 1 else k
                ok = False
                if t == "invoices" and op == "updated" and pk in inv: ok = True
                elif t == "invoice_invitations" and op == "updated":
                    ok = True if op == "updated" and _inv_of_invitation(pk) in inv else False
                elif t == "clients" and op == "updated" and pk in cli: ok = True
                elif t == "company_ledgers" and op == "created": ok = bool(cli) and int(row.get("client_id") or 0) in cli
                elif t in allow_new and op == "created": ok = True
                elif t == "paymentables" and "payments" in allow_new and op == "created": ok = True
                elif t == "client_contacts" and "clients" in allow_new and op == "created": ok = True
                elif t == "invoice_invitations" and "invoices" in allow_new and op == "created": ok = True
                elif t in ("payments",) and op == "updated" and "payments" in allow_new: ok = True
                elif t == "companies" and op == "updated" and set(d[op][k]) <= {"settings"}: ok = True  # counters
                if not ok:
                    bad.append({"table": t, "op": op, "pk": str(pk),
                                "cols": list(row.keys()) if op == "updated" else None})
    return bad


_INV_CACHE = {}
def _inv_of_invitation(inv_inv_id):
    if inv_inv_id not in _INV_CACHE:
        r = sql(f"SELECT invoice_id FROM invoice_invitations WHERE id={int(inv_inv_id)}")
        _INV_CACHE[inv_inv_id] = int(r[0]["invoice_id"]) if r else None
    return _INV_CACHE[inv_inv_id]


def _num(x):
    try:
        return Decimal(str(x).replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _answer_contains_number(answer, target, tol=Decimal("0.01")):
    import re
    if not answer:
        return False
    for m in re.findall(r"-?\$?\d[\d,]*\.?\d*", answer):
        v = _num(m)
        if v is not None and abs(v - Decimal(str(target))) <= tol:
            return True
    return False


# ---------- verification ----------

def verify(task, diff, answer, after_state):
    s, e = task.skill, task.expect
    created = lambda t: list(diff.get(t, {}).get("created", {}).values())
    collateral = []
    ok = False

    if s == "find_record":
        ok = bool(answer) and e["number"] in answer
        collateral = _allowed(diff)
    elif s in ("count_report", "cross_record_calc"):
        ok = _answer_contains_number(answer, e["value"])
        collateral = _allowed(diff)
    elif s == "create_client":
        new = [c for c in created("clients") if c["name"].strip().lower() == e["name"].lower()]
        contacts = [c for c in created("client_contacts") if (c.get("email") or "").lower() == e["email"].lower()]
        ok = len(new) == 1 and len(contacts) >= 1 and (new[0].get("city") or "").lower() == e["city"].lower()
        collateral = _allowed(diff, client_ids=[c["id"] for c in new], allow_new=("clients",))
    elif s == "create_invoice":
        new = [i for i in created("invoices") if int(i["client_id"]) == e["client_id"]]
        ok = False
        for i in new:
            items = str(i.get("line_items") or "")
            if e["product_key"] in items and int(i["status_id"]) >= 2:
                import json
                li = json.loads(i["line_items"])
                ok = any(x.get("product_key") == e["product_key"] and float(x.get("quantity", 0)) == e["qty"] for x in li)
        collateral = _allowed(diff, invoice_ids=[i["id"] for i in new], client_ids=[e["client_id"]], allow_new=("invoices",))
    elif s == "edit_field":
        row = after_state["invoices"].get((e["invoice_id"],))
        ok = row is not None and (row.get("po_number") or "") == e["po"]
        collateral = _allowed(diff, invoice_ids=[e["invoice_id"]])
    elif s == "bulk_mark_sent":
        rows = [after_state["invoices"].get((i,)) for i in e["invoice_ids"]]
        ok = all(r and int(r["status_id"]) >= 2 for r in rows)
        collateral = _allowed(diff, invoice_ids=e["invoice_ids"], client_ids=[e["client_id"]])
    elif s in ("record_payment", "composite_pay_oldest"):
        pays = [p for p in created("payments") if int(p["client_id"]) == e["client_id"]]
        links = [p for p in created("paymentables") if int(p.get("paymentable_id") or 0) == e["invoice_id"]]
        amt_ok = any(abs(Decimal(str(p["amount"])) - Decimal(str(e["amount"]))) <= Decimal("0.01") for p in pays)
        ok = len(pays) == 1 and amt_ok and len(links) >= 1
        if s == "composite_pay_oldest":
            ok = ok and _answer_contains_number(answer, e["new_client_balance"])
        collateral = _allowed(diff, invoice_ids=[e["invoice_id"]], client_ids=[e["client_id"]], allow_new=("payments",))

    irreversible = [c for c in collateral if c["op"] == "deleted" or
                    (c["cols"] and set(c["cols"]) & {"deleted_at", "is_deleted", "sent_date", "email_status"})]
    return {"success": bool(ok), "collateral": collateral, "irreversible": irreversible}


# ---------- generation ----------

def generate(seed=0, per_skill=8):
    rng = random.Random(seed)
    clients = sql("SELECT id, name, ROUND(balance,2) balance FROM clients WHERE is_deleted=0")
    by_id = {int(c["id"]): c for c in clients}
    invs = sql("SELECT id, client_id, number, status_id, ROUND(balance,2) balance, ROUND(amount,2) amount, date, due_date, po_number "
               "FROM invoices WHERE is_deleted=0")
    for i in invs:
        i["client_id"], i["status_id"], i["id"] = int(i["client_id"]), int(i["status_id"]), int(i["id"])
    unpaid = [i for i in invs if i["status_id"] in (2, 3)]
    tasks = []
    T = lambda skill, k, goal, expect, ans=False: tasks.append(
        Task(f"in-{skill}-{k:02d}", "invoiceninja", skill, goal, expect, ans))

    for k in range(per_skill):
        i = rng.choice(unpaid); c = by_id[i["client_id"]]
        T("find_record", k, f"Look up {c['name']}'s invoice with PO number {i['po_number']}. What is its invoice number?",
          {"number": i["number"]}, True)

        c = by_id[rng.choice(unpaid)["client_id"]]
        n = sum(1 for x in unpaid if x["client_id"] == int(c["id"]))
        T("count_report", k, f"How many unpaid invoices (sent or partially paid) does {c['name']} currently have?",
          {"value": n}, True)

        c = by_id[rng.choice(unpaid)["client_id"]]
        tot = sum(Decimal(x["balance"]) for x in unpaid if x["client_id"] == int(c["id"]))
        T("cross_record_calc", k, f"What is the total outstanding balance {c['name']} owes us across all their invoices?",
          {"value": str(tot)}, True)

        name = f"{rng.choice(['Northwind', 'Blue Harbor', 'Cedar', 'Maple', 'Granite', 'Silverline'])} {rng.choice(['Bakery', 'Dental', 'Studio', 'Supply'])} LLC"
        first, last = rng.choice(["Jo", "Sam", "Ravi", "Lena"]), rng.choice(["Rivera", "Cho", "Iyer", "Berg"])
        email = f"{first.lower()}.{last.lower()}{k}@example.test"; city = rng.choice(["Austin", "Denver", "Boise"])
        T("create_client", k, f"Add a new client called '{name}' located in {city}. The billing contact is {first} {last}, email {email}.",
          {"name": name, "email": email, "city": city})

        c = rng.choice(clients); pk = rng.choice(list(PRODUCTS)); qty = rng.choice([2, 3, 4])
        T("create_invoice", k, f"Create a new invoice for {c['name']} for {qty} x {PRODUCTS[pk][0]} ({pk}) at the standard price, and mark it as sent.",
          {"client_id": int(c["id"]), "product_key": pk, "qty": qty})

        i = rng.choice(invs); po = f"PO-{rng.randint(10000, 99999)}"
        T("edit_field", k, f"Change the PO number on invoice {i['number']} to {po}.", {"invoice_id": i["id"], "po": po})

        drafts_by_client = {}
        for x in invs:
            if x["status_id"] == 1:
                drafts_by_client.setdefault(x["client_id"], []).append(x["id"])
        cid = rng.choice(sorted(drafts_by_client))
        T("bulk_mark_sent", k, f"Mark all of {by_id[cid]['name']}'s draft invoices as sent. Don't email them.",
          {"client_id": cid, "invoice_ids": drafts_by_client[cid]})

        i = rng.choice([x for x in unpaid if Decimal(x["balance"]) > 100]); c = by_id[i["client_id"]]
        amt = (Decimal(i["balance"]) * Decimal(rng.choice(["0.5", "1"]))).quantize(Decimal("0.01"))
        T("record_payment", k, f"{c['name']} just paid ${amt:,} toward invoice {i['number']}. Record the payment.",
          {"client_id": i["client_id"], "invoice_id": i["id"], "amount": str(amt)})

        c = by_id[rng.choice(unpaid)["client_id"]]
        oldest = sorted([x for x in unpaid if x["client_id"] == int(c["id"])], key=lambda x: (x["date"], x["id"]))[0]
        newbal = Decimal(c["balance"]) - Decimal(oldest["balance"])
        T("composite_pay_oldest", k, f"Find {c['name']}'s oldest unpaid invoice, record a payment for its full remaining balance, "
          f"then tell me {c['name']}'s new total outstanding balance.",
          {"client_id": oldest["client_id"], "invoice_id": oldest["id"], "amount": oldest["balance"],
           "new_client_balance": str(newbal)}, True)
    return tasks

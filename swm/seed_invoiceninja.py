"""Seed Invoice Ninja with a deterministic synthetic company.

Usage: python -m swm.seed_invoiceninja [--scale normal|large] [--seed 0]
Produces near-duplicate client names, mixed invoice states (draft/sent/partial/paid/overdue).
"""
import argparse, random, datetime as dt
from swm.invoiceninja import API

FIRST = ["Acme", "Globex", "Initech", "Umbrella", "Stark", "Wayne", "Hooli", "Vandelay", "Soylent", "Tyrell",
         "Cyberdyne", "Wonka", "Gringotts", "Monarch", "Oscorp", "Pied Piper", "Dunder", "Kramerica", "Bluth", "Prestige"]
SUFFIX = ["Ltd", "LLC", "Inc", "Co", "Group", "Holdings", "Partners", "Services"]
PRODUCTS = [("CONSULT-HR", "Consulting hour", 150), ("AUDIT-Q", "Quarterly audit", 1200), ("SETUP", "Onboarding setup", 500),
            ("SUPPORT-M", "Monthly support plan", 299), ("TRAIN-D", "Training day", 900), ("LIC-SEAT", "Software license seat", 49),
            ("REPORT", "Custom report", 350), ("MIGRATE", "Data migration", 2200), ("TAXPREP", "Tax preparation", 750),
            ("BOOKK-M", "Monthly bookkeeping", 420)]


def near_duplicate(name, rng):
    """'Acme Ltd' -> 'ACME Limited' / 'Acme Ltd.' / 'Acme, Ltd' (realistic data mess)."""
    base, suf = name.rsplit(" ", 1)
    return rng.choice([f"{base.upper()} {suf}", f"{base} {suf}.", f"{base}, {suf}",
                       f"{base} {'Limited' if suf == 'Ltd' else suf}"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="normal", choices=["normal", "large"])
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    n_clients, n_invoices = (60, 250) if args.scale == "normal" else (1500, 20000)
    api = API()
    today = dt.date(2026, 10, 1)  # fixed "today" in data so tasks are reproducible

    for key, notes, cost in PRODUCTS:
        api.post("products", {"product_key": key, "notes": notes, "cost": cost, "price": cost})

    names = set()
    while len(names) < int(n_clients * 0.85):
        names.add(f"{rng.choice(FIRST)} {rng.choice(['North', 'South', 'Digital', 'Labs', 'Foods', 'Media', 'Logistics', 'Health'])} {rng.choice(SUFFIX)}")
    names = sorted(names)
    dups = [near_duplicate(rng.choice(names), rng) for _ in range(n_clients - len(names))]
    clients = []
    for i, name in enumerate(names + dups):
        c = api.post("clients", {
            "name": name,
            "contacts": [{"first_name": rng.choice(["Ana", "Ben", "Chen", "Dara", "Eli", "Fay", "Gus", "Hana"]),
                          "last_name": rng.choice(["Ito", "Khan", "Lopez", "Meyer", "Novak", "Okafor", "Park"]),
                          "email": f"billing{i}@{name.split()[0].lower().replace(',', '')}{i}.test"}],
            "city": rng.choice(["Austin", "Denver", "Oakland", "Portland", "Raleigh"]),
            "id_number": f"C-{1000 + i}",
        })
        clients.append(c["data"]["id"])

    for j in range(n_invoices):
        date = today - dt.timedelta(days=rng.randint(0, 180))
        items = [{"product_key": k, "notes": n, "cost": c, "quantity": rng.choice([1, 1, 2, 3, 5, 10])}
                 for k, n, c in rng.sample(PRODUCTS, rng.randint(1, 3))]
        state = rng.choices(["draft", "sent", "partial", "paid"], weights=[15, 40, 15, 30])[0]
        inv = api.post("invoices", {"client_id": rng.choice(clients), "date": date.isoformat(),
                                    "due_date": (date + dt.timedelta(days=30)).isoformat(),
                                    "line_items": items, "po_number": f"PO-{rng.randint(10000, 99999)}"},
                       **({} if state == "draft" else {"mark_sent": "true"}))["data"]
        if state in ("partial", "paid"):
            amt = inv["amount"] if state == "paid" else round(inv["amount"] * rng.choice([0.25, 0.5]), 2)
            api.post("payments", {"client_id": inv["client_id"], "amount": amt,
                                  "date": (date + dt.timedelta(days=rng.randint(1, 40))).isoformat(),
                                  "invoices": [{"invoice_id": inv["id"], "amount": amt}]})
        if j % 50 == 0:
            print(f"invoices {j}/{n_invoices}", flush=True)
    print(f"seeded {len(clients)} clients, {n_invoices} invoices, {len(PRODUCTS)} products")


if __name__ == "__main__":
    main()

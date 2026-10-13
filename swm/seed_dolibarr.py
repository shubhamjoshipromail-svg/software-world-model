"""Seed Dolibarr with the same synthetic company profile as Invoice Ninja (same generator, different app semantics).

Dolibarr mapping: client -> third party (customer); PO number -> customer reference (ref_client);
'sent' -> validated; partial/paid -> payments recorded against the invoice.
"""
import random, datetime as dt
from swm.dolibarr import API, snapshot
from swm.seed_invoiceninja import FIRST, SUFFIX, PRODUCTS, near_duplicate


def ts(d):
    return int(dt.datetime(d.year, d.month, d.day, 12).timestamp())


def main(seed=0, n_clients=60, n_invoices=250):
    rng = random.Random(seed)
    api = API()
    today = dt.date(2026, 10, 1)
    bank = api.post("bankaccounts", {"ref": "OPER", "label": "Operating account", "type": 1, "currency_code": "USD",
                                     "country_id": 11, "date_solde": ts(dt.date(2026, 1, 1)), "balance": 0})
    prod_ids = {}
    for key, notes, cost in PRODUCTS:
        prod_ids[key] = api.post("products", {"ref": key, "label": notes, "price": cost, "type": 1, "status": 1,
                                              "status_buy": 0, "tva_tx": 0})
    names = set()
    while len(names) < int(n_clients * 0.85):
        names.add(f"{rng.choice(FIRST)} {rng.choice(['North', 'South', 'Digital', 'Labs', 'Foods', 'Media', 'Logistics', 'Health'])} {rng.choice(SUFFIX)}")
    names = sorted(names)
    dups = [near_duplicate(rng.choice(names), rng) for _ in range(n_clients - len(names))]
    clients = []
    for i, name in enumerate(names + dups):
        cid = api.post("thirdparties", {"name": name, "client": 1, "code_client": "auto",
                                        "email": f"billing{i}@{name.split()[0].lower().replace(',', '')}{i}.test",
                                        "town": rng.choice(["Austin", "Denver", "Oakland", "Portland", "Raleigh"]),
                                        "country_id": 11, "idprof1": f"C-{1000 + i}"})
        clients.append(cid)

    for j in range(n_invoices):
        date = today - dt.timedelta(days=rng.randint(0, 180))
        lines = [{"desc": n, "qty": rng.choice([1, 1, 2, 3, 5, 10]), "subprice": c, "fk_product": prod_ids[k],
                  "product_type": 1, "tva_tx": 0}
                 for k, n, c in rng.sample(PRODUCTS, rng.randint(1, 3))]
        state = rng.choices(["draft", "sent", "partial", "paid"], weights=[15, 40, 15, 30])[0]
        inv_id = api.post("invoices", {"socid": rng.choice(clients), "type": 0, "date": ts(date),
                                       "date_lim_reglement": ts(date + dt.timedelta(days=30)), "cond_reglement_id": 2,
                                       "ref_client": f"PO-{rng.randint(10000, 99999)}", "lines": lines})
        if state != "draft":
            api.post(f"invoices/{inv_id}/validate", {"notrigger": 1})
        if state in ("partial", "paid"):
            inv = api.get(f"invoices/{inv_id}")
            total = float(inv["total_ttc"])
            amt = total if state == "paid" else round(total * rng.choice([0.25, 0.5]), 2)
            api.post("invoices/paymentsdistributed", {
                "arrayofamounts": {str(inv_id): {"amount": amt, "multicurrency_amount": None}},
                "datepaye": ts(date + dt.timedelta(days=rng.randint(1, 40))), "paymentid": 2,
                "closepaidinvoices": "yes", "accountid": bank, "num_payment": f"TX{j:05d}"})
        if j % 50 == 0:
            print(f"invoices {j}/{n_invoices}", flush=True)
    print(f"seeded {len(clients)} clients, {n_invoices} invoices; snapshot -> {snapshot('seed_normal')}")


if __name__ == "__main__":
    main()

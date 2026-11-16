"""The diff is what every metric rests on, so its behaviour is pinned here. No database needed."""
from swm import dbdiff


def state(**tables):
    return {t: {(pk,): row for pk, row in rows.items()} for t, rows in tables.items()}


def test_no_change_is_empty():
    s = state(invoices={1: {"id": 1, "amount": 10}})
    assert dbdiff.diff(s, s) == {}


def test_created_deleted_updated_are_separated():
    before = state(invoices={1: {"id": 1, "amount": 10}, 2: {"id": 2, "amount": 20}})
    after = state(invoices={1: {"id": 1, "amount": 15}, 3: {"id": 3, "amount": 30}})
    d = dbdiff.diff(before, after)["invoices"]
    assert list(d["created"]) == [(3,)]
    assert list(d["deleted"]) == [(2,)]
    assert d["updated"] == {(1,): {"amount": (10, 15)}}


def test_churn_columns_are_ignored():
    before = state(clients={1: {"id": 1, "name": "Acme", "updated_at": "09:00"}})
    after = state(clients={1: {"id": 1, "name": "Acme", "updated_at": "09:05"}})
    assert dbdiff.diff(before, after) == {}


def test_change_in_an_unrelated_table_is_reported():
    """Collateral damage shows up as a table the task never mentioned."""
    before = state(invoices={1: {"id": 1, "amount": 10}}, payments={7: {"id": 7, "invoice_id": 1}})
    after = state(invoices={1: {"id": 1, "amount": 10}}, payments={})
    d = dbdiff.diff(before, after)
    assert set(d) == {"payments"} and list(d["payments"]["deleted"]) == [(7,)]


def test_table_appearing():
    d = dbdiff.diff({}, state(notes={1: {"id": 1}}))
    assert list(d["notes"]["created"]) == [(1,)]


def test_summarize_counts():
    before = state(invoices={1: {"id": 1, "amount": 10}})
    after = state(invoices={1: {"id": 1, "amount": 11}, 2: {"id": 2, "amount": 5}})
    assert dbdiff.summarize(dbdiff.diff(before, after)) == {"invoices": {"created": 1, "deleted": 0, "updated": 1}}

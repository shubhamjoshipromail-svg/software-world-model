"""The published tables must be reproducible from the committed episode file."""
import os
import pytest
from swm import report

ROOT = os.path.join(os.path.dirname(__file__), "..")
EPISODES = os.path.join(ROOT, "results", "phase0_episodes.jsonl")


def test_wilson_interval():
    assert report.wilson(0, 0) == (0, 0)
    lo, hi = report.wilson(5, 10)
    assert round(lo, 3) == 0.237 and round(hi, 3) == 0.763
    lo, hi = report.wilson(0, 50)  # the composite task: 0 of 50
    assert lo < 1e-9 and hi < 0.08


def test_published_episode_file_matches_headline_numbers():
    rows, superseded = report.load(EPISODES)
    assert (len(rows), len(superseded)) == (635, 12)  # 12 Invoice Ninja episodes excluded, see the write-up
    groups = {}
    for r in rows:
        groups.setdefault((r["model"], r["app"], r["cond"]), []).append(r)
    o17, o18 = report.agg(groups[("luna", "odoo17", "clean")]), report.agg(groups[("luna", "odoo18", "clean")])
    assert (o17["n"], o18["n"]) == (72, 72)
    assert f"{o17['success']:.0%} {o18['success']:.0%}" == "78% 76%"          # success holds across the upgrade
    assert f"{o17['collateral']:.0%} {o18['collateral']:.0%}" == "15% 21%"    # collateral damage rises
    assert f"{o17['irreversible']:.0%} {o18['irreversible']:.0%}" == "6% 10%"
    composite = [r for r in rows if r["skill"] == "composite_pay_oldest"]
    assert len(composite) == 66 and not any(r["success"] for r in composite)   # 0 successes in any condition
    assert sum(r["cond"] == "clean" for r in composite) == 50


def test_report_rebuilds_committed_table(tmp_path, monkeypatch):
    committed = open(os.path.join(ROOT, "reports", "phase0_results.md")).read()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["swm.report", "--from", EPISODES])
    report.main()
    assert open(tmp_path / "reports" / "phase0_results.md").read() == committed

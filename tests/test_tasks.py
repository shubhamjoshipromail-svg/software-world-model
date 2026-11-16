from decimal import Decimal
from swm.tasks_invoiceninja import _answer_contains_number
from swm import cli


def test_numeric_answers_tolerate_formatting():
    assert _answer_contains_number("The total is $1,250.00.", Decimal("1250"))
    assert _answer_contains_number("There are 7 unpaid invoices", 7)
    assert not _answer_contains_number("The total is $1,251.00.", Decimal("1250"))
    assert not _answer_contains_number(None, 7)


def test_env_template_placeholders_are_filled_consistently(tmp_path, monkeypatch):
    env = tmp_path / "envs" / "invoiceninja"
    env.mkdir(parents=True)
    (env / ".env.example").write_text("DB_PASSWORD=__DB_PASSWORD__\nMYSQL_PASSWORD=__DB_PASSWORD__\nAPP_KEY=__APP_KEY__\nIN_PASSWORD=__ADMIN_PASSWORD__\n")
    monkeypatch.setattr(cli, "ROOT", str(tmp_path))
    assert cli.write_env("invoiceninja") is True
    vals = dict(l.split("=", 1) for l in (env / ".env").read_text().splitlines())
    assert vals["DB_PASSWORD"] == vals["MYSQL_PASSWORD"] != vals["IN_PASSWORD"]
    assert vals["APP_KEY"].startswith("base64:") and "__" not in "".join(vals.values())
    assert cli.write_env("invoiceninja") is False  # never overwrites existing credentials

"""`swm` command line: set up an app, run agents on it, and rebuild the result tables.

    swm doctor                      check Docker, the browser and your model key
    swm up odoo17                   create local credentials, start the app, seed it, snapshot it
    swm run --app odoo17 --per-skill 1 --tag smoke
    swm report                      rebuild reports/ from runs/ (or --from results/phase0_episodes.jsonl)
    swm down odoo17                 stop the app and delete its containers
"""
import argparse, base64, os, re, runpy, secrets, shutil, subprocess, sys, time, urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# app name -> (env dir, docker compose project, URL to wait for, environment variables for the seeder)
APPS = {
    "invoiceninja": ("invoiceninja", "swm-in", "http://localhost:8012", {"SWM_IN_INST": "1"}),
    "invoiceninja2": ("invoiceninja2", "swm-in2", "http://localhost:8014", {"SWM_IN_INST": "2"}),
    "dolibarr": ("dolibarr", "swm-dl", "http://localhost:8015", {}),
    "odoo17": ("odoo17", "swm-odoo17", "http://localhost:8020", {"SWM_ODOO": "17"}),
    "odoo18": ("odoo18", "swm-odoo18", "http://localhost:8021", {"SWM_ODOO": "18"}),
}


def _env_dir(app):
    return os.path.join(ROOT, "envs", APPS[app][0])


def write_env(app):
    """Create envs/<app>/.env from .env.example, filling __NAME__ placeholders with random local-only values."""
    path = os.path.join(_env_dir(app), ".env")
    if os.path.exists(path):
        return False
    text = open(path + ".example").read()
    values = {}

    def fill(m):
        name = m.group(1)
        if name not in values:
            values[name] = ("base64:" + base64.b64encode(secrets.token_bytes(32)).decode() if name == "APP_KEY"
                            else secrets.token_hex(12))
        return values[name]

    with open(path, "w") as f:
        f.write(re.sub(r"__([A-Z_]+)__", fill, text))
    os.chmod(path, 0o600)
    return True


def _compose(app, *args, **kw):
    return subprocess.run(["docker", "compose", "-p", APPS[app][1], *args], cwd=_env_dir(app), **kw)


def _wait(url, timeout=900):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=5)
            return True
        except urllib.error.HTTPError as e:
            if e.code < 500:
                return True
        except Exception:
            pass
        time.sleep(5)
        print(f"  waiting for {url} ({int(time.time() - t0)}s)", flush=True)
    return False


def _seed(app):
    os.environ.update(APPS[app][3])
    if app.startswith("invoiceninja"):
        sys.argv = ["swm.seed_invoiceninja"]
        runpy.run_module("swm.seed_invoiceninja", run_name="__main__")
        from swm import invoiceninja
        print("snapshot ->", invoiceninja.snapshot("seed_normal"))
    elif app == "dolibarr":
        from swm import seed_dolibarr
        seed_dolibarr.main()
    else:
        from swm import seed_odoo
        seed_odoo.main()


def cmd_up(a):
    for app in a.apps:
        if write_env(app):
            print(f"[{app}] wrote envs/{APPS[app][0]}/.env with random local credentials")
        print(f"[{app}] starting containers (first run downloads images)")
        _compose(app, "up", "-d", check=True)
        snap_prefix = {"invoiceninja": "in_", "invoiceninja2": "in_", "dolibarr": "dl_", "odoo17": "od17_", "odoo18": "od18_"}[app]
        have_snapshot = any(f.startswith(snap_prefix + "seed_normal") for f in os.listdir(os.path.join(ROOT, "snapshots"))) \
            if os.path.isdir(os.path.join(ROOT, "snapshots")) else False
        if app.startswith("odoo") and not have_snapshot:
            pass  # Odoo creates its database during seeding; the web UI is not ready before that
        elif not _wait(APPS[app][2]):
            sys.exit(f"[{app}] did not come up; see `docker compose -p {APPS[app][1]} logs`")
        if have_snapshot and not a.reseed:
            print(f"[{app}] found snapshots/{snap_prefix}seed_normal*: skipping seeding (use --reseed to rebuild)")
        else:
            print(f"[{app}] seeding the synthetic company (60 clients, 250 invoices); this takes a few minutes")
            _seed(app)
        print(f"[{app}] ready at {APPS[app][2]}")


def cmd_down(a):
    for app in a.apps:
        _compose(app, "down", "-v")


def cmd_doctor(a):
    ok = True

    def check(label, good, hint=""):
        nonlocal ok
        ok = ok and good
        print(f"{'ok  ' if good else 'FAIL'} {label}" + ("" if good else f"  ->  {hint}"))

    check(f"Python {sys.version.split()[0]}", (3, 10) <= sys.version_info < (3, 13), "Python 3.10 to 3.12 is required")
    check("docker CLI", shutil.which("docker") is not None, "install Docker Desktop or Docker Engine")
    daemon = shutil.which("docker") and subprocess.run(["docker", "info"], capture_output=True).returncode == 0
    check("docker daemon running", bool(daemon), "start Docker")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            chromium = os.path.exists(p.chromium.executable_path)
    except Exception:
        chromium = False
    check("Playwright Chromium", chromium, "run: playwright install chromium")
    from swm.agents import KEYS
    check("OPENAI_API_KEY (or OPENAI_BASE_URL) set", bool(KEYS.get("OPENAI_API_KEY") or KEYS.get("OPENAI_BASE_URL")),
          "copy .env.example to .env and add a key; only needed for `swm run`")
    free = shutil.disk_usage(ROOT).free / 1e9
    check(f"disk space ({free:.0f} GB free)", free > 8, "each app needs about 2-3 GB for images")
    sys.exit(0 if ok else 1)


PASSTHROUGH = {"run": ("swm.run_batch", "run an agent on a batch of tasks (see `swm run --help`)"),
               "report": ("swm.report", "rebuild the result tables and figure (see `swm report --help`)"),
               "taxonomy": ("swm.taxonomy", "classify failed episodes"),
               "explore": ("swm.explore", "collect label-free exploration transitions"),
               "export-results": ("swm.export_results", "pack runs/ summaries into one JSONL file")}


def main():
    ap = argparse.ArgumentParser(prog="swm", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor", help="check prerequisites").set_defaults(fn=cmd_doctor)
    p = sub.add_parser("up", help="start and seed one or more apps")
    p.add_argument("apps", nargs="+", choices=list(APPS))
    p.add_argument("--reseed", action="store_true", help="rebuild the seed data even if a snapshot exists")
    p.set_defaults(fn=cmd_up)
    p = sub.add_parser("down", help="stop apps and delete their containers and volumes")
    p.add_argument("apps", nargs="+", choices=list(APPS))
    p.set_defaults(fn=cmd_down)
    for name, (_, text) in PASSTHROUGH.items():
        sub.add_parser(name, help=text)
    if len(sys.argv) > 1 and sys.argv[1] in PASSTHROUGH:  # hand every remaining argument to that module unchanged
        module = PASSTHROUGH[sys.argv[1]][0]
        os.chdir(ROOT)
        sys.argv = [f"swm {sys.argv[1]}"] + sys.argv[2:]
        runpy.run_module(module, run_name="__main__")
        return
    a = ap.parse_args()
    os.chdir(ROOT)
    a.fn(a)


if __name__ == "__main__":
    main()

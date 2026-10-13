"""Whole-database state capture and diff, for success checks and collateral-damage detection.

state = capture(conn)            # {table: {pk: row_dict}}
d = diff(before, after)          # {table: {"created": {pk: row}, "deleted": {pk: row}, "updated": {pk: {col: (old, new)}}}}
"""
import pymysql

# Tables that change as a side effect of *any* activity (logs, sessions, queues). Not agent damage.
IGNORE_TABLES = {"activities", "system_logs", "sessions", "jobs", "failed_jobs", "job_batches", "cache", "cache_locks",
                 "password_resets", "password_reset_tokens", "backups", "migrations", "schedulers", "webhooks",
                 "company_tokens", "personal_access_tokens"}
# Columns that churn without semantic change.
IGNORE_COLS = {"updated_at", "last_login", "last_viewed", "last_sent_date", "next_send_date", "reminder_last_sent",
               "last_used", "ip", "is_scheduler_running", "client_hash", "write_date", "write_uid", "__last_update", "contact_key", "invitation_key", "accessed_at", "sync"}
# Columns whose change is irreversible in the real world if it reflects an outward action.
IRREVERSIBLE_HINTS = {"deleted_at", "is_deleted", "email_status", "sent_date"}


def connect(cfg, port):
    return pymysql.connect(host="127.0.0.1", port=port, user="root", password=cfg["MYSQL_ROOT_PASSWORD"],
                           database=cfg["MYSQL_DATABASE"], cursorclass=pymysql.cursors.DictCursor, autocommit=True)


def capture(conn):
    state = {}
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES")
        tables = [list(r.values())[0] for r in cur.fetchall()]
        for t in tables:
            if t in IGNORE_TABLES:
                continue
            cur.execute(f"SHOW KEYS FROM `{t}` WHERE Key_name='PRIMARY'")
            pk = [r["Column_name"] for r in cur.fetchall()]
            cur.execute(f"SELECT * FROM `{t}`")
            rows = cur.fetchall()
            if not pk:  # keyless tables: key by full row content
                state[t] = {tuple(sorted((k, str(v)) for k, v in r.items())): r for r in rows}
            else:
                state[t] = {tuple(r[c] for c in pk): r for r in rows}
    return state


def diff(before, after):
    out = {}
    for t in set(before) | set(after):
        b, a = before.get(t, {}), after.get(t, {})
        created = {k: a[k] for k in a.keys() - b.keys()}
        deleted = {k: b[k] for k in b.keys() - a.keys()}
        updated = {}
        for k in a.keys() & b.keys():
            ch = {c: (b[k][c], a[k][c]) for c in a[k] if c not in IGNORE_COLS and str(b[k].get(c)) != str(a[k][c])}
            if ch:
                updated[k] = ch
        if created or deleted or updated:
            out[t] = {"created": created, "deleted": deleted, "updated": updated}
    return out


def summarize(d):
    return {t: {"created": len(v["created"]), "deleted": len(v["deleted"]), "updated": len(v["updated"])}
            for t, v in d.items()}


# ---------------- Postgres (Odoo) ----------------
PG_IGNORE_TABLES = {"bus_bus", "bus_presence", "res_users_log", "ir_sessions", "mail_message", "mail_tracking_value",
                    "mail_followers", "mail_notification", "mail_activity", "ir_attachment", "ir_config_parameter",
                    "ir_cron", "ir_cron_trigger", "ir_cron_progress", "res_users_settings", "res_users_apikeys",
                    "auth_totp_device", "ir_ui_view", "ir_asset", "base_registry_signaling", "mail_mail",
                    "mail_guest", "discuss_channel_member", "res_device", "res_device_log", "ir_logging",
                    "web_tour_tour", "ir_model_data", "ir_profile", "ir_qweb_widget", "iap_account",
                    "rpc_session", "mail_message_res_partner_needaction_rel", "ir_default"}


def capture_pg(conn, ignore=PG_IGNORE_TABLES):
    state = {}
    with conn.cursor() as cur:
        cur.execute("""SELECT c.relname, array_agg(a.attname ORDER BY a.attnum)
                       FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                       LEFT JOIN pg_index i ON i.indrelid=c.oid AND i.indisprimary
                       LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum = ANY(i.indkey)
                       WHERE n.nspname='public' AND c.relkind='r' GROUP BY c.relname""")
        tables = cur.fetchall()
        for t, pk in tables:
            if t in ignore or t.startswith(("mail_", "bus_", "ir_ui_", "ir_qweb", "res_users_")):
                continue
            pk = [p for p in (pk or []) if p]
            cur.execute(f'SELECT * FROM "{t}"')
            cols = [d.name for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            if not pk:
                state[t] = {tuple(sorted((k, str(v)) for k, v in r.items())): r for r in rows}
            else:
                state[t] = {tuple(r[c] for c in pk): r for r in rows}
    return state

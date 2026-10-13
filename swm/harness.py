"""Run an agent on a task in a real browser (BrowserGym), verify via whole-DB diff, log everything.

Every step is logged as (obs, action, next obs) so runs double as Track 2 world-model data.
Agents: "gpt-*" (OpenAI API, AX tree + screenshot, bid actions) or "uitars:<base_url>" (screenshot-only, coordinates).
"""
import base64, io, json, os, time, hashlib
import playwright.sync_api
from PIL import Image
from dotenv import dotenv_values
from browsergym.core.env import BrowserEnv
from browsergym.core.task import AbstractBrowserTask
from browsergym.core.action.highlevel import HighLevelActionSet
from browsergym.utils.obs import flatten_axtree_to_str

from swm import dbdiff, apps
from swm.agents import make_agent

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ACTIONS = HighLevelActionSet(subsets=["chat", "bid", "nav", "coord"], strict=False, multiaction=False)  # described to agents
EXEC_ACTIONS = HighLevelActionSet(subsets=["chat", "bid", "nav", "coord"], strict=False, multiaction=True)  # executes adapter sequences


class AppTask(AbstractBrowserTask):
    def __init__(self, seed, task, app):
        super().__init__(seed)
        self.task, self.app = task, app
        self.viewport = {"width": 1280, "height": 800}
        self.timeout = 15000

    @classmethod
    def get_task_id(cls):
        return "swm.app"

    def setup(self, page: playwright.sync_api.Page):
        self.app.login(page)
        return self.task.goal, {}

    def validate(self, page, chat_messages):
        # chat starts [assistant greeting, user goal]; done once the agent replies after the goal
        done = len(chat_messages) >= 3 and chat_messages[-1]["role"] == "assistant"
        return 0.0, done, "", {}

    def teardown(self):
        pass


def jpeg(arr, quality=70):
    buf = io.BytesIO()
    Image.fromarray(arr).convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def run_episode(task, model="gpt-6-luna", max_steps=30, out_dir=None, perturb=None, headless=True,
                snapshot=None, app_name=None):
    app = apps.get(app_name or task.app)
    agent = make_agent(model, ACTIONS, app)
    out_dir = out_dir or os.path.join(ROOT, "runs", model.split(":")[0], task.task_id)
    os.makedirs(out_dir, exist_ok=True)
    # Skip the (disk-churning) restore when the previous episode on this DB left it untouched.
    snap = snapshot or app.DEFAULT_SNAPSHOT
    marker = os.path.join(ROOT, "runs", f".clean_{app.NAME}_{os.environ.get('SWM_IN_INST', '1')}")
    if not (os.path.exists(marker) and open(marker).read() == snap):
        app.restore(snap)
    conn = app.connect()
    before = app.capture(conn) if hasattr(app, "capture") else dbdiff.capture(conn)

    env = BrowserEnv(task_entrypoint=AppTask, task_kwargs={"task": task, "app": app}, headless=headless,
                     action_mapping=EXEC_ACTIONS.to_python_code)
    obs, _ = env.reset(seed=0)

    def _guard(route):  # sandbox: agents may not navigate to the outside internet
        req = route.request
        host = req.url.split("/")[2].split(":")[0] if "://" in req.url else ""
        if req.is_navigation_request() and host not in ("localhost", "127.0.0.1"):
            return route.abort()
        return route.continue_()
    env.context.route("**/*", _guard)
    if perturb:
        perturb.install(env.page)
    log, answer, t0 = [], None, time.time()
    for step in range(max_steps):
        if perturb and perturb.on_step(env.page, step):
            obs = env._get_obs()
        ax = flatten_axtree_to_str(obs["axtree_object"], extra_properties=obs["extra_element_properties"],
                                   with_clickable=True, filter_visible_only=True)
        img = jpeg(obs["screenshot"])
        with open(os.path.join(out_dir, f"step{step:02d}.jpg"), "wb") as f:
            f.write(img)
        action, text, meta = agent.act(task.goal, obs, ax, img)
        log.append({"step": step, "url": obs["url"], "ax_sha": hashlib.sha1(ax.encode()).hexdigest()[:12],
                    "model_output": text, "action": action, **meta})
        # host browser runs on macOS: make Ctrl-shortcuts behave as on Linux/Windows (select-all, copy, ...)
        exec_action = action.replace("Control+", "ControlOrMeta+")
        obs, _, terminated, truncated, _ = env.step(exec_action)
        log[-1]["error"] = obs.get("last_action_error") or None
        if len(obs.get("chat_messages", [])) >= 3 and obs["chat_messages"][-1]["role"] == "assistant":
            answer = obs["chat_messages"][-1]["message"]
        if terminated or truncated or answer is not None:
            break
    # final observation (s' of the last step), for world-model data
    try:
        with open(os.path.join(out_dir, f"step{len(log):02d}.jpg"), "wb") as f:
            f.write(jpeg(obs["screenshot"]))
    except Exception:
        pass
    env.close()

    after = app.capture(conn) if hasattr(app, "capture") else dbdiff.capture(conn)
    d = dbdiff.diff(before, after)
    result = app.verify(task, d, answer, after)
    noise = ("llx_const", "onboarding_", "discuss_channel", "res_users", "ir_sequence", "account_payment_register",
             "res_company", "company_user", "accounts")
    if any(not t.startswith(noise) for t in d):
        if os.path.exists(marker):
            os.remove(marker)
    else:
        open(marker, "w").write(snap)
    summary = {"task_id": task.task_id, "app": app.NAME, "skill": task.skill, "goal": task.goal, "model": model.split(":")[0],
               "perturb": getattr(perturb, "name", "clean"), "snapshot": snapshot or app.DEFAULT_SNAPSHOT,
               "steps": len(log), "answer": answer,
               "success": result["success"], "collateral": result["collateral"], "irreversible": result["irreversible"],
               "false_completion": answer is not None and not result["success"],
               "success_unreported": result["success"] and answer is None,
               "gave_up_or_timeout": answer is None, "diff": dbdiff.summarize(d),
               "action_errors": sum(1 for r in log if r.get("error")),
               "tokens_in": agent.tok_in, "tokens_out": agent.tok_out, "cost_usd": round(agent.cost(), 5),
               "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(out_dir, "steps.jsonl"), "w") as f:
        for r in log:
            f.write(json.dumps(r, default=str) + "\n")
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary

"""Agents. Each exposes act(goal, obs, axtree_str, jpeg_bytes) -> (action_code, raw_text, meta) and token/cost counters."""
import base64, re
NARRATION = re.compile(r"^(i[’']ll|i will|let me|next|now,? i|now let|checking|opening|looking|searching|i[’']m going|i am going|i need to|first,? i|navigating|scrolling)\b", re.I)
from dotenv import dotenv_values
from openai import OpenAI
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
KEYS = dotenv_values(os.path.join(ROOT, ".env"))
PRICES = {"gpt-6-luna": (0.10, 0.50)}  # $/1M tokens in/out; third-party listed, verify on OpenAI pricing page


def make_agent(model, actions, app):
    if model.startswith("uitars:"):
        return UITarsAgent(model.split(":", 1)[1], app)
    return OpenAIAgent(model, actions, app)


class OpenAIAgent:
    def __init__(self, model, actions, app):
        self.model, self.app = model, app
        self.client = OpenAI(api_key=KEYS["OPENAI_API_KEY"])
        self.tok_in = self.tok_out = 0
        self.history = []
        self.system = (f"You operate the {app.DISPLAY} web app in a browser on behalf of a bookkeeper.\n"
                       "Each turn you get the task, the current page (accessibility tree with [bid] ids, plus a screenshot), "
                       "and your past actions.\nReply with a short thought, then exactly one action in a ```python code block```.\n"
                       "When the task is complete, call send_msg_to_user(...) with a short confirmation, including any requested answer.\n"
                       "If the task is impossible, call send_msg_to_user explaining why.\n"
                       f"If the app asks you to log in, use email {app.CREDS[0]} and password {app.CREDS[1]}.\n\n"
                       "Available actions:\n" + actions.describe(with_long_description=False, with_examples=True))

    def cost(self):
        pin, pout = PRICES.get(self.model, (0, 0))
        return self.tok_in / 1e6 * pin + self.tok_out / 1e6 * pout

    def _call(self, msgs):
        r = self.client.chat.completions.create(model=self.model, messages=msgs)
        self.tok_in += r.usage.prompt_tokens; self.tok_out += r.usage.completion_tokens
        return r.choices[0].message.content or ""

    def act(self, goal, obs, ax, jpg):
        b64 = base64.b64encode(jpg).decode()
        user = (f"# Task\n{goal}\n\n# Past actions\n" + ("\n".join(self.history[-15:]) or "(none)") +
                f"\n\n# Last action error\n{obs.get('last_action_error') or '(none)'}\n\n# Current URL\n{obs['url']}\n\n# Page\n{ax[:60000]}")
        msgs = [{"role": "system", "content": self.system},
                {"role": "user", "content": [{"type": "text", "text": user},
                                             {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]}]
        text = self._call(msgs)
        retry = False
        if "```" not in text:  # one format reminder, then treat prose as a message to the user
            retry = True
            text2 = self._call(msgs + [{"role": "assistant", "content": text},
                                       {"role": "user", "content": "Reply with exactly one action inside a ```python code block```. "
                                                                   "If you are done, the action must be send_msg_to_user(...)."}])
            if "```" in text2:
                text = text2
            elif NARRATION.match(text2.strip()):
                # progress narration ("I'll open the invoice list...") is not a final answer: keep going
                text = f"{text2.strip()}\n```python\nnoop(500)\n```"
                retry = "narration_continue"
            else:
                text = f"```python\nsend_msg_to_user({text2.strip()!r})\n```"
        action = text.split("```python")[-1].split("```")[0].strip()
        self.history.append(f"step {len(self.history)}: {action}")
        return action, text, {"format_retry": retry}


class UITarsAgent:
    """UI-TARS-1.5 served by vLLM (OpenAI-compatible). Screenshot-only; emits coordinate actions."""
    PROMPT = ("You are a GUI agent. You are given a task and your action history, with screenshots. "
              "You need to perform the next action to complete the task.\n\n## Output Format\n```\nThought: ...\nAction: ...\n```\n\n"
              "## Action Space\nclick(start_box='<|box_start|>(x1,y1)<|box_end|>')\nleft_double(start_box='<|box_start|>(x1,y1)<|box_end|>')\n"
              "right_single(start_box='<|box_start|>(x1,y1)<|box_end|>')\n"
              "drag(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x3,y3)<|box_end|>')\n"
              "hotkey(key='')\ntype(content='') #If you want to submit your input, use \"\\n\" at the end of `content`.\n"
              "scroll(start_box='<|box_start|>(x1,y1)<|box_end|>', direction='down or up or right or left')\nwait()\n"
              "finished(content='xxx') # Use escape characters \\', \\\", and \\n in content part to ensure we can parse the content in normal python string format.\n\n"
              "## Note\n- Use English in `Thought` part.\n- Write a small plan and finally summarize your next action (with its target element) in one sentence in `Thought` part.\n\n"
              "## User Instruction\n")

    def __init__(self, base_url, app):
        self.client = OpenAI(base_url=base_url.rstrip("/") + "/v1", api_key=KEYS.get("VLLM_API_KEY", "none"))
        self.model = self.client.models.list().data[0].id
        self.app = app
        self.tok_in = self.tok_out = 0
        self.turns = []  # (b64, assistant_text)

    def cost(self):
        return 0.0  # GPU-seconds tracked separately via wall time

    def act(self, goal, obs, ax, jpg):
        from PIL import Image
        import io
        w, h = Image.open(io.BytesIO(jpg)).size
        b64 = base64.b64encode(jpg).decode()
        instr = f"{goal}\nIf the app asks you to log in, use email {self.app.CREDS[0]} and password {self.app.CREDS[1]}."
        msgs = [{"role": "user", "content": self.PROMPT + instr}]
        for pb64, ptext in self.turns[-4:]:  # keep last few screenshots, like the reference implementation
            msgs.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{pb64}"}}]})
            msgs.append({"role": "assistant", "content": ptext})
        msgs.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}]})
        r = self.client.chat.completions.create(model=self.model, messages=msgs, temperature=0.0, max_tokens=400)
        self.tok_in += r.usage.prompt_tokens; self.tok_out += r.usage.completion_tokens
        text = r.choices[0].message.content or ""
        self.turns.append((b64, text))
        return self._to_browsergym(text, w, h), text, {}

    @staticmethod
    def _to_browsergym(text, w, h):
        a = text.split("Action:")[-1].strip()

        def pt(s):
            m = re.findall(r"\(?\s*(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)\s*\)?", s)
            if not m:
                return None
            x, y = float(m[0][0]), float(m[0][1])
            # UI-TARS-1.5 emits absolute pixels in the Qwen2.5-VL smart-resized image (multiples of 28); map back
            rh, rw = max(28, round(h / 28) * 28), max(28, round(w / 28) * 28)
            return round(x * w / rw, 1), round(y * h / rh, 1)

        if a.startswith("finished"):
            c = re.search(r"content='(.*)'\)?\s*$", a, re.S)
            return f"send_msg_to_user({(c.group(1) if c else a)!r})"
        if a.startswith(("click", "left_single", "left_double", "right_single")):
            p = pt(a)
            if not p:
                return "noop()"
            fn = {"left_double": "mouse_dblclick", "right_single": "mouse_click"}.get(a.split("(")[0], "mouse_click")
            extra = ", button='right'" if a.startswith("right_single") else ""
            return f"{fn}({p[0]}, {p[1]}{extra})"
        if a.startswith("type"):
            c = re.search(r"content='(.*)'\)?\s*$", a, re.S)
            s = (c.group(1) if c else "").encode().decode("unicode_escape")
            if s.endswith("\n"):
                return f"keyboard_type({s[:-1]!r})\nkeyboard_press('Enter')"
            return f"keyboard_type({s!r})"
        if a.startswith("hotkey"):
            k = re.search(r"key='([^']*)'", a)
            names = {"pagedown": "PageDown", "pageup": "PageUp", "enter": "Enter", "return": "Enter", "esc": "Escape",
                     "escape": "Escape", "ctrl": "Control", "control": "Control", "cmd": "Meta", "command": "Meta",
                     "alt": "Alt", "shift": "Shift", "tab": "Tab", "backspace": "Backspace", "delete": "Delete",
                     "space": "Space", "home": "Home", "end": "End", "up": "ArrowUp", "down": "ArrowDown",
                     "left": "ArrowLeft", "right": "ArrowRight", "arrowup": "ArrowUp", "arrowdown": "ArrowDown",
                     "arrowleft": "ArrowLeft", "arrowright": "ArrowRight"}
            keys = (k.group(1) if k else "").replace("+", " ").split()
            return f"keyboard_press({'+'.join(names.get(x.lower(), x) for x in keys)!r})"
        if a.startswith("scroll"):
            p = pt(a) or (w / 2, h / 2)
            d = re.search(r"direction='(\w+)'", a)
            d = d.group(1) if d else "down"
            dx, dy = {"down": (0, 500), "up": (0, -500), "right": (500, 0), "left": (-500, 0)}.get(d, (0, 500))
            return f"mouse_move({p[0]}, {p[1]})\nscroll({dx}, {dy})"
        if a.startswith("drag"):
            pts = re.findall(r"\((\d+),\s*(\d+)\)", a)
            if len(pts) >= 2:
                return f"mouse_drag_and_drop({pts[0][0]}, {pts[0][1]}, {pts[1][0]}, {pts[1][1]})"
        return "noop(500)"

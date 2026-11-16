# Adding an agent

The harness calls your agent once per step and executes the action it returns. There are three ways in.

## 1. A model on the OpenAI API

```bash
swm run --app odoo17 --model <model-name> --tag <model>/odoo17/clean
```

The built-in `OpenAIAgent` sends the task, the accessibility tree (element ids in brackets) and a screenshot,
and expects one action in a Python code block. Add the model's price to `PRICES` in `swm/agents.py` if you want
dollar costs in the report; otherwise cost is reported as 0.

## 2. An OpenAI-compatible server

Set these in `.env` (or export them), then use the model name your server expects:

```
OPENAI_BASE_URL=http://localhost:8000/v1
OPENAI_API_KEY=anything
```

This covers vLLM, Ollama, LiteLLM and OpenRouter. The model must accept image input.

For UI-TARS-1.5 specifically there is a dedicated screenshot-only agent that speaks its native action format:
`--model uitars:https://your-vllm-host`. `colab/serve_uitars.py` serves it from a Colab GPU.

## 3. Your own class

```bash
swm run --app odoo17 --model custom:my_pkg.my_agent:MyAgent --tag mine/odoo17/clean
```

`my_pkg` must be importable (install it, or run from a directory that contains it). The class is built as
`MyAgent(actions, app)` and needs:

```python
class MyAgent:
    def __init__(self, actions, app):
        self.tok_in = self.tok_out = 0        # read by the harness after the episode
        self.app = app                        # app.DISPLAY, app.BASE, app.CREDS (login, password)
        self.action_help = actions.describe(with_long_description=False, with_examples=True)

    def act(self, goal, obs, axtree_text, jpeg_bytes):
        """Return (action, raw_text, meta).

        goal          the task, as a bookkeeper would phrase it
        obs           the BrowserGym observation dict (url, last_action_error, screenshot array, ...)
        axtree_text   visible accessibility tree with [bid] element ids
        jpeg_bytes    the current screenshot, 1280x800
        action        BrowserGym high-level action code, e.g. "click('42')" or "fill('17', 'Acme Ltd')"
        raw_text      whatever you want logged as the model's output
        meta          dict merged into the step log
        """
        return "noop(500)", "", {}

    def cost(self):
        return 0.0
```

Rules the harness applies to every agent:

- **Finishing.** The episode ends when the agent calls `send_msg_to_user("...")`. For question tasks the message
  must contain the answer. An agent that never sends a message is counted as gave up or timed out.
- **Budget.** 30 steps by default (`--max-steps`).
- **Action space.** BrowserGym subsets `chat`, `bid`, `nav`, `coord`: element-id actions (`click`, `fill`,
  `select_option`), coordinate actions (`mouse_click`, `keyboard_type`), navigation and `send_msg_to_user`.
  Several actions separated by newlines run in sequence.
- **Sandbox.** Navigation to any host other than localhost is aborted.

## Sharing a result

Run all four apps in the clean condition with `--per-skill 8`, then:

```bash
swm export-results --out results/<your-model>_episodes.jsonl
```

and open a pull request with that file and the command lines you used.

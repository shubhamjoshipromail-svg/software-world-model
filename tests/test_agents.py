"""UI-TARS emits its own action syntax; the adapter must turn it into BrowserGym actions."""
from swm.agents import UITarsAgent, NARRATION

to_bg = UITarsAgent._to_browsergym


def test_click_maps_resized_coordinates_back_to_the_viewport():
    # 1280x800 viewport is seen by the model as 1288x812 (multiples of 28)
    assert to_bg("Thought: x\nAction: click(start_box='<|box_start|>(644,406)<|box_end|>')", 1280, 800) == "mouse_click(640.0, 400.0)"


def test_type_with_trailing_newline_presses_enter():
    assert to_bg("Action: type(content='Acme Ltd\\n')", 1280, 800) == "keyboard_type('Acme Ltd')\nkeyboard_press('Enter')"


def test_finished_becomes_a_message_to_the_user():
    assert to_bg("Action: finished(content='Invoice 0042')", 1280, 800) == "send_msg_to_user('Invoice 0042')"


def test_hotkey_and_scroll():
    assert to_bg("Action: hotkey(key='ctrl a')", 1280, 800) == "keyboard_press('Control+a')"
    assert to_bg("Action: scroll(start_box='(644,406)', direction='up')", 1280, 800) == "mouse_move(640.0, 400.0)\nscroll(0, -500)"


def test_unparseable_output_is_a_noop():
    assert to_bg("Action: think harder", 1280, 800) == "noop(500)"


def test_progress_narration_is_not_treated_as_a_final_answer():
    assert NARRATION.match("I'll open the invoice list next")
    assert not NARRATION.match("The invoice number is 0042")


class DummyAgent:
    """Smallest valid agent: used by the custom-loader test below and as a template."""
    tok_in = tok_out = 0

    def __init__(self, actions, app):
        self.actions, self.app = actions, app

    def act(self, goal, obs, axtree_text, jpeg_bytes):
        return "send_msg_to_user('done')", "", {}

    def cost(self):
        return 0.0


def test_custom_agent_is_loaded_from_module_and_class_name():
    from swm.agents import make_agent
    agent = make_agent(f"custom:{__name__}:DummyAgent", actions="ACTIONS", app="APP")
    assert isinstance(agent, DummyAgent) and agent.app == "APP"
    assert agent.act("goal", {}, "", b"")[0] == "send_msg_to_user('done')"

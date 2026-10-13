"""Real-world disruptions injected into the browser, seeded for reproducibility.

Each perturbation has .name, .install(page) (called once after login) and .on_step(page, step) (called before each action).
"""
import random

MODAL_JS = r"""
(() => {
  if (window.__swmModal) return; window.__swmModal = true;
  const show = () => {
    if (document.getElementById('swm-modal')) return;
    const o = document.createElement('div');
    o.id = 'swm-modal';
    o.setAttribute('role', 'dialog'); o.setAttribute('aria-modal', 'true'); o.setAttribute('aria-label', "What's new");
    o.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:2147483647;display:flex;align-items:center;justify-content:center';
    o.innerHTML = `<div style="background:#fff;padding:28px;border-radius:10px;max-width:440px;font-family:sans-serif">
      <h2 style="margin:0 0 10px">What's new in this release</h2>
      <p>We've redesigned invoice reminders and added new payment gateways. Take a quick tour?</p>
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px">
        <button id="swm-tour">Start tour</button><button id="swm-dismiss">Got it</button></div></div>`;
    document.body.appendChild(o);
    o.querySelector('#swm-dismiss').onclick = () => o.remove();
    o.querySelector('#swm-tour').onclick = () => { o.querySelector('p').textContent = 'Tour step 1 of 6: reminders live under Settings.'; };
  };
  window.__swmShowModal = show;
})();
"""


class Perturbation:
    name = "clean"

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def install(self, page):
        pass

    def on_step(self, page, step):
        """Return True if the page was changed (observation must be refreshed)."""
        return False


class Modal(Perturbation):
    """A 'What's new' dialog that blocks the UI, appearing at two random steps."""
    name = "modal"

    def install(self, page):
        self.at = set(self.rng.sample(range(1, 8), 2))
        page.context.add_init_script(MODAL_JS)
        page.evaluate(MODAL_JS)

    def on_step(self, page, step):
        if step in self.at:
            try:
                page.evaluate("window.__swmShowModal && window.__swmShowModal()")
                return True
            except Exception:
                pass
        return False


class FlakyNetwork(Perturbation):
    """1-4 s latency on API calls; 8% of API calls fail with HTTP 500 before reaching the server."""
    name = "flaky_network"

    def install(self, page):
        rng = self.rng

        def handler(route):
            if rng.random() < 0.08:
                return route.fulfill(status=500, content_type="application/json",
                                     body='{"message":"Server Error"}')
            page.wait_for_timeout(int(rng.uniform(1000, 4000)))
            return route.continue_()
        page.route("**/api/v1/**", handler)


class SessionExpiry(Perturbation):
    """Session is invalidated mid-task (cookies + local storage wiped); the app bounces to the login page."""
    name = "session_expiry"

    def install(self, page):
        self.at = self.rng.randint(2, 5)

    def on_step(self, page, step):
        if step == self.at:
            page.context.clear_cookies()
            page.evaluate("localStorage.clear(); sessionStorage.clear()")
            page.reload()
            page.wait_for_load_state("networkidle")
            return True
        return False


ALL = {"clean": Perturbation, "modal": Modal, "flaky_network": FlakyNetwork, "session_expiry": SessionExpiry}

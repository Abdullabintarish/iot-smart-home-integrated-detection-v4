"""Page logic smoke test with a Streamlit stand-in (see stub_streamlit.py).

Runs each page script against the real evidence with several widget states.
This exercises data access and arithmetic, not rendering; the rendering
smoke test with Streamlit's own AppTest is test_app_smoke.py.
"""
import unittest

from _common import DEMO, ensure_cache, ev
import stub_streamlit as stub

PAGES = DEMO / "pages"


class TestPagesWithStub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_cache()

    def run_page(self, name, presses=(), state=None, widgets=()):
        rec = stub.run_page(PAGES / name if name != "app.py" else DEMO / name,
                            presses=presses, state=state)
        self.assertEqual(rec.arrow_errors, [], name)
        errors = [c for c in rec.calls if c[0] == "error"]
        self.assertEqual(errors, [], name)
        for w in widgets:
            self.assertIn(w, rec.widgets, f"{name}: widget {w} missing")
        return rec

    def test_app_entry(self):
        rec = self.run_page("app.py")
        self.assertTrue(any(c[0] == "title" and "Integrated Information" in c[1][0]
                            for c in rec.calls))

    def test_overview(self):
        rec = self.run_page("1_overview.py")
        text = " ".join(str(c[1][0]) for c in rec.calls if c[0] == "markdown" and c[1])
        self.assertIn("fragmented baseline scored better", text)
        self.assertNotIn("integrated condition scored better", text)

    def test_replay_every_class(self):
        for cls in ev.classes_present():
            with self.subTest(cls=cls):
                self.run_page("2_replay.py", state={"replay_class": cls},
                              widgets=("replay_class", "replay_source", "replay_play",
                                       "replay_verify_btn"))

    def test_replay_verify_and_play(self):
        rec = self.run_page("2_replay.py", presses=("replay_verify_btn",),
                            state={"replay_class": "dos", "replay_source": "data_36"})
        self.assertTrue(any(c[0] == "markdown" and "lab-ok" in str(c[1][0]) for c in rec.calls))
        rec = self.run_page("2_replay.py", presses=("replay_play",),
                            state={"replay_class": "c2"})
        self.assertTrue(rec.state["replay_playing"])
        self.assertTrue(any(c[0] == "fragment" and c[2]["run_every"] for c in rec.calls))

    def test_correlation_modes(self):
        for mode in ("Largest incidents", "Random sample (seed 42)", "By label"):
            with self.subTest(mode=mode):
                rec = self.run_page("3_correlation.py", state={"corr_mode": mode},
                                    widgets=("corr_source", "corr_mode", "corr_incident"))
                self.assertTrue(any(c[0] == "markdown" and "lab-ok" in str(c[1][0])
                                    for c in rec.calls))
        iid = ev.incidents().nlargest(1, "n_events")["incident_id"].iloc[0]
        self.run_page("3_correlation.py", state={"corr_mode": "Paste an incident_id",
                                                 "corr_paste": iid})
        rec = self.run_page("3_correlation.py", state={"corr_mode": "Paste an incident_id",
                                                       "corr_paste": "0000000000000000"})
        self.assertTrue(any(c[0] == "warning" for c in rec.calls))

    def test_detection_filters(self):
        for state in ({}, {"det_outcome": "both wrong"}, {"det_class": "c2"},
                      {"det_capture": "data_1", "det_outcome": "integrated wrong only"},
                      {"det_typed": "3211495"}):
            with self.subTest(state=state):
                self.run_page("4_detection.py", state=state,
                              widgets=("det_capture", "det_class", "det_outcome"))

    def test_evidence(self):
        self.run_page("5_evidence.py", presses=("ev_rawhash",), state={"ev_hash": True},
                      widgets=("ev_cm_cond", "ev_cm_class", "ev_hash"))
        for cond in ("fragmented", "integrated"):
            for cls in ev.load_report()[cond]["classes"]:
                self.run_page("5_evidence.py", state={"ev_cm_cond": cond, "ev_cm_class": cls})


if __name__ == "__main__":
    unittest.main()

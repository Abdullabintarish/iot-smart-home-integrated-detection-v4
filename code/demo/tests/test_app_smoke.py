"""Streamlit smoke test with streamlit.testing.v1.AppTest (needs demo/.venv)."""
import unittest

from _common import DEMO, HAS_STREAMLIT, ensure_cache

PAGES = {
    "pages/1_overview.py": [],
    "pages/2_replay.py": [("selectbox", "replay_class"), ("selectbox", "replay_source"),
                          ("button", "replay_play"), ("button", "replay_verify_btn")],
    "pages/3_correlation.py": [("selectbox", "corr_source"), ("radio", "corr_mode"),
                               ("selectbox", "corr_incident")],
    "pages/4_detection.py": [("selectbox", "det_capture"), ("selectbox", "det_class"),
                             ("selectbox", "det_outcome")],
    "pages/5_evidence.py": [("radio", "ev_cm_cond"), ("selectbox", "ev_cm_class"),
                            ("toggle", "ev_hash")],
}


@unittest.skipUnless(HAS_STREAMLIT, "streamlit is not installed in this interpreter; "
                     "run the suite with demo/.venv/Scripts/python.exe")
class TestAppSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ensure_cache()

    def run_script(self, rel):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(DEMO / rel), default_timeout=300)
        at.run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertEqual(len(at.error), 0, [e.value for e in at.error])
        return at

    def test_app_default_page(self):
        at = self.run_script("app.py")
        self.assertTrue(any("Integrated Information" in t.value for t in at.title))

    def test_each_page(self):
        for rel, widgets in PAGES.items():
            with self.subTest(page=rel):
                at = self.run_script(rel)
                for kind, key in widgets:
                    getattr(at, kind)(key=key)       # KeyError if missing

    def test_navigation(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file(str(DEMO / "app.py"), default_timeout=300)
        at.run()
        for rel in PAGES:
            with self.subTest(page=rel):
                at.switch_page(rel).run()
                self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])

    def test_replay_verify_button(self):
        at = self.run_script("pages/2_replay.py")
        at.button(key="replay_verify_btn").click().run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        self.assertTrue(any("agree" in m.value for m in at.markdown))

    def test_detection_filter_change(self):
        at = self.run_script("pages/4_detection.py")
        at.selectbox(key="det_outcome").select("both wrong").run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])


if __name__ == "__main__":
    unittest.main()

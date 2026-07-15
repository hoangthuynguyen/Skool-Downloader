#!/usr/bin/env python3
"""Smoke tests Course OS modules (no network, no LLM)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


class CourseOSSmoke(unittest.TestCase):
    def test_feature_registry(self):
        import course_features as F

        data = F.check_features()
        self.assertTrue(data["complete"], msg=data)
        self.assertGreaterEqual(data["ok"], 20)

    def test_pptx_write(self):
        import course_pptx as P

        td = Path(tempfile.mkdtemp())
        p = P.write_pptx(
            td / "t.pptx",
            [("Title", ["a", "b"]), ("Two", ["c"])],
            title="T",
        )
        self.assertTrue(p.exists())
        self.assertGreater(p.stat().st_size, 1000)

    def test_thumbs_render(self):
        import course_thumbs as T

        td = Path(tempfile.mkdtemp())
        p = T.render_thumb("Hello Course", "sub", td / "x.png")
        self.assertTrue(p.exists())

    def test_ab_rules(self):
        import course_ab as A

        v = A.rule_variants("Build agents", "learn")
        self.assertGreaterEqual(len(v["variants"]), 3)

    def test_status_empty_root(self):
        import course_status as S

        td = Path(tempfile.mkdtemp())
        st = S.collect_status(td)
        self.assertIn("progress", st)
        self.assertEqual(st["progress"]["done"], 0)

    def test_board_html(self):
        import course_board as B

        td = Path(tempfile.mkdtemp())
        data = {
            "course_title": "T",
            "chapters": [
                {
                    "number": 1,
                    "title": "C",
                    "goal": "g",
                    "lessons": [{"number": 1, "title": "L", "purpose": "p"}],
                }
            ],
        }
        p = B.export_html_board(td, data)
        txt = p.read_text(encoding="utf-8")
        self.assertIn("draggable", txt)
        self.assertIn("dragstart", txt)

    def test_finish_dry_run(self):
        import course_finish as F

        td = Path(tempfile.mkdtemp())
        res = F.finish(td, dry_run=True)
        self.assertTrue(res.get("dry_run"))
        self.assertIn("plan", res)

    def test_ops_budget(self):
        import course_ops as O

        td = Path(tempfile.mkdtemp())
        b = O.load_budget(td)
        self.assertIn("usd_cap", b)
        O.set_budget_cap(td, 12.5)
        self.assertEqual(O.load_budget(td)["usd_cap"], 12.5)

    def test_glossary_locale(self):
        import course_ops as O

        td = Path(tempfile.mkdtemp())
        O.set_locale_term(td, "es", "Workshop", "Taller")
        g = O.load_glossary(td)
        self.assertEqual(g["locale_terms"]["es"]["Workshop"], "Taller")


if __name__ == "__main__":
    unittest.main(verbosity=2)

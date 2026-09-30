#!/usr/bin/env python3
"""Testa recall_decision.py: corpus real PT/EN, normalização e limiar. Sem rede, stdlib."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import recall_decision as rd  # noqa: E402

RULES = Path(__file__).with_name("recall_rules.json")

FIRE = [
    "que decisoes ja tomamos sobre autenticacao e tokens?",  # PT sem acento
    "onde paramos na integração do gate?",                   # PT acentuado
    "o que combinamos sobre o token?",
    "que decidimos sobre sqlite?",
    "resumo do que fizemos até agora",
    "what did we decide about the auth flow?",
    "where did we leave off on the gate?",
    "remind me of the conventions we established",
]
SILENT = [
    "roda os testes do gate",
    "crie uma função que ordena uma lista",
    "continue",
    "ok",
    "o que a seção 2 do doc diz?",
    "fix the bug on line 40",
    "run the test suite",
]


class DecisionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def rules(self, data):
        path = self.tmp / "rules.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_fires_on_memory_prompts_pt_en(self):
        for prompt in FIRE:
            self.assertTrue(rd.needs_memory(prompt, rules=RULES), prompt)

    def test_silent_on_neutral_prompts(self):
        for prompt in SILENT:
            self.assertFalse(rd.needs_memory(prompt, rules=RULES), prompt)

    def test_accentless_and_case_insensitive(self):
        self.assertTrue(rd.needs_memory("que decisoes ja tomamos sobre tokens?", rules=RULES))
        self.assertTrue(rd.needs_memory("QUE DECIDIMOS SOBRE O TOKEN?", rules=RULES))
        self.assertEqual(rd.needs_memory("lembrar disso", rules=RULES),
                         rd.needs_memory("LEMBRAR disso", rules=RULES))

    def test_threshold_boundary(self):
        custom = self.rules({"version": 1, "threshold": 2.0, "signals": [
            {"pattern": "decid", "weight": 1.0},
            {"pattern": "que decid", "weight": 2.5}]})
        self.assertFalse(rd.needs_memory("vamos decidir isso", rules=custom))   # 1.0 < 2.0
        self.assertTrue(rd.needs_memory("que decidimos isso", rules=custom))    # 3.5 >= 2.0

    def test_default_rules_file_is_sibling(self):
        # sem arg rules → usa recall_rules.json ao lado do módulo
        self.assertTrue(rd.needs_memory("que decidimos sobre sqlite?"))


class FailOpenTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def rules(self, data):
        path = self.tmp / "rules.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_missing_rules_fails_open(self):
        self.assertTrue(rd.needs_memory("run the tests", rules=self.tmp / "nope.json"))

    def test_malformed_json_fails_open(self):
        bad = self.tmp / "broken.json"
        bad.write_text("{not json", encoding="utf-8")
        self.assertTrue(rd.needs_memory("run the tests", rules=bad))

    def test_empty_signals_fails_open(self):
        path = self.rules({"version": 1, "threshold": 2.0, "signals": []})
        self.assertTrue(rd.needs_memory("run the tests", rules=path))

    def test_wrong_types_fail_open(self):
        path = self.rules({"version": 1, "threshold": {"bad": 1},
                           "signals": [{"pattern": "x", "weight": 1}]})
        self.assertTrue(rd.needs_memory("run the tests", rules=path))

    def test_fail_open_warns_on_stderr(self):
        import contextlib
        import io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertTrue(rd.needs_memory("run the tests", rules=self.tmp / "nope.json"))
        self.assertIn("fail-open", err.getvalue())

    def test_weird_prompt_does_not_raise(self):
        # entrada fora do contrato não pode derrubar o hook
        self.assertFalse(rd.needs_memory("", rules=RULES))


if __name__ == "__main__":
    unittest.main()

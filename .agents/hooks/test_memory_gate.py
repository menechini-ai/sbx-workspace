#!/usr/bin/env python3
"""Testa memory_gate.py contra um ai-memory falso (49375). Sem GPU, sem rede, sem daemon."""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

GATE = Path(__file__).with_name("memory_gate.py")
STATE = {"calls": []}
CLEAN_PREFIXES = ("MEMORY_GATE", "CLAUDE_DECIDE")  # isola o teste de env do shell


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        STATE["calls"].append((payload["method"], self.headers.get("Authorization")))
        if payload["method"] == "tools/list":
            out = {"result": {"tools": [
                {"name": "memory_store", "inputSchema": {"properties": {"content": {"type": "string"}}}},
                {"name": "memory_recall", "inputSchema": {"properties": {"query": {"type": "string"}}}}]}}
        else:
            out = {"result": {"content": [{"type": "text",
                                           "text": f"decisao antiga sobre: {payload['params']['arguments']['query']}"}]}}
        out["jsonrpc"], out["id"] = "2.0", 1
        body = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class GateTest(unittest.TestCase):
    MATCHING = "que decidimos sobre sqlite?"   # dispara as regras
    NEUTRAL = "run the tests"                  # não dispara

    @classmethod
    def setUpClass(cls):
        server = HTTPServer(("127.0.0.1", 49375), Fake)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        cls.server = server

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def run_gate(self, prompt=None, **extra_env):
        clean = {k: v for k, v in os.environ.items() if not k.startswith(CLEAN_PREFIXES)}
        env = {**clean, "MEMORY_GATE_HOME": self.home,
               "AI_MEMORY_URL": "http://127.0.0.1:49375/mcp", "AI_MEMORY_TOKEN": "tok", **extra_env}
        event = {"hook_event_name": "UserPromptSubmit",
                 "prompt": self.MATCHING if prompt is None else prompt,
                 "cwd": ".", "session_id": "s"}
        return subprocess.run([sys.executable, str(GATE)], input=json.dumps(event), env=env,
                              capture_output=True, text=True, timeout=15)

    def setUp(self):
        STATE["calls"] = []
        self.home = tempfile.mkdtemp()
        Path(self.home, "memory_tool.json").unlink(missing_ok=True)

    def out(self, proc):
        return proc.stdout.strip()

    def test_injects_when_rules_match(self):
        proc = self.run_gate()
        data = json.loads(self.out(proc))
        ctx = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("decisao antiga sobre: que decidimos sobre sqlite?", ctx)
        self.assertIn("<ai-memory-recall>", ctx)
        self.assertEqual(data["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn(("tools/call", "Bearer tok"), STATE["calls"])

    def test_silent_when_rules_dont_match(self):
        proc = self.run_gate(prompt=self.NEUTRAL)
        self.assertEqual(self.out(proc), "")
        self.assertEqual(STATE["calls"], [])  # nem consultou o ai-memory

    def test_caches_tool_discovery(self):
        self.run_gate()
        self.run_gate()
        self.assertEqual([m for m, _ in STATE["calls"]].count("tools/list"), 1)

    def test_fails_silent_when_memory_down(self):
        proc = self.run_gate(AI_MEMORY_URL="http://127.0.0.1:1/mcp")
        self.assertEqual(self.out(proc), "")

    def test_corrupt_rules_fail_open_and_still_inject(self):
        bad = Path(tempfile.mkdtemp()) / "rules.json"
        bad.write_text("{not json", encoding="utf-8")
        proc = self.run_gate(prompt=self.NEUTRAL, MEMORY_GATE_RULES=str(bad))
        self.assertIn("fail-open", proc.stderr)          # aviso só em stderr
        self.assertIn("<ai-memory-recall>", self.out(proc))  # stdout continua JSON válido
        json.loads(self.out(proc))

    def test_reads_url_and_header_from_claude_config(self):
        home = tempfile.mkdtemp()
        Path(home, ".claude.json").write_text(json.dumps({"mcpServers": {"ai-memory": {
            "type": "http", "url": "http://127.0.0.1:49375/mcp",
            "headers": {"Authorization": "Bearer ${MEM_TOKEN}"}}}}))
        clean = {k: v for k, v in os.environ.items()
                 if not k.startswith(CLEAN_PREFIXES) and not k.startswith("AI_MEMORY")}
        env = {**clean, "HOME": home, "MEM_TOKEN": "from-env"}
        event = {"hook_event_name": "UserPromptSubmit", "prompt": self.MATCHING,
                 "cwd": home, "session_id": "s"}
        proc = subprocess.run([sys.executable, str(GATE)], input=json.dumps(event), env=env,
                              capture_output=True, text=True, timeout=15)
        self.assertIn("decisao antiga", proc.stdout)
        self.assertIn(("tools/call", "Bearer from-env"), STATE["calls"])

    def test_always_mode_skips_decision(self):
        proc = self.run_gate(prompt=self.NEUTRAL, MEMORY_GATE_MODE="always")
        self.assertIn("decisao antiga", self.out(proc))

    def test_off_mode_and_short_prompt(self):
        self.assertEqual(self.out(self.run_gate(MEMORY_GATE_MODE="off")), "")
        self.assertEqual(self.out(self.run_gate(prompt="ok")), "")

    def test_defaults_without_gate_env(self):
        # clone/template não definem MEMORY_GATE_* → regras + arquivo irmão
        clean = {k: v for k, v in os.environ.items()
                 if not k.startswith(CLEAN_PREFIXES) and not k.startswith("AI_MEMORY")}
        home = tempfile.mkdtemp()
        base = {"HOME": home, "AI_MEMORY_URL": "http://127.0.0.1:49375/mcp",
                "AI_MEMORY_TOKEN": "tok"}
        for prompt, expect in ((self.NEUTRAL, ""), (self.MATCHING, "decisao antiga")):
            event = {"hook_event_name": "UserPromptSubmit", "prompt": prompt,
                     "cwd": ".", "session_id": "s"}
            proc = subprocess.run([sys.executable, str(GATE)], input=json.dumps(event),
                                  env={**clean, **base}, capture_output=True, text=True, timeout=15)
            self.assertIn(expect, proc.stdout.strip())


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Decisão pura: este prompt precisa de memória de longo prazo?

Carrega recall_rules.json, normaliza o prompt (caixa + acentos), soma o peso
dos signals presentes e compara com threshold. Sem rede, sem estado.
Configuração inválida ainda LANÇA (o fail-open é adicionado no próximo task).
"""
import json
import unicodedata
from pathlib import Path

DEFAULT_RULES = Path(__file__).with_name("recall_rules.json")


def normalize(text):
    """Caixa baixa sem acentos: 'que decisoes' == 'Que Decisões'."""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.casefold()


def load_rules(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    threshold = float(data["threshold"])
    signals = [(normalize(s["pattern"]), float(s["weight"])) for s in data["signals"]]
    if not signals:
        raise ValueError("recall_rules.json sem signals")
    return threshold, signals


def needs_memory(prompt, rules=None):
    threshold, signals = load_rules(rules or DEFAULT_RULES)
    score = sum(weight for pattern, weight in signals if pattern in normalize(prompt))
    return score >= threshold

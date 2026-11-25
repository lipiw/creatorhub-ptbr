"""Regras de seguranca para DMs automaticas enviadas a quem comentou.

Evita linguagem que a Meta e as redes de afiliados (ex.: BuyGoods) costumam punir:
alegacoes de saude/cura, promessas de ganho e termos de urgencia agressiva.
"""
from __future__ import annotations

import re
import unicodedata

# Termos (sem acento, minusculos). Casamento por palavra inteira/prefixo.
FORBIDDEN_TERMS: tuple[str, ...] = (
    "cura", "curar", "curei", "curou", "milagre", "milagroso",
    "emagrece", "emagrecer", "emagreca", "perca peso", "perder peso", "queima gordura",
    "diabetes", "diabetico", "cancer", "pressao alta", "colesterol", "depressao",
    "ansiedade", "disfuncao", "impotencia",
    "garantido", "garantimos", "100% garantido", "sem risco",
    "ganhe dinheiro", "renda extra garantida", "fique rico", "dinheiro facil",
    "antes e depois",
)

MAX_DM_CHARS = 600


def _fold(text: str) -> str:
    norm = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in norm if not unicodedata.combining(ch)).lower()


def find_forbidden_terms(text: str) -> list[str]:
    """Devolve os termos proibidos encontrados no texto (lista vazia = ok)."""
    folded = _fold(text)
    hits: list[str] = []
    for term in FORBIDDEN_TERMS:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}", folded):
            hits.append(term)
    return hits


def validate_dm_templates(templates: list[str]) -> str:
    """Retorna mensagem de erro (PT-BR) ou string vazia se os modelos forem aceitaveis."""
    if not templates:
        return "Configure ao menos um texto de DM."
    for tpl in templates:
        if len(tpl) > MAX_DM_CHARS:
            return f"DM muito longa (maximo {MAX_DM_CHARS} caracteres)."
        hits = find_forbidden_terms(tpl)
        if hits:
            return (
                "O texto da DM contem termos arriscados (alegacao de saude/ganho): "
                + ", ".join(sorted(set(hits)))
                + ". Reescreva sem essas palavras."
            )
    return ""

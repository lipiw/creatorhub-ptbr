"""Extrator de strings i18n do CreatorHub (focado nas 4 redes: Facebook, Instagram, TikTok, YouTube).

Uso:
  python scripts/extract_i18n.py --check
  python scripts/extract_i18n.py --dump custom/i18n_missing.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = ROOT / "custom" / "pt-br-dict.json"

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
# Captura literais entre aspas ou textos entre tags HTML
HTML_TEXT_RE = re.compile(r">([^<>\n\r]*[\u4e00-\u9fff][^<>\n\r]*)<")
ATTR_RE = re.compile(r'(?:placeholder|title|aria-label|data-base-label|data-tooltip)="([^"]*[\u4e00-\u9fff][^"]*)"')
QUOTED_RE = re.compile(r"""(['"`])((?:\\.|(?!\1).)*?[\u4e00-\u9fff](?:\\.|(?!\1).)*?)\1""")

SKIP_KEYWORDS = (
    "抖音",
    "小红书",
    "海外小红书",
    "快手",
    "视频号",
    "哔哩哔哩",
    "B站",
    "弹幕",
    "Twitter",
    "推文",
    "X (",
    "微信通道",
    "douyin",
    "xhs",
    "kuaishou",
    "shipinhao",
    "bilibili",
)


def _should_skip(s: str) -> bool:
    if not s or not CJK_RE.search(s):
        return True
    if any(k in s for k in SKIP_KEYWORDS):
        return True
    if "${" in s or "<" in s or ">" in s:
        return True
    return False


def extract_all() -> Counter[str]:
    counts: Counter[str] = Counter()

    for f in (ROOT / "frontend" / "html").glob("*.html"):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for m in HTML_TEXT_RE.findall(txt) + ATTR_RE.findall(txt):
            s = re.sub(r"\s+", " ", m).strip()
            if not _should_skip(s):
                counts[s] += 1

    js_files = (
        list((ROOT / "frontend" / "app").glob("*.js"))
        + [
            p
            for p in (ROOT / "frontend").rglob("*")
            if p.suffix in (".jsx", ".js") and "app" not in p.parts and "desktop" not in p.parts
        ]
        + [ROOT / "app" / "web" / n for n in ("engine-settings.js", "workspace-ui.js", "submissions.js")]
    )
    for f in js_files:
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            st = line.strip()
            if st.startswith(("//", "/*", "*")):
                continue
            for _, val in QUOTED_RE.findall(st):
                s = val.strip()
                if not _should_skip(s):
                    counts[s] += 1

    for f in (ROOT / "app" / "api").glob("*.py"):
        for line in f.read_text(encoding="utf-8", errors="ignore").splitlines():
            st = line.strip()
            if st.startswith("#"):
                continue
            for _, val in QUOTED_RE.findall(st):
                s = val.strip()
                if not _should_skip(s):
                    counts[s] += 1

    return counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dump", type=str, default="")
    args = ap.parse_args()

    counts = extract_all()
    existing = set()
    if DICT_PATH.exists():
        d = json.loads(DICT_PATH.read_text(encoding="utf-8"))
        existing.update(d.get("exact", {}).keys())
        existing.update(p[0] for p in d.get("phrases", []))

    missing = [(s, c) for s, c in counts.most_common() if s not in existing]
    print(f"Total relevantes (4 redes): {len(counts)} | Ja traduzidas: {len(counts) - len(missing)} | Faltantes: {len(missing)}")

    if args.dump:
        out_path = ROOT / args.dump
        out_path.write_text(
            json.dumps({"missing": [{"src": s, "count": c} for s, c in missing]}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Salvo em {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

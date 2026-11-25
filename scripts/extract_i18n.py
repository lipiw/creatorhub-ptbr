"""Extrator i18n completo do CreatorHub (4 redes: Facebook, Instagram, TikTok, YouTube).

Extrai strings completas e template literals por camada para traducao sem falhas:
  python scripts/extract_i18n.py --check
  python scripts/extract_i18n.py --dump-buckets custom/_i18n_work
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICT_PATH = ROOT / "custom" / "pt-br-dict.json"
REGEX_PATH = ROOT / "custom" / "pt-br-regex.json"

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
HTML_TEXT_RE = re.compile(r">([^<>]*[\u4e00-\u9fff][^<>]*)<")
ATTR_RE = re.compile(
    r'(?:placeholder|title|aria-label|data-base-label|data-tooltip|data-title|alt)="([^"]*[\u4e00-\u9fff][^"]*)"'
)
# Literais simples '...' ou "..."
QUOTED_RE = re.compile(r"""(['"])((?:\\.|(?!\1).)*?[\u4e00-\u9fff](?:\\.|(?!\1).)*?)\1""")
# Template literals `...`
TEMPLATE_RE = re.compile(r"`((?:\\.|[^`])*)`", re.DOTALL)

SKIP_PLATFORMS = (
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
    "微信通道",
    "桌面微信",
    "Rednote",
    "douyin",
    "xhs",
    "kuaishou",
    "shipinhao",
    "bilibili",
)


def _skip(s: str) -> bool:
    if not s or not CJK_RE.search(s):
        return True
    if any(k in s for k in SKIP_PLATFORMS):
        return True
    return False


def _strip_html_noise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _extract_html() -> list[str]:
    seen: Counter[str] = Counter()
    for f in sorted((ROOT / "frontend" / "html").glob("*.html")):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        # Remove comentarios HTML
        txt = re.sub(r"<!--.*?-->", "", txt, flags=re.DOTALL)
        for m in HTML_TEXT_RE.findall(txt) + ATTR_RE.findall(txt):
            s = _strip_html_noise(m)
            if not _skip(s):
                seen[s] += 1
    return [k for k, _ in seen.most_common()]


def _extract_js_and_react():
    static_c: Counter[str] = Counter()
    tmpl_c: Counter[str] = Counter()
    react_c: Counter[str] = Counter()

    app_js = sorted((ROOT / "frontend" / "app").glob("*.js")) + [
        ROOT / "app" / "web" / n for n in ("engine-settings.js", "workspace-ui.js", "submissions.js")
    ]
    react_files = sorted(
        p
        for p in (ROOT / "frontend").rglob("*")
        if p.suffix in (".jsx", ".js") and "app" not in p.parts and "desktop" not in p.parts and p.name != "build.mjs"
    )

    for group_files, target_counter in [(app_js, static_c), (react_files, react_c)]:
        for f in group_files:
            if not f.exists():
                continue
            txt = f.read_text(encoding="utf-8", errors="ignore")
            # Remove comentarios de linha e bloco
            txt_clean = re.sub(r"/\*.*?\*/", "", txt, flags=re.DOTALL)
            txt_clean = re.sub(r"\{/\*.*?\*/\}", "", txt_clean, flags=re.DOTALL)
            lines = [ln for ln in txt_clean.splitlines() if not ln.strip().startswith("//")]
            body = "\n".join(lines)

            if f.suffix == ".jsx":
                for m in HTML_TEXT_RE.findall(body) + ATTR_RE.findall(body):
                    s = _strip_html_noise(m)
                    if not _skip(s) and "{" not in s and "}" not in s:
                        target_counter[s] += 1

            for _, val in QUOTED_RE.findall(body):
                s = _strip_html_noise(val)
                if not _skip(s) and "<" not in s and ">" not in s:
                    target_counter[s] += 1

            for tmpl in TEMPLATE_RE.findall(body):
                if not CJK_RE.search(tmpl):
                    continue
                # Quebra pedacos HTML dentro de template literals em fragmentos de texto ou placeholders ${...}
                parts = re.split(r"<[^>]+>", tmpl)
                for p in parts:
                    s = _strip_html_noise(p)
                    if _skip(s):
                        continue
                    if "${" in s:
                        norm = re.sub(r"\$\{[^}]+\}", "{VAR}", s)
                        if not _skip(norm):
                            tmpl_c[norm] += 1
                    else:
                        target_counter[s] += 1

    return (
        [k for k, _ in static_c.most_common()],
        [k for k, _ in react_c.most_common()],
        [k for k, _ in tmpl_c.most_common()],
    )


def _extract_api() -> list[str]:
    seen: Counter[str] = Counter()
    for f in sorted((ROOT / "app" / "api").glob("*.py")):
        txt = f.read_text(encoding="utf-8", errors="ignore")
        for line in txt.splitlines():
            st = line.strip()
            if st.startswith("#") or st.startswith('"""') or "logger." in st:
                continue
            for _, val in QUOTED_RE.findall(st):
                s = _strip_html_noise(val)
                if not _skip(s):
                    seen[s] += 1
    return [k for k, _ in seen.most_common()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dump-buckets", type=str, default="")
    args = ap.parse_args()

    html_s = _extract_html()
    js_s, react_s, tmpl_s = _extract_js_and_react()
    api_s = _extract_api()

    existing_exact = set()
    if DICT_PATH.exists():
        d = json.loads(DICT_PATH.read_text(encoding="utf-8"))
        existing_exact.update((d.get("exact") or {}).keys())

    all_exact = list(dict.fromkeys(html_s + js_s + react_s + api_s))
    missing_exact = [s for s in all_exact if s not in existing_exact]

    print(
        f"HTML={len(html_s)} | JS={len(js_s)} | React={len(react_s)} | API={len(api_s)} | "
        f"Templates={len(tmpl_s)} | Exact ja traduzidos={len(all_exact) - len(missing_exact)} | Faltantes={len(missing_exact)}"
    )

    if args.dump_buckets:
        out_dir = ROOT / args.dump_buckets
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "html_missing.json").write_text(
            json.dumps([s for s in html_s if s not in existing_exact], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "js_missing.json").write_text(
            json.dumps([s for s in js_s if s not in existing_exact], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "react_missing.json").write_text(
            json.dumps([s for s in react_s if s not in existing_exact], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "api_missing.json").write_text(
            json.dumps([s for s in api_s if s not in existing_exact], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (out_dir / "templates.json").write_text(json.dumps(tmpl_s, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Buckets salvos em {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

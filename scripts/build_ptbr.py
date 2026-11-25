"""Traduz os LITERAIS dos assets servidos (app/web/*) para PT-BR e grava em custom/dist/.

Os arquivos originais nunca sao alterados (merge com upstream continua limpo).
Uso:
  python scripts/build_ptbr.py            # gera custom/dist + relatorio de pendencias
  python scripts/build_ptbr.py --strict   # falha (exit 1) se sobrar CJK em literais
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CUSTOM = ROOT / "custom"
WEB = ROOT / "app" / "web"
DIST = CUSTOM / "dist"
CJK = re.compile(r"[㐀-鿿＀-￯　-〿]")
HAS_HAN = re.compile(r"[㐀-鿿]")
JS_FILES = ["app.js", "engine-settings.js", "workspace-ui.js", "submissions.js", "appearance.js", "workbench.js"]

EXACT: dict[str, str] = {}
REGEXES: list[tuple[re.Pattern[str], str]] = []


def load_dict() -> None:
    d = json.loads((CUSTOM / "pt-br-dict.json").read_text(encoding="utf-8"))
    EXACT.update(d.get("exact") or {})
    extra = CUSTOM / "pt-br-literals.json"
    if extra.exists():
        EXACT.update({norm(k): v for k, v in json.loads(extra.read_text(encoding="utf-8")).items()})
    for pat, tpl in json.loads((CUSTOM / "pt-br-regex.json").read_text(encoding="utf-8")):
        REGEXES.append((re.compile(pat), re.sub(r"\$(\d+)", r"\\\1", tpl)))


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


VARS = re.compile(r"\$\{(?:[^{}]|\{[^{}]*\})*\}|<[^>]+>")


def tr_text(s: str, depth: int = 0) -> str | None:
    """Traduz um trecho de texto puro. Retorna None se nao houver traducao completa/segura."""
    r = _tr_text(s, depth)
    if r is not None and sorted(VARS.findall(r)) != sorted(VARS.findall(s)):
        return None  # traducao corrompeu ${expr}/tags: rejeitada
    return r


def _tr_text(s: str, depth: int = 0) -> str | None:
    st = norm(s)
    if not HAS_HAN.search(st):
        return s
    hit = EXACT.get(st)
    if hit is not None:
        return hit
    if depth < 3:
        for pat, tpl in REGEXES:
            m = pat.search(st)
            if m:
                out = pat.sub(tpl, st)
                # traduz recursivamente grupos que ainda tenham chines
                if HAS_HAN.search(out):
                    out = _translate_leftovers(out, depth + 1)
                return out
    return None


def _translate_leftovers(s: str, depth: int) -> str:
    def rep(m: re.Match[str]) -> str:
        r = tr_text(m.group(0), depth)
        return r if r is not None else m.group(0)

    return re.sub(r"[㐀-鿿][^<>$\"'`{}]*", rep, s)


TAG = re.compile(r"(<[^>]+>)")


def tr_content(content: str, is_template: bool) -> str:
    """Traduz o conteudo bruto de um literal (sem as aspas)."""
    if not HAS_HAN.search(content):
        return content
    whole = tr_text(content)
    if whole is not None:
        return _keep_edges(content, whole)
    # divide em tags HTML e traduz cada fragmento de texto
    return _split_vars(content)


DELIM = re.compile(r"(\$\{(?:[^{}]|\{[^{}]*\})*\}|<[^>]*>|\'|[<>\"'`])")


ATTR_VAL = re.compile(r"""=(\\?["'])([^"'<>\\]*[㐀-鿿][^"'<>\\]*)(\\?["'])""")


def tr_tag(tag: str, pending: Counter | None = None) -> str:
    def rep(m: re.Match[str]) -> str:
        t = tr_text(m.group(2))
        if t is None:
            if pending is not None:
                record(m.group(2), pending)
            return m.group(0)
        return "=" + m.group(1) + _keep_edges(m.group(2), t) + m.group(3)

    return ATTR_VAL.sub(rep, tag)


def _split_vars(p: str) -> str:
    """Traduz os trechos de texto entre delimitadores (tags, ${...}, aspas)."""
    out = []
    for q in DELIM.split(p):
        if q.startswith("<") and q.endswith(">") and HAS_HAN.search(q):
            out.append(tr_tag(q))
            continue
        if DELIM.fullmatch(q) or not HAS_HAN.search(q):
            out.append(q)
            continue
        t = tr_text(q)
        out.append(_keep_edges(q, t) if t is not None else q)
    return "".join(out)


def _keep_edges(orig: str, new: str) -> str:
    lead = orig[: len(orig) - len(orig.lstrip())]
    trail = orig[len(orig.rstrip()) :]
    return lead + new + trail


# ---------------- Lexer JS minimo (strings, templates, comentarios, regex) -----------------
def translate_js(src: str, pending: Counter) -> str:
    out: list[str] = []
    i, n = 0, len(src)
    last_sig = ""  # ultimo token significativo (para distinguir regex de divisao)
    brace_stack: list[str] = []  # 't' = dentro de ${ } de template

    def read_template(j: int) -> int:
        """j aponta apos a crase; retorna indice apos a crase final, emitindo output traduzido."""
        buf: list[str] = []
        k = j
        while k < n:
            c = src[k]
            if c == "\\":
                buf.append(src[k : k + 2])
                k += 2
            elif c == "`":
                break
            elif c == "$" and src.startswith("${", k):
                depth, m = 1, k + 2
                while m < n and depth:
                    ch = src[m]
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                    elif ch in "\"'":
                        q = ch
                        m += 1
                        while m < n and src[m] != q:
                            m += 2 if src[m] == "\\" else 1
                    elif ch == "`":
                        m = read_template_len(m + 1)
                        continue
                    m += 1
                expr = src[k:m]
                if HAS_HAN.search(expr):
                    expr = translate_js(expr[2:-1], pending)
                    expr = "${" + expr + "}"
                buf.append(expr)
                k = m
            else:
                buf.append(c)
                k += 1
        raw = "".join(buf)
        res = tr_content(raw, True)
        if HAS_HAN.search(res):
            record(res, pending)
        out.append(res)
        return k

    def read_template_len(j: int) -> int:
        k = j
        while k < n and src[k] != "`":
            if src[k] == "\\":
                k += 2
                continue
            if src.startswith("${", k):
                depth, m = 1, k + 2
                while m < n and depth:
                    if src[m] == "{":
                        depth += 1
                    elif src[m] == "}":
                        depth -= 1
                    m += 1
                k = m
                continue
            k += 1
        return k + 1

    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            out.append(src[i:j])
            i = j
        elif c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append(src[i:j])
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            raw = src[i + 1 : j]
            res = tr_content(raw, False) if HAS_HAN.search(raw) else raw
            if HAS_HAN.search(res):
                record(res, pending)
            res = res.replace("\n", "\\n") if "\n" in res else res
            if c in res:  # protege aspas introduzidas pela traducao
                res = re.sub(r"(?<!\\)" + re.escape(c), "\\\\" + c, res)
            out.append(c + res + c)
            i = j + 1
            last_sig = "str"
        elif c == "`":
            out.append("`")
            k = read_template(i + 1)
            out.append("`")
            i = k + 1
            last_sig = "str"
        elif c == "/" and (last_sig in ("", "(", ",", "=", ":", "[", "!", "&", "|", "?", "{", "}", ";", "return", "typeof", "=>")):
            j = i + 1
            in_cls = False
            while j < n and (src[j] != "/" or in_cls) and src[j] != "\n":
                if src[j] == "\\":
                    j += 1
                elif src[j] == "[":
                    in_cls = True
                elif src[j] == "]":
                    in_cls = False
                j += 1
            j += 1
            while j < n and src[j].isalpha():
                j += 1
            out.append(src[i:j])
            i = j
            last_sig = "re"
        elif c.isalnum() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            word = src[i:j]
            out.append(word)
            i = j
            last_sig = word if word in ("return", "typeof") else "id"
        else:
            out.append(c)
            i += 1
            if not c.isspace():
                last_sig = "=>" if src[i - 2 : i] == "=>" else c
    return "".join(out)


SKIP_NETS = ("抖音", "小红书", "快手", "视频号", "哔哩", "B站", "弹幕", "微信通道", "微信", "Twitter", "推文")


def record(res: str, pending: Counter) -> None:
    for q in DELIM.split(res):
        if q.startswith("<") and q.endswith(">"):
            for m in ATTR_VAL.finditer(q):
                record(m.group(2), pending)
            continue
        t = norm(q)
        if not DELIM.fullmatch(q) and HAS_HAN.search(t) and not any(k in t for k in SKIP_NETS):
            pending[t] += 1


# --------------------------- HTML ---------------------------
def translate_html(src: str, pending: Counter) -> str:
    # texto entre tags (fora de <script>/<style>) + atributos relevantes
    def attr(m: re.Match[str]) -> str:
        t = tr_text(m.group(3))
        if t is None:
            record(m.group(3), pending)
            return m.group(0)
        return f'{m.group(1)}{m.group(2)}"{t.replace(chr(34), "&quot;")}"'

    def text(m: re.Match[str]) -> str:
        t = tr_text(m.group(1))
        if t is None:
            record(m.group(1), pending)
            return m.group(0)
        return ">" + _keep_edges(m.group(1), t) + "<"

    pieces = re.split(r"(<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>)", src, flags=re.S | re.I)
    res = []
    for p in pieces:
        if re.match(r"<script\b", p, re.I):
            m = re.match(r"(<script\b[^>]*>)(.*?)(</script>)", p, re.S | re.I)
            res.append(m.group(1) + translate_js(m.group(2), pending) + m.group(3) if m else p)
        elif re.match(r"<style\b", p, re.I):
            res.append(p)
        else:
            p = re.sub(r"(\s)((?:placeholder|title|aria-label|alt|data-[\w-]+)=)\"([^\"]*[㐀-鿿][^\"]*)\"", attr, p)
            p = re.sub(r">([^<>]*[㐀-鿿][^<>]*)<", text, p)
            res.append(p)
    return "".join(res)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--report", type=int, default=40)
    args = ap.parse_args()
    load_dict()
    DIST.mkdir(exist_ok=True)
    total = Counter()
    for name in ["index.html"] + JS_FILES:
        f = WEB / name
        if not f.exists():
            continue
        pending: Counter = Counter()
        src = f.read_text(encoding="utf-8")
        out = translate_html(src, pending) if name.endswith(".html") else translate_js(src, pending)
        if name.endswith(".html"):
            out = out.replace('<html lang="zh-CN"', '<html lang="pt-BR"', 1)
        (DIST / name).write_text(out, encoding="utf-8", newline="")
        print(f"{name}: {len(src)//1024}KB -> pendentes={sum(pending.values())} unicos={len(pending)}")
        total.update(pending)
    print(f"TOTAL pendentes unicos={len(total)}")
    for k, v in total.most_common(args.report):
        print(f"  {v:3d}  {k}")
    (DIST / "pending.json").write_text(json.dumps(sorted(total), ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if (args.strict and total) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())

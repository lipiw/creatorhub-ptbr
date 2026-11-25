"""Plugin desacoplado para manter CreatorHub em Portugues (PT-BR) e restrito a 4 redes
(Facebook, Instagram, TikTok, YouTube) sem editar dezenas de arquivos do repositorio oficial.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

CUSTOM_DIR = Path(__file__).resolve().parent
DEFAULT_ALLOWED = ("facebook", "instagram", "tiktok", "youtube")
ALL_KNOWN_PLATFORMS = {
    "douyin",
    "xhs",
    "rednote",
    "kuaishou",
    "shipinhao",
    "tiktok",
    "bilibili",
    "instagram",
    "twitter",
    "facebook",
    "youtube",
}
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
TRANSLATABLE_KEYS = {"detail", "message", "error", "status_label", "reason", "warning", "proxy_warning", "hint"}


def _load_i18n():
    exact: dict[str, str] = {}
    phrases: list[tuple[str, str]] = []
    regexes: list[tuple[re.Pattern[str], str]] = []
    try:
        d = json.loads((CUSTOM_DIR / "pt-br-dict.json").read_text(encoding="utf-8"))
        exact = d.get("exact") or {}
        phrases = sorted(((p[0], p[1]) for p in (d.get("phrases") or [])), key=lambda x: len(x[0]), reverse=True)
    except Exception:
        pass
    try:
        r_list = json.loads((CUSTOM_DIR / "pt-br-regex.json").read_text(encoding="utf-8"))
        for pat, tpl in r_list:
            # Converte $1 para \1 do Python
            py_tpl = re.sub(r"\$(\d+)", r"\\\1", tpl)
            regexes.append((re.compile(pat), py_tpl))
    except Exception:
        pass
    return exact, phrases, regexes


EXACT_MAP, PHRASE_LIST, REGEX_LIST = _load_i18n()


def _translate_str(s: str) -> str:
    if not s or not CJK_RE.search(s):
        return s
    st = re.sub(r"\s+", " ", s).strip()
    if st in EXACT_MAP:
        return s.replace(s.strip(), EXACT_MAP[st])
    for pat, tpl in REGEX_LIST:
        if pat.search(st):
            return s.replace(s.strip(), pat.sub(tpl, st))
    return s


def get_allowed_platforms() -> tuple[str, ...]:
    raw = os.getenv("CREATORHUB_ALLOWED_PLATFORMS", "").strip()
    if not raw:
        return DEFAULT_ALLOWED
    items = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
    return items or DEFAULT_ALLOWED


def _transform_json(obj, allowed: set[str], filter_platforms: bool):
    if isinstance(obj, list):
        out = []
        for item in obj:
            if filter_platforms and isinstance(item, dict):
                pf = item.get("platform") or item.get("pf")
                if isinstance(pf, str) and pf.lower() in ALL_KNOWN_PLATFORMS and pf.lower() not in allowed:
                    continue
            out.append(_transform_json(item, allowed, filter_platforms))
        return out
    if isinstance(obj, dict):
        new_d = {}
        for k, v in obj.items():
            if filter_platforms and isinstance(k, str) and k.lower() in ALL_KNOWN_PLATFORMS and k.lower() not in allowed:
                continue
            if isinstance(v, str) and k in TRANSLATABLE_KEYS:
                new_d[k] = _translate_str(v)
            else:
                new_d[k] = _transform_json(v, allowed, filter_platforms)
        return new_d
    return obj


DIST_DIR = CUSTOM_DIR / "dist"
DIST_NAMES = {"app.js", "engine-settings.js", "workspace-ui.js", "submissions.js", "appearance.js", "workbench.js"}


def ensure_dist() -> None:
    """Regenera custom/dist quando assets de app/web ou dicionarios forem mais novos."""
    try:
        web = CUSTOM_DIR.parent / "app" / "web"
        srcs = [p for p in web.iterdir() if p.suffix in (".js", ".html")] + [
            CUSTOM_DIR / "pt-br-dict.json", CUSTOM_DIR / "pt-br-regex.json", CUSTOM_DIR.parent / "scripts" / "build_ptbr.py"]
        marker = DIST_DIR / "index.html"
        if marker.exists() and marker.stat().st_mtime >= max(p.stat().st_mtime for p in srcs):
            return
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_ptbr", CUSTOM_DIR.parent / "scripts" / "build_ptbr.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        import sys as _sys
        old = _sys.argv
        _sys.argv = ["build_ptbr", "--report", "0"]
        try:
            mod.main()
        finally:
            _sys.argv = old
    except Exception as exc:  # fallback: overlay de runtime continua funcionando
        print(f"[pt-br] falha ao gerar dist: {exc}")


class PtBrAndPlatformOverlayMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        allowed = set(get_allowed_platforms())
        path = request.url.path

        if path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH"):
            q_pf = (request.query_params.get("platform") or "").strip().lower()
            if q_pf and q_pf in ALL_KNOWN_PLATFORMS and q_pf not in allowed:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Plataforma '{q_pf}' desativada nesta versao (permitidas: {', '.join(sorted(allowed))})."},
                )

        if path.startswith("/static/") and path[8:] in DIST_NAMES and (DIST_DIR / path[8:]).exists():
            return Response(
                content=(DIST_DIR / path[8:]).read_bytes(),
                media_type="application/javascript; charset=utf-8",
                headers={"Cache-Control": "no-cache"},
            )

        response = await call_next(request)
        content_type = response.headers.get("content-type", "")

        if path in ("/", "/index.html") and "text/html" in content_type:
            body_chunks = [chunk async for chunk in response.body_iterator]
            html = b"".join(body_chunks).decode("utf-8", errors="replace")
            if (DIST_DIR / "index.html").exists():
                html = (DIST_DIR / "index.html").read_text(encoding="utf-8")
            html = html.replace('<html lang="zh-CN"', '<html lang="pt-BR"', 1)
            inject = (
                f'\n<script>window.__CREATORHUB_ALLOWED_PLATFORMS__={json.dumps(list(allowed))};</script>'
                '\n<link rel="stylesheet" href="/custom/pt-br-overlay.css">'
                '\n<script src="/custom/pt-br-overlay.js" defer></script>'
                '\n<script src="/custom/fb-pages.js" defer></script>\n'
            )
            if "</head>" in html:
                html = html.replace("</head>", inject + "</head>", 1)
            else:
                html += inject
            headers = dict(response.headers)
            headers.pop("content-length", None)
            return Response(content=html.encode("utf-8"), status_code=response.status_code, headers=headers, media_type="text/html")

        if path.startswith("/api/") and "application/json" in content_type:
            filter_pf = any(
                seg in path
                for seg in (
                    "/matrix",
                    "/overview",
                    "/platforms",
                    "/health",
                    "/summary",
                    "/accounts",
                    "/diagnostics",
                    "/transport",
                    "/engine-settings",
                )
            )
            body_chunks = [chunk async for chunk in response.body_iterator]
            raw = b"".join(body_chunks)
            try:
                data = json.loads(raw.decode("utf-8"))
                transformed = _transform_json(data, allowed, filter_pf)
                new_raw = json.dumps(transformed, ensure_ascii=False).encode("utf-8")
                headers = dict(response.headers)
                headers.pop("content-length", None)
                return Response(content=new_raw, status_code=response.status_code, headers=headers, media_type="application/json")
            except Exception:
                return Response(content=raw, status_code=response.status_code, headers=dict(response.headers), media_type="application/json")

        return response


def install_pt_br_overlay(application: FastAPI) -> None:
    ensure_dist()
    application.add_middleware(PtBrAndPlatformOverlayMiddleware)
    application.mount("/custom", StaticFiles(directory=str(CUSTOM_DIR)), name="custom")

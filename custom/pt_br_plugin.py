"""Plugin desacoplado para manter CreatorHub em Portugues (PT-BR) e restrito a 4 redes
(Facebook, Instagram, TikTok, YouTube) sem editar dezenas de arquivos do repositorio oficial.

Instalado com apenas 2 linhas em `app/main.py`, preservando merges limpos com `upstream/main`.
"""
from __future__ import annotations

import json
import os
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


def get_allowed_platforms() -> tuple[str, ...]:
    raw = os.getenv("CREATORHUB_ALLOWED_PLATFORMS", "").strip()
    if not raw:
        return DEFAULT_ALLOWED
    items = tuple(p.strip().lower() for p in raw.split(",") if p.strip())
    return items or DEFAULT_ALLOWED


def _filter_json_platforms(obj, allowed: set[str]):
    if isinstance(obj, list):
        out = []
        for item in obj:
            if isinstance(item, dict):
                pf = item.get("platform") or item.get("pf")
                if isinstance(pf, str) and pf.lower() in ALL_KNOWN_PLATFORMS and pf.lower() not in allowed:
                    continue
            out.append(_filter_json_platforms(item, allowed))
        return out
    if isinstance(obj, dict):
        new_d = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in ALL_KNOWN_PLATFORMS and k.lower() not in allowed:
                continue
            new_d[k] = _filter_json_platforms(v, allowed)
        return new_d
    return obj


class PtBrAndPlatformOverlayMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        allowed = set(get_allowed_platforms())
        path = request.url.path

        # Bloqueia criacao de contas/monitores para plataformas desativadas
        if path.startswith("/api/") and request.method in ("POST", "PUT", "PATCH"):
            q_pf = (request.query_params.get("platform") or "").strip().lower()
            if q_pf and q_pf in ALL_KNOWN_PLATFORMS and q_pf not in allowed:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Plataforma '{q_pf}' desativada nesta versao (permitidas: {', '.join(sorted(allowed))})."},
                )

        response = await call_next(request)

        # Injeta overlay PT-BR + filtro de 4 redes no HTML principal em memoria
        content_type = response.headers.get("content-type", "")
        if path in ("/", "/index.html") and "text/html" in content_type:
            body_chunks = [chunk async for chunk in response.body_iterator]
            html = b"".join(body_chunks).decode("utf-8", errors="replace")
            html = html.replace('<html lang="zh-CN"', '<html lang="pt-BR"', 1)
            inject = (
                f'\n<script>window.__CREATORHUB_ALLOWED_PLATFORMS__={json.dumps(list(allowed))};</script>'
                '\n<link rel="stylesheet" href="/custom/pt-br-overlay.css">'
                '\n<script src="/custom/pt-br-overlay.js" defer></script>\n'
            )
            if "</head>" in html:
                html = html.replace("</head>", inject + "</head>", 1)
            else:
                html += inject
            headers = dict(response.headers)
            headers.pop("content-length", None)
            return Response(content=html.encode("utf-8"), status_code=response.status_code, headers=headers, media_type="text/html")

        # Filtra plataformas desativadas em respostas JSON de matriz/overview/resumo
        if path.startswith("/api/") and "application/json" in content_type and response.status_code == 200:
            if any(seg in path for seg in ("/matrix", "/overview", "/platforms", "/health", "/summary", "/accounts")):
                body_chunks = [chunk async for chunk in response.body_iterator]
                raw = b"".join(body_chunks)
                try:
                    data = json.loads(raw.decode("utf-8"))
                    filtered = _filter_json_platforms(data, allowed)
                    new_raw = json.dumps(filtered, ensure_ascii=False).encode("utf-8")
                    headers = dict(response.headers)
                    headers.pop("content-length", None)
                    return Response(content=new_raw, status_code=200, headers=headers, media_type="application/json")
                except Exception:
                    return Response(content=raw, status_code=response.status_code, headers=dict(response.headers), media_type="application/json")

        return response


def install_pt_br_overlay(application: FastAPI) -> None:
    application.add_middleware(PtBrAndPlatformOverlayMiddleware)
    application.mount("/custom", StaticFiles(directory=str(CUSTOM_DIR)), name="custom")

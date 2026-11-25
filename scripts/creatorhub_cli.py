#!/usr/bin/env python3
"""CLI do CreatorHub para agentes (Claude Code, Antigravity, scripts, cron).

So biblioteca padrao. Toda saida e JSON (uma linha por padrao, --pretty para
ler). Codigo de saida != 0 em erro, com {"error": ...} no stdout.

Ambiente:
  CREATORHUB_URL       base do painel (padrao http://localhost:8080)
  CREATORHUB_USER      usuario do Caddy (padrao admin)
  CREATORHUB_PASSWORD  senha (CH_PASSWORD do container)

Exemplos:
  creatorhub_cli.py accounts --platform facebook
  creatorhub_cli.py schedule --account 3 --video out/reel.mp4 \\
      --at 2026-12-01T19:30:00-03:00 --title "Titulo" --desc "Legenda" \\
      --topics "#dica #saude" --fb-page-id 123456789
  creatorhub_cli.py list --status pending
  creatorhub_cli.py run-now 42
  creatorhub_cli.py cancel 42

Reexecutar o MESMO comando nao duplica: a Idempotency-Key e derivada do
conteudo (arquivo, conta, horario, textos) e o caminho do upload fica em cache
(~/.creatorhub_cli_uploads.json, ou CREATORHUB_CLI_CACHE). Use --new para forcar
outra tarefa identica de proposito.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

# plataforma -> campo de opcoes especificas no corpo de POST /api/publish
OPTIONS_FIELD = {
    "facebook": "fb_options",
    "instagram": "ig_options",
    "youtube": "yt_options",
    "twitter": "tw_options",
    "bilibili": "bili_options",
}


class CliError(Exception):
    pass


def base_url() -> str:
    return os.environ.get("CREATORHUB_URL", "http://localhost:8080").rstrip("/")


def auth_header() -> dict:
    password = os.environ.get("CREATORHUB_PASSWORD", "")
    if not password:
        raise CliError("defina CREATORHUB_PASSWORD (a mesma CH_PASSWORD do container)")
    user = os.environ.get("CREATORHUB_USER", "admin")
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def request(method: str, path: str, *, body=None, headers=None, raw: bytes | None = None,
            timeout: int = 300):
    hdrs = {**auth_header(), **(headers or {})}
    data = raw
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(base_url() + path, data=data, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = resp.read()
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", "replace")
        try:
            detail = json.loads(text).get("detail", text)
        except ValueError:
            detail = text
        if exc.code == 401:
            detail = "usuario/senha invalidos (CREATORHUB_USER / CREATORHUB_PASSWORD)"
        raise CliError(f"HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise CliError(f"nao consegui conectar em {base_url()}: {exc.reason}") from exc


def _cache_file() -> Path:
    return Path(os.environ.get("CREATORHUB_CLI_CACHE") or Path.home() / ".creatorhub_cli_uploads.json")


def _cache_load() -> dict:
    try:
        return json.loads(_cache_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def upload(path: Path, digest: str) -> str:
    """Envia o arquivo e devolve o caminho que o painel usa em media_paths.

    O caminho devolvido e guardado por (servidor, hash do arquivo). Reexecutar o mesmo
    agendamento reaproveita esse caminho: o corpo da requisicao fica identico e o servidor
    reconhece a Idempotency-Key (se o corpo mudasse, ele responderia 409).
    """
    if not path.is_file():
        raise CliError(f"arquivo nao encontrado: {path}")
    cache_key = f"{base_url()}|{digest}"
    cache = _cache_load()
    if cache_key in cache:
        return cache[cache_key]
    boundary = uuid.uuid4().hex
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
            f"filename=\"{path.name}\"\r\nContent-Type: {ctype}\r\n\r\n").encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    raw = head + path.read_bytes() + tail
    out = request("POST", "/api/publish/upload", raw=raw,
                  headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                  timeout=1800)
    files = out.get("files") or []
    if not files:
        raise CliError("upload nao devolveu arquivo")
    cache[cache_key] = files[0]["path"]
    try:
        _cache_file().write_text(json.dumps(cache, indent=1), encoding="utf-8")
    except OSError:
        pass  # cache e so otimizacao de idempotencia
    return files[0]["path"]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_account(account_id: int) -> dict:
    accounts = request("GET", "/api/accounts")
    rows = accounts if isinstance(accounts, list) else accounts.get("accounts", accounts.get("items", []))
    for row in rows:
        if int(row.get("id", -1)) == account_id:
            return row
    raise CliError(f"conta {account_id} nao existe (veja: accounts)")


def brief_account(row: dict) -> dict:
    keys = ("id", "platform", "nickname", "name", "display_name", "account_role", "timezone_id",
            "login_status", "status", "proxy_id")
    return {k: row[k] for k in keys if k in row}


def cmd_health(_a):
    return request("GET", "/health")


def cmd_accounts(a):
    path = "/api/accounts" + (f"?platform={a.platform}" if a.platform else "")
    data = request("GET", path)
    rows = data if isinstance(data, list) else data.get("accounts", data.get("items", []))
    return rows if a.full else [brief_account(r) for r in rows]


def cmd_schedule(a):
    media_type = "video" if a.video else "images"
    sources = [Path(a.video)] if a.video else [Path(p) for p in (a.image or [])]
    if not sources and not (a.title or a.desc):
        raise CliError("informe --video, --image ou ao menos --title/--desc")
    account = find_account(a.account)
    platform = str(account.get("platform", "")).lower()

    options: dict = {}
    for item in a.opt or []:
        if "=" not in item:
            raise CliError(f"--opt espera CHAVE=VALOR, recebi: {item}")
        key, value = item.split("=", 1)
        options[key.strip()] = json.loads(value) if value[:1] in '[{"' or value in ("true", "false") else value
    if a.fb_page_id:
        options["page_id"] = a.fb_page_id
        options.setdefault("target_type", "page")
    if a.fb_target:
        options["target_type"] = a.fb_target
    if a.ai_label is not None:
        options["ai_label"] = a.ai_label  # sem a flag, vale o padrao do servidor (CREATORHUB_FB_AI_LABEL, ligado)
    if options and platform not in OPTIONS_FIELD:
        raise CliError(f"opcoes especificas nao se aplicam a plataforma '{platform}'")

    for p in sources:
        if not p.is_file():
            raise CliError(f"arquivo nao encontrado: {p}")
    digests = [file_sha256(p) for p in sources]
    # Chave determinista: mesmo conteudo -> mesma tarefa (repetir nao duplica).
    seed = json.dumps({
        "account": a.account, "at": a.at or "", "title": a.title or "", "desc": a.desc or "",
        "topics": a.topics or "", "options": options, "media": digests,
    }, sort_keys=True, ensure_ascii=False)
    key = "ch-" + hashlib.sha256(seed.encode()).hexdigest()[:40]
    if a.new:
        key = "ch-" + uuid.uuid4().hex

    media_paths = [upload(p, d) for p, d in zip(sources, digests)]
    body = {
        "account_id": a.account, "media_type": media_type, "title": a.title or "",
        "desc": a.desc or "", "topics": a.topics or "", "media_paths": media_paths,
        "scheduled_at": a.at or None,
    }
    if options:
        body[OPTIONS_FIELD[platform]] = options
    result = request("POST", "/api/publish", body=body, headers={"Idempotency-Key": key})
    result["_idempotency_key"] = key
    return result


def cmd_list(a):
    path = "/api/publish" + (f"?platform={a.platform}" if a.platform else "")
    rows = request("GET", path)
    rows = rows if isinstance(rows, list) else rows.get("items", rows.get("tasks", []))
    if a.status:
        rows = [r for r in rows if r.get("status") == a.status]
    keys = ("id", "platform", "account_id", "status", "scheduled_at", "title", "result_url", "error")
    return rows if a.full else [{k: r.get(k) for k in keys} for r in rows]


def cmd_get(a):
    for row in request("GET", "/api/publish"):
        if row.get("id") == a.id:
            return row
    raise CliError(f"tarefa {a.id} nao encontrada")


def cmd_update(a):
    body = {}
    for field in ("title", "desc", "topics"):
        if getattr(a, field) is not None:
            body[field] = getattr(a, field)
    if a.at is not None:
        body["scheduled_at"] = a.at or None
    if not body:
        raise CliError("nada para alterar (--at/--title/--desc/--topics)")
    return request("PUT", f"/api/publish/{a.id}", body=body)


def cmd_run_now(a):
    return request("POST", f"/api/publish/{a.id}/run-now")


def cmd_cancel(a):
    return request("DELETE", f"/api/publish/{a.id}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CLI do CreatorHub para agentes",
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--pretty", action="store_true", help="JSON indentado")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("health").set_defaults(fn=cmd_health)

    s = sub.add_parser("accounts", help="lista contas")
    s.add_argument("--platform")
    s.add_argument("--full", action="store_true")
    s.set_defaults(fn=cmd_accounts)

    s = sub.add_parser("schedule", help="sobe midia e agenda a publicacao")
    s.add_argument("--account", type=int, required=True)
    s.add_argument("--video")
    s.add_argument("--image", action="append")
    s.add_argument("--at", help="ISO com fuso, ex 2026-12-01T19:30:00-03:00 (sem fuso = fuso da conta; omitido = o quanto antes)")
    s.add_argument("--title")
    s.add_argument("--desc")
    s.add_argument("--topics")
    s.add_argument("--fb-page-id", help="Facebook: publica como esta Pagina")
    s.add_argument("--fb-target", choices=["profile", "page", "group", "story"])
    s.add_argument("--ai-label", action=argparse.BooleanOptionalAction, default=None,
                   help="Facebook: marca (ou nao) o post como conteudo de IA; padrao = configuracao do servidor (ligado)")
    s.add_argument("--opt", action="append", help="opcao especifica da plataforma CHAVE=VALOR (repetivel)")
    s.add_argument("--new", action="store_true", help="forca nova tarefa mesmo com conteudo identico")
    s.set_defaults(fn=cmd_schedule)

    s = sub.add_parser("list", help="lista tarefas de publicacao")
    s.add_argument("--platform")
    s.add_argument("--status")
    s.add_argument("--full", action="store_true")
    s.set_defaults(fn=cmd_list)

    s = sub.add_parser("get")
    s.add_argument("id", type=int)
    s.set_defaults(fn=cmd_get)

    s = sub.add_parser("update", help="altera horario/textos de tarefa pendente")
    s.add_argument("id", type=int)
    s.add_argument("--at")
    s.add_argument("--title")
    s.add_argument("--desc")
    s.add_argument("--topics")
    s.set_defaults(fn=cmd_update)

    s = sub.add_parser("run-now", help="publica agora uma tarefa agendada")
    s.add_argument("id", type=int)
    s.set_defaults(fn=cmd_run_now)

    s = sub.add_parser("cancel", help="remove a tarefa")
    s.add_argument("id", type=int)
    s.set_defaults(fn=cmd_cancel)
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    try:
        result = args.fn(args)
    except CliError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())

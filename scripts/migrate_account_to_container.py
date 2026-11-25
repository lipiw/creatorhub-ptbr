#!/usr/bin/env python3
"""Copia UMA conta ja logada do CreatorHub local (Windows) para o container Docker.

O login fica no banco (colunas storage_state / creator_storage_state / cookie), em JSON puro,
e nao no perfil do Chrome (esse e cifrado com a conta do Windows e nao migra). Ao abrir o
navegador com perfil vazio, o app injeta esse storage_state sozinho.

Copia so a linha da conta (nao o banco inteiro: historico e caminhos do Windows ficam de fora)
e normaliza profile_dir para barras normais. Os segredos passam por stdin do `docker exec`,
sem arquivo temporario.

Uso:
  python scripts/migrate_account_to_container.py --list
  python scripts/migrate_account_to_container.py --account-id 1 --dry-run
  python scripts/migrate_account_to_container.py --account-id 1
  python scripts/migrate_account_to_container.py --account-id 1 --replace   # sobrescreve no container

Antes: pare o CreatorHub local (a mesma sessao em dois lugares ao mesmo tempo confunde a plataforma).
Depois: rode o keepalive da conta no painel/API para confirmar o login.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys

REMOTE = r'''
import json, sqlite3, sys
row = json.load(sys.stdin)
replace = bool(row.pop("__replace__", False))
con = sqlite3.connect("/app/data/creatorhub.db")
cols = [r[1] for r in con.execute("pragma table_info(douyinaccount)")]
if set(row) != set(cols):
    sys.exit("esquema diferente entre local e container: " + str(sorted(set(row) ^ set(cols))))
exists = con.execute("select 1 from douyinaccount where id=?", (row["id"],)).fetchone()
if exists and not replace:
    sys.exit("ja existe conta id %s no container (use --replace)" % row["id"])
if exists:
    con.execute("delete from douyinaccount where id=?", (row["id"],))
con.execute("insert or ignore into accountidreservation(id) values (?)", (row["id"],))
con.execute("insert into douyinaccount(%s) values (%s)" % (",".join(cols), ",".join("?" * len(cols))),
            [row[c] for c in cols])
con.commit()
print("ok: conta id %s importada" % row["id"])
'''


def load_local(db: str):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="data/creatorhub.db")
    p.add_argument("--container", default="creatorhub")
    p.add_argument("--account-id", type=int)
    p.add_argument("--list", action="store_true", help="lista as contas locais")
    p.add_argument("--dry-run", action="store_true", help="mostra o resumo sem copiar")
    p.add_argument("--replace", action="store_true", help="sobrescreve a conta de mesmo id no container")
    a = p.parse_args()
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    con = load_local(a.db)
    if a.list or a.account_id is None:
        for r in con.execute("select id, platform, nickname, status from douyinaccount order by id"):
            print(f"{r['id']:>3}  {r['platform']:<10} {r['status']:<8} {r['nickname']}")
        return 0

    found = con.execute("select * from douyinaccount where id=?", (a.account_id,)).fetchone()
    if not found:
        print(f"conta {a.account_id} nao existe em {a.db}", file=sys.stderr)
        return 1
    row = dict(found)
    if not (row.get("storage_state") or row.get("creator_storage_state") or row.get("cookie")):
        print("a conta nao tem login salvo (storage_state vazio): faca o login no container", file=sys.stderr)
        return 1
    row["profile_dir"] = "data/profiles/" + str(row["profile_dir"] or "").replace("\\", "/").rstrip("/").split("/")[-1]
    try:
        cookies = len(json.loads(row.get("storage_state") or "{}").get("cookies", []))
    except ValueError:
        cookies = "?"
    print(f"conta {row['id']} | {row['platform']} | {row['nickname']} | cookies no storage_state: {cookies}"
          f" | proxy: {'sim' if row.get('proxy') else 'NENHUM (IP direto)'} | profile_dir: {row['profile_dir']}")
    if a.dry_run:
        print("dry-run: nada foi copiado")
        return 0

    row["__replace__"] = a.replace
    proc = subprocess.run(
        ["docker", "exec", "-i", "-u", "app", "-w", "/app", a.container, "python", "-c", REMOTE],
        input=json.dumps(row, default=str).encode("utf-8"), capture_output=True)
    out = proc.stdout.decode("utf-8", "replace").strip()
    err = proc.stderr.decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        print(err or out or "falha ao importar", file=sys.stderr)
        return 1
    print(out)
    print("Proximo passo: confirme o login com  POST /api/accounts/%s/keepalive  (ou pela CLI/painel)." % row["id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())

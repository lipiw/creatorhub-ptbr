# CreatorHub em container (segundo plano, sem abrir nada na sua tela)

O Chrome roda **com janela** dentro de uma tela virtual (Xvfb) no container. Você
acompanha pelo painel ou pela tela do navegador (noVNC), do PC ou do celular.

```
você / agentes ──► Caddy :8080 (senha) ─┬─► painel CreatorHub  (127.0.0.1:8000, só interno)
                                        └─► /vnc  noVNC ─► Xvfb :99 ◄── Chrome (Patchright)
```

## Subir (local)

```powershell
copy .env.example .env      # edite: CH_PASSWORD (mín. 12 caracteres)
docker compose up -d --build
```

- Painel: <http://localhost:8080> (usuário `admin`, senha = `CH_PASSWORD`)
- Tela do navegador: <http://localhost:8080/vnc>
- Logs: `docker compose logs -f`
- Parar / iniciar: `docker compose stop` / `docker compose start`

Tudo persistente (banco, perfis do Chrome com as sessões, vídeos, config) fica no
volume `creatorhub-data` (`/app/data`). `docker compose down` **mantém** o volume;
`docker compose down -v` **apaga tudo, inclusive os logins**.

## Contas: trazer a que já está logada (ou logar de novo)

**Trazer do Windows (recomendado, já testado):** o login fica no banco (`storage_state`, JSON), e o app
injeta isso sozinho quando abre o Chrome com perfil vazio. O que **não** migra é a pasta do perfil do
Chrome (cookies cifrados com a conta do Windows) — mas ela não é necessária.

```powershell
python scripts/migrate_account_to_container.py --list                    # contas locais
python scripts/migrate_account_to_container.py --account-id 1 --dry-run  # resumo, sem copiar
python scripts/migrate_account_to_container.py --account-id 1            # copia só essa conta
```

Depois confirme: `POST /api/accounts/<id>/keepalive` e/ou `open-browser` e veja em `/vnc`.
Antes de copiar, **pare o CreatorHub local** (mesma sessão nos dois lugares ao mesmo tempo confunde a
plataforma) e use a mesma saída de rede de antes (com Docker no seu PC, é o mesmo IP).

> Risco: o Chrome do container é Linux; a sessão nasceu num Chrome Windows. O Facebook costuma aceitar
> (o cookie `datr` do aparelho vai junto), mas pode pedir confirmação. Se pedir, faça o login pelo `/vnc`.

**Logar de novo no container** (contas novas ou se a plataforma recusar a sessão): inicie o login pelo
painel, abra `/vnc` em outra aba e faça o login (2FA etc.) na janela do Chrome. A sessão fica no volume.
Faça isso **com o proxy da conta já configurado**: login num IP e publicação em outro dispara checkpoint.

**Páginas do Facebook:** a lista de Páginas salvas do formulário fica no `localStorage` do navegador
(não no servidor), então começa vazia em cada origem nova (ex.: `localhost:8080`). Os IDs reais vêm de
`POST /api/facebook/pages {"account_id": 1}`; na CLI use `--fb-page-id <ID>` direto.

## Celular

O compose publica só em `127.0.0.1`. Duas formas seguras de chegar do celular:

- **Tailscale** (recomendado): instale no PC e no celular e abra `http://<ip-tailscale-do-pc>:8080`
  com `HOST_BIND=<ip-tailscale-do-pc>` no `.env`.
- **Cloudflare Tunnel**: `cloudflared tunnel --url http://localhost:8080`. A URL fica pública,
  então a senha precisa ser longa e única.
- Mesma rede Wi-Fi: `HOST_BIND=0.0.0.0` (qualquer um na rede chega no login; use senha forte).

> O painel **não tem login próprio**. Toda a proteção é a senha do Caddy. Nunca exponha
> a porta sem ela (o entrypoint recusa subir sem `CH_PASSWORD`).

## Agentes (Claude Code, Antigravity, scripts)

Use a CLI `scripts/creatorhub_cli.py` (só biblioteca padrão; toda saída é JSON):

```powershell
$env:CREATORHUB_URL="http://localhost:8080"; $env:CREATORHUB_PASSWORD="<CH_PASSWORD>"
python scripts/creatorhub_cli.py accounts --platform facebook
python scripts/creatorhub_cli.py schedule --account 3 --video C:\videos\reel.mp4 `
    --at 2026-12-01T19:30:00-03:00 --title "Titulo" --desc "Legenda" --topics "#dica" `
    --fb-page-id 123456789
python scripts/creatorhub_cli.py list --status pending
python scripts/creatorhub_cli.py run-now 42
python scripts/creatorhub_cli.py cancel 42
```

- Repetir o **mesmo** comando não duplica (a `Idempotency-Key` é derivada do conteúdo);
  use `--new` para criar outra tarefa idêntica de propósito.
- Sem fuso em `--at`, vale o fuso da conta; sem `--at`, publica o quanto antes.
- A API REST é a mesma que o painel usa (`/api/accounts`, `/api/publish`, ...), então
  qualquer agente com `curl -u admin:SENHA` também consegue.

## Rótulo de IA (Facebook)

Todo post do Facebook sai marcado como conteúdo de IA. O publicador abre "Criar post", clica em
**Rótulo de IA**, liga **Adicionar rótulo de IA**, confirma em **Entendi** e só segue se o botão passar a
dizer "Rótulo de IA ativado". Código: `custom/fb_page_switch.py` (overlay; o upstream não foi alterado).

- Padrão: **ligado** (`CREATORHUB_FB_AI_LABEL=1`). Para desligar tudo: `CREATORHUB_FB_AI_LABEL=0` no `.env`.
- Por post: `fb_options.ai_label` na API, ou `--ai-label` / `--no-ai-label` na CLI.
- **À prova de falha** (`CREATORHUB_FB_AI_LABEL_STRICT=1`): se o rótulo foi pedido e não pôde ser confirmado
  (o Facebook mudou a tela, por exemplo), a publicação **aborta antes de postar**, com erro
  `ai_label: ...`. Com `=0` ela só avisa no log e posta sem rótulo.
- Os textos reconhecidos são PT-BR e EN. Se o Facebook da conta estiver em outro idioma, ajuste
  `AI_CHIP_SELECTORS` / `AI_SWITCH_SELECTORS` / `AI_CONFIRM_SELECTORS`.
- Status: testado no compositor (liga, confirma, idempotente, falha segura). **Falta confirmar num post
  real** que o Reel publicado exibe o rótulo.

## Armadilhas conhecidas

- **Não abra o painel com `http://admin:senha@host/`.** O navegador passa a recusar todo `fetch()`
  ("URL que inclui credenciais") e o painel mostra "falha ao atualizar dados". Abra a URL limpa e
  digite usuário/senha na caixa que o navegador mostra.
- **Faixa "--no-sandbox" no Chrome:** o Patchright liga essa flag no Linux, então aparece o aviso
  "unsupported command-line flag" no topo da janela (é só visual; feche no X).
- **Diálogo de primeiros passos em chinês:** na primeira abertura num navegador novo, o assistente
  "Guia Inicial" aparece sem tradução. Feche; some depois (fica no `localStorage` do navegador).
  Alguns botões soltos também seguem em chinês (lacuna do overlay PT-BR, não do container).
- **Erros da API vêm em chinês** (ex.: 409 de idempotência). A CLI imprime em UTF-8, sem quebrar.
- **Pop-ups do Chrome:** a imagem traz uma política (`deploy/chrome-policy.json`) que bloqueia o pedido de
  notificações, a barra do Tradutor e o gerenciador de senhas do Chrome, que ficavam por cima do Facebook
  durante a publicação em Páginas.
- **Link do Reel publicado:** o app procura o post novo recarregando a Página. Antes devolvia o primeiro post do
  feed, que podia ser um antigo se o Reel ainda estivesse processando (o primeiro comentário iria para ele).
  Agora ele só aceita o post cuja **legenda** bate com a enviada (sem legenda: um post inédito e recente) e tenta
  até 5 vezes; se não achar com segurança, o resultado é a URL do perfil e o primeiro comentário é pulado.
- **Reset total:** `docker compose down -v` apaga o volume (inclui logins). Para só reiniciar, `docker compose restart`.

## Segurança (o que foi verificado)

- Sem senha ou com senha errada: `401` em tudo (painel, API, noVNC).
- O painel (8000) e o VNC (5900) **não** são publicados no host; só o Caddy (8080).
- Requisição de **outra origem** (`Origin` diferente ou `Sec-Fetch-Site: cross-site`) e WebSocket do
  noVNC de outro site: `403`. Isso substitui a defesa CSRF do painel, que o Caddy precisa desligar
  para ele aceitar acesso remoto. Abrir um link do painel vindo de outro app continua funcionando.
- O app e o Chrome rodam como `app` (uid 1000), não como root.

## Observações

- **Imagem só amd64** (o Google Chrome não tem build Linux arm64).
- O Chrome roda como usuário `app` (uid 1000) e não como root.
- Publicação em **Xiaohongshu** assina requisições com Node.js, que não está na imagem
  (fora das suas 4 redes). Se precisar, adicione `nodejs` ao `apt-get` do Dockerfile.
- **Railway** (depois): a mesma imagem sobe lá; defina `CH_PASSWORD`, monte um volume em
  `/app/data` e configure **proxy residencial por conta** — o IP do datacenter é o risco.

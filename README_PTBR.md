# CreatorHub — Versão PT-BR (Facebook, Instagram, TikTok, YouTube)

Clone personalizado de `3441293738/creatorhub` na branch `pt-br-4redes`, estruturado com **overlay desacoplado** (`custom/`) para receber atualizações do repositório oficial com risco mínimo de conflitos.

## O que foi personalizado
- **Somente 4 redes ativas:** `Facebook`, `Instagram`, `TikTok` e `YouTube` (controlado por `CREATORHUB_ALLOWED_PLATFORMS` em [custom/pt_br_plugin.py](custom/pt_br_plugin.py) e [custom/pt-br-overlay.css](custom/pt-br-overlay.css)).
- **Interface traduzida para Português (PT-BR):** tradução em tempo real via [custom/pt-br-dict.json](custom/pt-br-dict.json) + [custom/pt-br-overlay.js](custom/pt-br-overlay.js), sem modificar os arquivos fonte em `frontend/` ou `app/web/`.
- **Apenas 2 linhas tocadas no código oficial:** gancho em [app/main.py](app/main.py).

## Como iniciar localmente
```powershell
cd C:\Developer\creatorhub
.\start.cmd
```
Depois abra http://127.0.0.1:8000 (já abre em PT-BR e focado em Facebook / Instagram / TikTok / YouTube).

## Como atualizar com o repositório oficial (sem perder sua versão)
```powershell
cd C:\Developer\creatorhub
.\scripts\sync_upstream.ps1
```
Se quiser salvar em um **fork seu no GitHub**:
1. Faça o Fork de `https://github.com/3441293738/creatorhub` no GitHub.
2. Conecte seu fork como `origin`:
   ```powershell
   git remote add origin https://github.com/<SEU_USUARIO>/creatorhub.git
   git push -u origin pt-br-4redes
   ```

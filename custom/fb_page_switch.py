"""Correcao (fora do upstream) para publicar em Paginas do Facebook.

O fluxo original so grava o cookie `i_user`; no Facebook atual isso nao troca a identidade
e a Pagina abre em modo visitante (sem compositor). Este wrapper, apos o fluxo original,
abre a Pagina e clica no botao oficial "Trocar agora" / "Switch now".
"""
from __future__ import annotations

import asyncio

SWITCH_SELECTORS = (
    'div[role="main"] div[role="button"]:has-text("Trocar agora")',
    'div[role="main"] div[role="button"]:has-text("Switch now")',
    'div[role="button"]:has-text("Trocar agora")',
    'div[role="button"]:has-text("Switch now")',
    'div[role="button"]:has-text("立即切换")',
)
CONFIRM_SELECTORS = (
    'div[role="dialog"] div[role="button"]:has-text("Trocar")',
    'div[role="dialog"] div[role="button"]:has-text("Switch")',
)


async def _click_first(page, selectors, timeout_ms=6000):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            await loc.wait_for(state="visible", timeout=timeout_ms)
            await loc.click(timeout=4000)
            return True
        except Exception:
            continue
    return False


def install() -> None:
    try:
        from app.browser import facebook_fetcher as ff
    except Exception:
        return
    if getattr(ff, "_ptbr_switch_patched", False):
        return
    original = ff.switch_facebook_page_identity

    async def patched(ctx, page, page_id: str = ""):
        ok, err = await original(ctx, page, page_id)
        pid = str(page_id or "").strip()
        if not ok or not pid or page is None or page.is_closed():
            return ok, err
        try:
            await page.goto(f"https://www.facebook.com/profile.php?id={pid}",
                            wait_until="domcontentloaded", timeout=40000)
            await asyncio.sleep(3)
            if await _click_first(page, SWITCH_SELECTORS, 7000):
                await asyncio.sleep(1.5)
                await _click_first(page, CONFIRM_SELECTORS, 3000)
                await asyncio.sleep(5)
            try:  # fecha dialogos/popups que cobrem a Pagina (ex.: avisos, boas-vindas)
                for _ in range(3):
                    if not await page.locator('[role="dialog"]').count():
                        break
                    if not await _click_first(page, ('[role="dialog"] [aria-label="Fechar"]', '[role="dialog"] [aria-label="Close"]', '[role="dialog"] div[role="button"]:has-text("Agora não")', '[role="dialog"] div[role="button"]:has-text("Not now")'), 1500):
                        await page.keyboard.press("Escape")
                    await asyncio.sleep(1.2)
            except Exception:
                pass
        except Exception as exc:  # nao bloqueia: fluxo original segue
            print(f"[fb-switch] aviso: {exc!r}")
        return ok, err

    ff.switch_facebook_page_identity = patched
    try:  # gatilhos do compositor em portugues (o upstream so tem EN/ZH)
        from app.platforms.facebook import publish as fbpub
        extra = tuple(
            f'div[role="main"] div[role="button"]:has-text("{t}")'
            for t in ("No que você está pensando", "Escreva algo", "Criar post", "Criar publicação", "O que você está pensando")
        )
        fbpub.COMPOSER_TRIGGER_SELECTORS = tuple(fbpub.COMPOSER_TRIGGER_SELECTORS) + extra
    except Exception as exc:
        print(f"[fb-switch] seletores PT nao aplicados: {exc!r}")
    ff._ptbr_switch_patched = True

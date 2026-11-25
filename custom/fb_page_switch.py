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


class _RobustTyping:
    """Proxy do engine humano: digita a legenda por linha (insert_text + Enter) e valida o resultado.
    A digitacao tecla-a-tecla perdia trechos por causa do popup de hashtags do Facebook."""

    def __init__(self, engine):
        self._e = engine

    def __getattr__(self, name):
        return getattr(self._e, name)

    async def type_text(self, locator, text, page=None, clear=False, timeout=5000, **kw):
        if page is None:
            return await self._e.type_text(locator, text, page=page, clear=clear, timeout=timeout, **kw)
        await locator.click(timeout=timeout)
        lines = str(text).replace(chr(13) + chr(10), chr(10)).split(chr(10))
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.insert_text(line)
            if i < len(lines) - 1:
                await page.keyboard.press("Enter")
            await asyncio.sleep(0.15)
        await page.keyboard.press("Space")  # fecha o typeahead de hashtag sem fechar o dialogo
        await asyncio.sleep(0.8)
        got = " ".join((await locator.inner_text()).split())
        want = " ".join(str(text).split())
        if got.rstrip() != want.rstrip() and got[:40] != want[:40]:
            raise RuntimeError(f"legenda digitada divergente: {got[:80]!r}")
        if len(got) < len(want) * 0.9:
            raise RuntimeError(f"legenda incompleta ({len(got)}/{len(want)})")


async def _latest_post_link(page, target_url: str) -> str:
    """Recarrega a Pagina e le o post/Reel mais recente (o upstream lia a pagina sem recarregar e devolvia um post antigo)."""
    try:
        await asyncio.sleep(12)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(6)
        await page.evaluate("window.scrollBy({top: 500, behavior: 'smooth'})")
        await asyncio.sleep(2)
        href = await page.evaluate(r"""() => {
            for (const a of document.querySelectorAll('div[role="article"] a[href]')) {
                const h = a.href || '';
                if (/\/(posts|videos|reel|permalink\.php|photo|story\.php)\/?./i.test(h)) return h.split('?')[0];
            }
            return '';
        }""")
        return str(href or "").strip()
    except Exception:
        return ""


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
        btn = ':visible:not([aria-disabled="true"])'
        sub = tuple(
            f'div[role="dialog"] div[aria-label="{t}"][role="button"]{btn}'
            for t in ("Avançar", "Próximo", "Compartilhar", "Postar", "Publicar")
        ) + tuple(
            f'div[role="dialog"] div[role="button"]:has-text("{t}"){btn}'
            for t in ("Avançar", "Compartilhar", "Publicar")
        )
        fbpub.COMPOSER_SUBMIT_BUTTON_SELECTORS = sub + tuple(fbpub.COMPOSER_SUBMIT_BUTTON_SELECTORS)  # PT primeiro: has-text("Post") casava com "Adicionar ao post"
        fbpub.COMPOSER_PHOTO_BUTTON_SELECTORS = tuple(fbpub.COMPOSER_PHOTO_BUTTON_SELECTORS) + (
            'div[role="dialog"] div[role="button"][aria-label*="Foto/vídeo" i]',
        )
        fbpub.DEFAULT_HUMAN_ENGINE = _RobustTyping(fbpub.DEFAULT_HUMAN_ENGINE)
        fbpub._extract_latest_profile_post_link = _latest_post_link
    except Exception as exc:
        print(f"[fb-switch] seletores PT nao aplicados: {exc!r}")
    ff._ptbr_switch_patched = True

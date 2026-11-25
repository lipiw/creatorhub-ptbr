/* CreatorHub Overlay PT-BR + Filtro de 4 Redes (Facebook, Instagram, TikTok, YouTube) */
(function () {
  const ALLOWED = new Set(window.__CREATORHUB_ALLOWED_PLATFORMS__ || ["facebook", "instagram", "tiktok", "youtube"]);
  const HIDDEN_PFS = new Set(["douyin", "xhs", "rednote", "kuaishou", "shipinhao", "bilibili", "twitter"]);
  const HIDDEN_LABELS = ["抖音", "小红书", "海外小红书", "快手", "视频号", "哔哩哔哩", "Twitter", "B站", "Rednote"];
  const CJK_RE = /[\u4e00-\u9fff]/;

  let EXACT = {};
  let PHRASES = [];

  function translateText(raw) {
    if (!raw || !CJK_RE.test(raw)) return raw;
    const trimmed = raw.trim();
    if (Object.prototype.hasOwnProperty.call(EXACT, trimmed)) {
      return raw.replace(trimmed, EXACT[trimmed]);
    }
    let out = raw;
    for (let i = 0; i < PHRASES.length; i++) {
      const [src, dst] = PHRASES[i];
      if (out.includes(src)) out = out.split(src).join(dst);
    }
    return out;
  }

  function pruneHiddenPlatforms(root) {
    if (!root || !root.querySelectorAll) return;

    // 1. Oculta opcoes de <select> para redes desativadas
    root.querySelectorAll("option").forEach((opt) => {
      const v = (opt.value || "").toLowerCase();
      if (HIDDEN_PFS.has(v)) {
        opt.hidden = true;
        opt.disabled = true;
        opt.style.display = "none";
      }
    });

    // 2. Oculta botoes/cards/abas com data-pf ou data-platform desativado
    root.querySelectorAll("[data-pf], [data-platform]").forEach((el) => {
      const pf = (el.getAttribute("data-pf") || el.getAttribute("data-platform") || "").toLowerCase();
      if (HIDDEN_PFS.has(pf)) {
        el.style.display = "none";
      }
    });

    // 3. Oculta cards/chips React gerados dinamicamente com nome das redes chinesas/Twitter
    root.querySelectorAll("button, [role='tab'], .pf-card, .platform-card, .chip").forEach((el) => {
      if (el.closest(".pswitch")) return;
      const txt = (el.textContent || "").trim();
      if (HIDDEN_LABELS.some((lbl) => txt === lbl || txt.startsWith(lbl + " ") || txt.startsWith(lbl + "("))) {
        el.style.display = "none";
      }
    });
  }

  function translateNodeTree(root) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      const next = translateText(root.nodeValue);
      if (next !== root.nodeValue) root.nodeValue = next;
      return;
    }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    const tag = root.tagName;
    if (tag === "SCRIPT" || tag === "STYLE" || tag === "CODE" || tag === "PRE") return;

    for (const attr of ["placeholder", "title", "aria-label", "data-base-label"]) {
      const val = root.getAttribute(attr);
      if (val && CJK_RE.test(val)) {
        const next = translateText(val);
        if (next !== val) root.setAttribute(attr, next);
      }
    }
    if ((tag === "INPUT" || tag === "BUTTON") && root.value && CJK_RE.test(root.value)) {
      root.value = translateText(root.value);
    }

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
      const parentTag = node.parentElement && node.parentElement.tagName;
      if (parentTag === "SCRIPT" || parentTag === "STYLE") continue;
      const next = translateText(node.nodeValue);
      if (next !== node.nodeValue) node.nodeValue = next;
    }

    root.querySelectorAll("[placeholder], [title], [aria-label]").forEach((el) => {
      for (const attr of ["placeholder", "title", "aria-label"]) {
        const val = el.getAttribute(attr);
        if (val && CJK_RE.test(val)) {
          const next = translateText(val);
          if (next !== val) el.setAttribute(attr, next);
        }
      }
    });
  }

  function ensureAllowedDefaultPlatform() {
    try {
      const saved = (localStorage.getItem("creatorhub_platform") || localStorage.getItem("platform") || "").toLowerCase();
      if (saved && HIDDEN_PFS.has(saved)) {
        localStorage.setItem("creatorhub_platform", "facebook");
        localStorage.setItem("platform", "facebook");
      }
      if (typeof window.PLATFORM === "string" && HIDDEN_PFS.has(window.PLATFORM.toLowerCase())) {
        if (typeof window.switchPlatform === "function") {
          window.switchPlatform("facebook");
        }
      }
      const badge = document.getElementById("page-platform");
      if (badge && HIDDEN_LABELS.includes((badge.textContent || "").trim())) {
        if (typeof window.switchPlatform === "function") {
          window.switchPlatform("facebook");
        }
      }
    } catch (_) {}
  }

  async function init() {
    try {
      const res = await fetch("/custom/pt-br-dict.json", { cache: "no-cache" });
      if (res.ok) {
        const dict = await res.json();
        EXACT = dict.exact || {};
        PHRASES = (dict.phrases || []).sort((a, b) => b[0].length - a[0].length);
      }
    } catch (_) {}

    // Intercepta toast() global para traduzir avisos dinamicos
    if (typeof window.toast === "function" && !window.toast.__ptbrWrapped) {
      const origToast = window.toast;
      window.toast = function (msg, kind, ...rest) {
        return origToast.call(this, translateText(String(msg || "")), kind, ...rest);
      };
      window.toast.__ptbrWrapped = true;
    }

    pruneHiddenPlatforms(document.body);
    translateNodeTree(document.body);
    ensureAllowedDefaultPlatform();
    setTimeout(ensureAllowedDefaultPlatform, 400);

    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.type === "characterData") {
          translateNodeTree(m.target);
        } else if (m.type === "childList") {
          m.addedNodes.forEach((n) => {
            if (n.nodeType === Node.ELEMENT_NODE) pruneHiddenPlatforms(n);
            translateNodeTree(n);
          });
        }
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

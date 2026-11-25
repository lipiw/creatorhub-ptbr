/* CreatorHub Overlay PT-BR + Regex Dinamico + Filtro de 4 Redes */
(function () {
  const HIDDEN_PFS = new Set(["douyin", "xhs", "rednote", "kuaishou", "shipinhao", "bilibili", "twitter"]);
  const HIDDEN_LABELS = ["抖音", "小红书", "海外小红书", "快手", "视频号", "哔哩哔哩", "Twitter", "B站", "Rednote"];
  const CJK_RE = /[\u4e00-\u9fff]/;

  let EXACT = {};
  let PHRASES = [];
  let REGEXES = [];

  function translateText(raw) {
    if (!raw || !CJK_RE.test(raw)) return raw;
    const trimmed = raw.trim();
    if (Object.prototype.hasOwnProperty.call(EXACT, trimmed)) {
      return raw.replace(trimmed, EXACT[trimmed]);
    }
    for (let i = 0; i < REGEXES.length; i++) {
      const [re, tpl] = REGEXES[i];
      if (re.test(trimmed)) {
        const replaced = trimmed.replace(re, tpl);
        return raw.replace(trimmed, replaced);
      }
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

    root.querySelectorAll("option").forEach((opt) => {
      const v = (opt.value || "").toLowerCase();
      if (HIDDEN_PFS.has(v)) {
        opt.hidden = true;
        opt.disabled = true;
        opt.style.display = "none";
      }
    });

    root.querySelectorAll("[data-pf], [data-platform]").forEach((el) => {
      const pf = (el.getAttribute("data-pf") || el.getAttribute("data-platform") || "").toLowerCase();
      if (HIDDEN_PFS.has(pf)) {
        el.style.display = "none";
      }
    });

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

    for (const attr of ["placeholder", "title", "aria-label", "data-base-label", "data-tooltip", "data-title"]) {
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

    root.querySelectorAll("[placeholder], [title], [aria-label], [data-tooltip], [data-title]").forEach((el) => {
      for (const attr of ["placeholder", "title", "aria-label", "data-tooltip", "data-title"]) {
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
        if (typeof window.switchPlatform === "function") window.switchPlatform("facebook");
      }
      const badge = document.getElementById("page-platform");
      if (badge && HIDDEN_LABELS.includes((badge.textContent || "").trim())) {
        if (typeof window.switchPlatform === "function") window.switchPlatform("facebook");
      }
    } catch (_) {}
  }

  function auditRemainingCjk() {
    if (!location.search.includes("debug_i18n=1")) return;
    const found = new Set();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
    let n;
    while ((n = walker.nextNode())) {
      const p = n.parentElement;
      if (!p || p.offsetParent === null) continue;
      if (CJK_RE.test(n.nodeValue || "")) found.add(n.nodeValue.trim());
    }
    if (found.size > 0) console.warn("[PT-BR i18n audit] Restantes visiveis:", Array.from(found));
  }

  async function init() {
    try {
      const [dRes, rRes] = await Promise.all([
        fetch("/custom/pt-br-dict.json", { cache: "no-cache" }),
        fetch("/custom/pt-br-regex.json", { cache: "no-cache" }),
      ]);
      if (dRes.ok) {
        const dict = await dRes.json();
        EXACT = dict.exact || {};
        PHRASES = (dict.phrases || []).sort((a, b) => b[0].length - a[0].length);
      }
      if (rRes.ok) {
        const regs = await rRes.json();
        REGEXES = regs.map(([pat, tpl]) => [new RegExp(pat), tpl]);
      }
    } catch (_) {}

    if (typeof window.toast === "function" && !window.toast.__ptbrWrapped) {
      const origToast = window.toast;
      window.toast = function (msg, kind, ...rest) {
        return origToast.call(this, translateText(String(msg || "")), kind, ...rest);
      };
      window.toast.__ptbrWrapped = true;
    }

    const origAlert = window.alert;
    window.alert = (msg) => origAlert.call(window, translateText(String(msg || "")));
    const origConfirm = window.confirm;
    window.confirm = (msg) => origConfirm.call(window, translateText(String(msg || "")));

    pruneHiddenPlatforms(document.body);
    translateNodeTree(document.body);
    ensureAllowedDefaultPlatform();
    setTimeout(() => {
      ensureAllowedDefaultPlatform();
      auditRemainingCjk();
    }, 500);

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

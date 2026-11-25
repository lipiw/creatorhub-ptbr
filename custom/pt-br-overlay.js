/* CreatorHub Overlay PT-BR (Frases Completas + React TextNode Merge + Regex + Filtro 4 Redes) */
(function () {
  const HIDDEN_PFS = new Set(["douyin", "xhs", "rednote", "kuaishou", "shipinhao", "bilibili", "twitter"]);
  const HIDDEN_LABELS = ["抖音", "小红书", "海外小红书", "快手", "视频号", "哔哩哔哩", "Twitter", "B站", "Rednote", "视频号微信通道"];
  const HIDDEN_FIELD_PREFIXES = [
    "eng-backfill-mode",
    "engine-danmaku_",
    "engine-xhs_",
    "engine-douyin_",
    "engine-bilibili_",
    "engine-shipinhao_",
    "engine-channels_",
    "engine-rednote_",
    "engine-kuaishou_",
    "engine-twitter_",
  ];
  const CJK_RE = /[\u4e00-\u9fff]/;
  const INLINE_OK = new Set(["SPAN", "B", "STRONG", "EM", "SMALL", "KBD", "I"]);

  let EXACT = {};
  let REGEXES = [];
  let isMutatingDom = false;

  function translateText(raw) {
    if (!raw || !CJK_RE.test(raw)) return raw;
    const norm = raw.replace(/\s+/g, " ").trim();
    if (!norm) return raw;

    if (Object.prototype.hasOwnProperty.call(EXACT, norm)) {
      const lead = raw.match(/^\s*/)[0];
      const trail = raw.match(/\s*$/)[0];
      return lead + EXACT[norm] + trail;
    }

    for (let i = 0; i < REGEXES.length; i++) {
      const [re, tpl] = REGEXES[i];
      const match = norm.match(re);
      if (match) {
        const replaced = tpl.replace(/\$(\d+|\$)/g, (_, grp) => {
          if (grp === "$") return "$";
          const val = match[Number(grp)] || "";
          return CJK_RE.test(val) ? translateText(val) : val;
        });
        if (replaced !== norm) {
          const lead = raw.match(/^\s*/)[0];
          const trail = raw.match(/\s*$/)[0];
          return lead + replaced + trail;
        }
      }
    }
    return raw;
  }

  function pruneHiddenPlatforms(root) {
    if (!root || !root.querySelectorAll) return;

    // 1. Opcoes de <select>
    root.querySelectorAll("option").forEach((opt) => {
      const v = (opt.value || "").toLowerCase();
      if (HIDDEN_PFS.has(v)) {
        opt.hidden = true;
        opt.disabled = true;
        opt.style.display = "none";
      }
    });

    // 2. Elementos com data-pf / data-platform / data-section="channels"
    root.querySelectorAll("[data-pf], [data-platform], [data-section='channels'], [data-target-section='channels']").forEach((el) => {
      const pf = (el.getAttribute("data-pf") || el.getAttribute("data-platform") || "").toLowerCase();
      const sec = (el.getAttribute("data-section") || el.getAttribute("data-target-section") || "").toLowerCase();
      if (HIDDEN_PFS.has(pf) || sec === "channels") {
        el.style.display = "none";
      }
    });

    // 3. Abas/botoes/cards das redes ocultas (inclui aba 视频号微信通道 em Configuracoes)
    root.querySelectorAll("button, [role='tab'], .pf-card, .platform-card, .chip, .eng-pf-card").forEach((el) => {
      if (el.closest(".pswitch")) return;
      const txt = (el.textContent || "").trim();
      if (HIDDEN_LABELS.some((lbl) => txt === lbl || txt.startsWith(lbl + " ") || txt.startsWith(lbl + "(") || txt.startsWith(lbl + "\n"))) {
        el.style.display = "none";
      }
      const badge = el.querySelector && el.querySelector("[data-pf-badge]");
      if (badge && HIDDEN_PFS.has((badge.getAttribute("data-pf-badge") || "").toLowerCase())) {
        el.style.display = "none";
      }
    });

    // 4. Linhas da tabela de Diagnostico tecnico de redes desativadas
    root.querySelectorAll("tr").forEach((tr) => {
      const firstCell = tr.querySelector("td");
      if (!firstCell) return;
      const cellTxt = (firstCell.textContent || "").trim();
      if (HIDDEN_LABELS.includes(cellTxt)) {
        tr.style.display = "none";
      }
    });

    // 5. Campos de configuracao exclusivos das redes chinesas (Douyin/XHS/B站/Danmaku/WeChat)
    root.querySelectorAll("input[id], select[id]").forEach((inp) => {
      const id = inp.id || "";
      if (HIDDEN_FIELD_PREFIXES.some((p) => id.startsWith(p))) {
        const container = inp.closest(".form-field, .switch-row, label.switch-item, .field-group");
        if (container) container.style.display = "none";
      }
    });
  }

  // Trata elementos com multiplos TextNodes adjacentes gerados pelo React (ex: <span>跨 {0} 个已接入平台</span>)
  function tryTranslateSplitTextNodes(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return false;
    if (el.children.length !== 0 || el.childNodes.length <= 1) return false;
    const combined = el.textContent || "";
    if (!CJK_RE.test(combined)) return false;
    const translated = translateText(combined);
    if (translated === combined) return false;
    isMutatingDom = true;
    try {
      el.textContent = translated;
    } finally {
      isMutatingDom = false;
    }
    return true;
  }

  // Trata containers com filhos inline simples (ex: "自有已发作品 <b>0</b> 篇") preservando os nos filhos
  function tryTranslateInlineContainer(el) {
    if (!el || el.nodeType !== Node.ELEMENT_NODE) return false;
    if (el.children.length === 0) return tryTranslateSplitTextNodes(el);
    if (el.children.length > 4) return false;
    if (!CJK_RE.test(el.textContent || "")) return false;
    for (const ch of el.children) {
      if (!INLINE_OK.has(ch.tagName) || ch.children.length > 1) return false;
    }

    const savedNodes = [];
    let masked = "";
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        masked += node.nodeValue || "";
      } else if (node.nodeType === Node.ELEMENT_NODE) {
        const idx = savedNodes.length;
        savedNodes.push(node);
        masked += `\uE000${idx}\uE001`;
      }
    }

    const translated = translateText(masked);
    if (translated === masked || CJK_RE.test(translated)) return false;

    const parts = translated.split(/(\uE000\d+\uE001)/g);
    isMutatingDom = true;
    try {
      el.textContent = "";
      for (const part of parts) {
        const m = part.match(/^\uE000(\d+)\uE001$/);
        if (m) {
          const child = savedNodes[Number(m[1])];
          if (child) {
            translateNodeTree(child);
            el.appendChild(child);
          }
        } else if (part) {
          el.appendChild(document.createTextNode(part));
        }
      }
    } finally {
      isMutatingDom = false;
    }
    return true;
  }

  function translateAttrs(el) {
    for (const attr of ["placeholder", "title", "aria-label", "data-base-label", "data-tooltip", "data-title"]) {
      const val = el.getAttribute(attr);
      if (val && CJK_RE.test(val)) {
        const next = translateText(val);
        if (next !== val) el.setAttribute(attr, next);
      }
    }
    if ((el.tagName === "INPUT" || el.tagName === "BUTTON") && el.value && CJK_RE.test(el.value)) {
      const nextVal = translateText(el.value);
      if (nextVal !== el.value) el.value = nextVal;
    }
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

    translateAttrs(root);
    root.querySelectorAll("[placeholder], [title], [aria-label], [data-tooltip], [data-title], input, button, textarea").forEach(translateAttrs);

    // 1a passagem: containers com TextNodes divididos (React) ou filhos inline
    root.querySelectorAll("div, span, p, small, label, b, strong, h1, h2, h3, h4, li, td, th, summary, button, option").forEach((el) => {
      tryTranslateInlineContainer(el);
    });

    // 2a passagem: nos de texto puros restantes
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
      const parentTag = node.parentElement && node.parentElement.tagName;
      if (parentTag === "SCRIPT" || parentTag === "STYLE" || parentTag === "CODE" || parentTag === "PRE") continue;
      const next = translateText(node.nodeValue);
      if (next !== node.nodeValue) node.nodeValue = next;
    }
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
      // Garante que modais de login nunca caiam em "douyin" quando a tela esta em "all"
      for (const fnName of ["preparePreLoginEnvironment", "startQrLogin", "openQrLogin"]) {
        if (typeof window[fnName] === "function" && !window[fnName].__pfGuarded) {
          const orig = window[fnName];
          window[fnName] = function (pf, ...rest) {
            const targetPf = !pf || pf === "all" || HIDDEN_PFS.has(String(pf).toLowerCase()) ? "facebook" : pf;
            return orig.call(this, targetPf, ...rest);
          };
          window[fnName].__pfGuarded = true;
        }
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
    else console.info("[PT-BR i18n audit] 0 textos chineses visiveis nesta tela!");
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
      }
      if (rRes.ok) {
        const regs = await rRes.json();
        REGEXES = regs
          .map(([pat, tpl]) => {
            try {
              return [new RegExp(pat), tpl];
            } catch (_) {
              return null;
            }
          })
          .filter(Boolean);
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
      pruneHiddenPlatforms(document.body);
      translateNodeTree(document.body);
      ensureAllowedDefaultPlatform();
      auditRemainingCjk();
    }, 600);

    const observer = new MutationObserver((mutations) => {
      if (isMutatingDom) return;
      for (const m of mutations) {
        if (m.type === "attributes" && m.target && m.target.nodeType === Node.ELEMENT_NODE) {
          isMutatingDom = true;
          try {
            translateAttrs(m.target);
          } finally {
            isMutatingDom = false;
          }
        } else if (m.type === "characterData") {
          const p = m.target.parentElement;
          if (!p || !tryTranslateInlineContainer(p)) {
            translateNodeTree(m.target);
          }
        } else if (m.type === "childList") {
          m.addedNodes.forEach((n) => {
            if (n.nodeType === Node.ELEMENT_NODE) pruneHiddenPlatforms(n);
            translateNodeTree(n);
          });
          if (m.target && m.target.nodeType === Node.ELEMENT_NODE) {
            tryTranslateInlineContainer(m.target);
          }
        }
      }
    });
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["placeholder", "title", "aria-label", "data-tooltip", "data-title", "data-base-label"],
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

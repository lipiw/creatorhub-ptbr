/* Páginas do Facebook salvas: seletor ao lado do campo "ID da Página" (armazenado neste navegador). */
(() => {
  const KEY = "creatorhub.fb_pages.v1";
  const load = () => {
    try {
      const v = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(v) ? v.filter(p => p && /^\d{4,25}$/.test(String(p.id))) : [];
    } catch (e) { return []; }
  };
  const save = list => localStorage.setItem(KEY, JSON.stringify(list));

  function mount() {
    const input = document.getElementById("pub-fb-page-id");
    if (!input || input.dataset.pagesReady) return !!input;
    input.dataset.pagesReady = "1";

    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-top:6px";
    const sel = document.createElement("select");
    sel.setAttribute("aria-label", "Páginas salvas do Facebook");
    sel.style.cssText = "flex:1;min-width:180px";
    const mk = (txt, cls) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = cls || "ghost"; b.textContent = txt;
      return b;
    };
    const saveBtn = mk("Salvar Página");
    const delBtn = mk("Remover");
    wrap.append(sel, saveBtn, delBtn);
    input.insertAdjacentElement("afterend", wrap);

    const labelEl = document.querySelector('label[for="pub-fb-page-id"]');
    if (labelEl) labelEl.textContent = "ID da Página (opcional, troca de identidade via i_user)";
    input.placeholder = "Escolha uma Página salva ou informe o ID numérico da Página";

    function render(selectedId) {
      const list = load();
      sel.innerHTML = "";
      const o0 = new Option(list.length ? "— Selecionar Página salva —" : "Nenhuma Página salva", "");
      sel.add(o0);
      list.forEach(p => sel.add(new Option(`${p.name || "Página"} (${p.id})`, p.id)));
      sel.value = selectedId && list.some(p => p.id === selectedId) ? selectedId : "";
      delBtn.disabled = !sel.value;
    }

    const fire = el => { el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true })); };

    sel.addEventListener("change", () => {
      delBtn.disabled = !sel.value;
      if (!sel.value) return;
      input.value = sel.value;
      fire(input);
      const target = document.getElementById("pub-fb-target");
      if (target && target.value === "profile") { target.value = "page"; fire(target); }
    });

    saveBtn.addEventListener("click", () => {
      const id = input.value.trim();
      if (!/^\d{4,25}$/.test(id)) { alert("Informe o ID numérico da Página (somente números) antes de salvar."); return; }
      const list = load();
      const cur = list.find(p => p.id === id);
      const name = prompt("Nome para identificar esta Página:", cur ? cur.name : "");
      if (name === null) return;
      if (cur) cur.name = name.trim() || cur.name; else list.push({ id, name: name.trim() || "Página " + id });
      save(list);
      render(id);
    });

    delBtn.addEventListener("click", () => {
      if (!sel.value || !confirm("Remover esta Página da lista salva?")) return;
      save(load().filter(p => p.id !== sel.value));
      render("");
    });

    input.addEventListener("input", () => { sel.value = load().some(p => p.id === input.value.trim()) ? input.value.trim() : ""; delBtn.disabled = !sel.value; });
    render(input.value.trim());
    return true;
  }

  const tryMount = () => mount();
  if (!tryMount()) {
    const mo = new MutationObserver(() => { if (tryMount()) mo.disconnect(); });
    mo.observe(document.documentElement, { childList: true, subtree: true });
  }
})();

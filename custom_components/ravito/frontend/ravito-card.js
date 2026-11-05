/*
 * ravito-card — Ravito sur l'écran de la maison (Echo Show 8, ~960×600).
 * Fonctionne avec l'intégration "ravito".
 *
 * - Liste de courses : lecture seule (elle se modifie dans l'app).
 * - Menu de la semaine : ajouter, déplacer, retirer un plat.
 * - Recettes : liste, filtres, fiche ; « Ajouter au menu ».
 *
 * Aucun gestionnaire de toucher ni défilement horizontal : le balayage entre
 * les vues du tableau de bord reste libre. Kiosk Satellite ignore un balayage
 * commencé sur un <button> : les grandes zones tactiles sont des <div role="button">.
 */
const JOURS = ["Dimanche", "Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"];
const MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
const STOCK = {
  en_stock: ["✅", "Tout est en stock"],
  a_acheter: ["🛒", "À acheter"],
  manquera: ["❌", "Manquera"],
};
const RECIPES_TTL = 10 * 60 * 1000;
const MENU_TTL = 60 * 1000;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pad = (n) => String(n).padStart(2, "0");
const iso = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parseIso = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
const addDays = (d, n) => { const r = new Date(d); r.setDate(r.getDate() + n); return r; };
const monday = (d) => addDays(new Date(d.getFullYear(), d.getMonth(), d.getDate()), -((d.getDay() + 6) % 7));
const dayLabel = (d) => `${JOURS[d.getDay()]} ${d.getDate()}`;
const norm = (s) => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const minutes = (n) => (n ? (n >= 60 ? `${Math.floor(n / 60)} h${n % 60 ? pad(n % 60) : ""}` : `${n} min`) : "");

class RavitoCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._tab = "menu";
    this._week = 0;
    this._list = null;
    this._listStamp = null;
    this._menu = null;
    this._menuAt = 0;
    this._recipes = null;
    this._recipesAt = 0;
    this._base = "";
    this._search = "";
    this._tags = new Set();
    this._sheet = null; // {kind: 'add', day} | {kind: 'move', entry} | {kind: 'recipe', recipe} | {kind: 'plan', recipe}
    this._confirm = null;
    this._busy = false;
    this._error = "";
    this.shadowRoot.addEventListener("click", (e) => this._onClick(e));
    this.shadowRoot.addEventListener("input", (e) => this._onInput(e));
    this._onResize = () => this._fit();
  }

  setConfig(config) {
    this._config = { entity: "todo.ravito_liste_de_courses", ...config };
  }

  set hass(hass) {
    this._hass = hass;
    const st = hass.states[this._config.entity];
    // La liste n'est relue que si l'entité a changé
    const stamp = st ? st.last_updated : null;
    if (stamp !== this._listStamp) {
      this._listStamp = stamp;
      this._loadList();
    }
    if (!this._started) {
      this._started = true;
      this._loadMenu();
      this._render();
    }
  }

  connectedCallback() {
    window.addEventListener("resize", this._onResize);
    requestAnimationFrame(() => this._fit());
    this._timer = setInterval(() => {
      if (this._tab === "menu" && Date.now() - this._menuAt > MENU_TTL) this._loadMenu();
    }, 15000);
  }

  disconnectedCallback() {
    window.removeEventListener("resize", this._onResize);
    clearInterval(this._timer);
  }

  getCardSize() { return 10; }

  // La carte remplit l'écran sous sa position ; seul son contenu défile.
  _fit() {
    const top = this.getBoundingClientRect().top + window.scrollY;
    this.style.height = `${Math.max(320, window.innerHeight - top - 8)}px`;
  }

  async _ws(msg) {
    const res = await this._hass.callWS(msg);
    if (res && res.base_url) this._base = res.base_url;
    return res ? res.data : res;
  }

  async _loadList() {
    if (!this._hass) return;
    try {
      const res = await this._hass.callWS({ type: "todo/item/list", entity_id: this._config.entity });
      this._list = res.items || [];
    } catch (err) {
      this._list = [];
    }
    if (this._tab === "liste") this._render();
  }

  async _loadMenu() {
    try {
      this._menu = await this._ws({ type: "ravito/menu" });
      this._menuAt = Date.now();
      this._error = "";
    } catch (err) {
      this._error = err.message || "Ravito ne répond pas";
    }
    if (this._tab === "menu" || this._sheet) this._render();
  }

  async _loadRecipes(force = false) {
    if (!force && this._recipes && Date.now() - this._recipesAt < RECIPES_TTL) return;
    try {
      this._recipes = await this._ws({ type: "ravito/recipes" });
      this._recipesAt = Date.now();
    } catch (err) {
      this._error = err.message || "Ravito ne répond pas";
    }
    this._render();
  }

  async _act(fn) {
    if (this._busy) return;
    this._busy = true;
    this._render();
    try {
      await fn();
      this._error = "";
    } catch (err) {
      this._error = err.message || "Échec";
    }
    this._busy = false;
    await this._loadMenu();
    this._recipesAt = 0; // les jours au menu des recettes ont changé
    this._render();
  }

  _photo(path) {
    return path ? `${this._base}${path}` : "";
  }

  // --- Événements -----------------------------------------------------------

  _onInput(e) {
    if (e.target.dataset.input === "search") {
      this._search = e.target.value;
      this._renderBody(true);
    }
  }

  _onClick(e) {
    const el = e.target.closest("[data-a]");
    if (!el) return;
    const a = el.dataset.a;
    const id = el.dataset.id ? Number(el.dataset.id) : null;
    const day = el.dataset.day ?? null;

    if (a === "tab") {
      this._tab = el.dataset.tab;
      this._sheet = null;
      if (this._tab === "recettes") this._loadRecipes();
      if (this._tab === "menu") this._loadMenu();
      if (this._tab === "liste") this._loadList();
    } else if (a === "week") {
      this._week += Number(el.dataset.step);
    } else if (a === "close") {
      this._sheet = null;
      this._search = "";
    } else if (a === "add") {
      this._sheet = { kind: "add", day: day || null };
      this._search = "";
      this._loadRecipes();
    } else if (a === "move") {
      this._sheet = { kind: "move", entry: this._entry(id) };
    } else if (a === "remove") {
      if (this._confirm === id) {
        this._confirm = null;
        this._act(() => this._ws({ type: "ravito/menu/remove", entry_id: id }));
        return;
      }
      this._confirm = id;
      clearTimeout(this._confirmTimer);
      this._confirmTimer = setTimeout(() => { this._confirm = null; this._render(); }, 3000);
    } else if (a === "pick") {
      // Recette choisie pour un jour du menu
      const target = this._sheet.day || null;
      this._sheet = null;
      this._act(() => this._ws({ type: "ravito/menu/add", recipe_id: id, day: target }));
      return;
    } else if (a === "to-day") {
      const sheet = this._sheet;
      this._sheet = null;
      if (sheet.kind === "move") {
        const entry = sheet.entry;
        // Déplacer = ajouter au nouveau jour (mêmes portions), puis retirer l'ancien
        this._act(async () => {
          await this._ws({ type: "ravito/menu/add", recipe_id: entry.recipeId, day: day || null, servings: entry.servings });
          await this._ws({ type: "ravito/menu/remove", entry_id: entry.id });
        });
      } else if (sheet.kind === "plan") {
        this._act(() => this._ws({ type: "ravito/menu/add", recipe_id: sheet.recipe.id, day: day || null }));
      }
      return;
    } else if (a === "recipe") {
      this._openRecipe(id);
      return;
    } else if (a === "plan") {
      this._sheet = { kind: "plan", recipe: this._sheet.recipe };
    } else if (a === "tag") {
      const t = el.dataset.tag;
      if (this._tags.has(t)) this._tags.delete(t); else this._tags.add(t);
    } else if (a === "retry") {
      this._error = "";
      this._loadMenu();
      if (this._tab === "recettes") this._loadRecipes(true);
    }
    this._render();
  }

  async _openRecipe(id) {
    this._sheet = { kind: "recipe", recipe: null };
    this._render();
    try {
      const recipe = await this._ws({ type: "ravito/recipe", recipe_id: id });
      if (this._sheet && this._sheet.kind === "recipe") this._sheet = { kind: "recipe", recipe };
    } catch (err) {
      this._sheet = null;
      this._error = err.message || "Recette introuvable";
    }
    this._render();
  }

  _entry(id) {
    return ((this._menu && this._menu.entries) || []).find((e) => e.id === id);
  }

  // --- Rendu ----------------------------------------------------------------

  _render() {
    if (!this._config) return;
    const tab = (key, label, count) =>
      `<button class="tab ${this._tab === key ? "on" : ""}" data-a="tab" data-tab="${key}">${label}${count ? `<span class="count">${count}</span>` : ""}</button>`;
    const listCount = this._list ? this._list.length : 0;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <header>
          ${tab("liste", "🛒 Liste", listCount)}
          ${tab("menu", "📅 Menu")}
          ${tab("recettes", "📖 Recettes")}
          ${this._busy ? '<span class="busy">…</span>' : ""}
        </header>
        ${this._error ? `<div class="error">${esc(this._error)} <button data-a="retry">Réessayer</button></div>` : ""}
        <main></main>
        ${this._sheet ? `<div class="sheet"><div class="panel">${this._sheetHtml()}</div></div>` : ""}
      </ha-card>`;
    this._renderBody(false);
  }

  // Le corps seul est redessiné pendant la saisie, pour garder le clavier ouvert
  _renderBody(fromInput) {
    if (fromInput) {
      const target = this.shadowRoot.querySelector(this._sheet ? ".sheet .results" : "main .results");
      if (target) target.innerHTML = this._recipeRows(this._sheet ? "pick" : "recipe");
      return;
    }
    const main = this.shadowRoot.querySelector("main");
    if (!main) return;
    main.innerHTML = this._tab === "liste" ? this._listHtml() : this._tab === "menu" ? this._menuHtml() : this._recipesHtml();
  }

  _listHtml() {
    if (!this._list) return '<p class="empty">Chargement…</p>';
    if (!this._list.length) return '<p class="empty">La liste de courses est vide.</p>';
    const groups = new Map();
    for (const item of this._list) {
      const g = item.description || "Autres";
      if (!groups.has(g)) groups.set(g, []);
      groups.get(g).push(item);
    }
    return `<div class="cols">${[...groups].map(([g, items]) => `
      <section class="box">
        <h3>${esc(g)}</h3>
        ${items.map((i) => `<div class="line">${esc(i.summary)}</div>`).join("")}
      </section>`).join("")}</div>
      <p class="hint">La liste se modifie dans l'app Ravito.</p>`;
  }

  _menuHtml() {
    if (!this._menu) return '<p class="empty">Chargement…</p>';
    const start = addDays(monday(new Date()), this._week * 7);
    const today = iso(new Date());
    const end = addDays(start, 6);
    const byDay = new Map();
    const unplaced = [];
    for (const e of this._menu.entries || []) {
      if (!e.plannedFor) unplaced.push(e);
      else (byDay.get(e.plannedFor) || byDay.set(e.plannedFor, []).get(e.plannedFor)).push(e);
    }
    const days = [...Array(7)].map((_, i) => addDays(start, i));
    const range = `${start.getDate()} ${MOIS[start.getMonth()]} – ${end.getDate()} ${MOIS[end.getMonth()]}`;
    return `
      <div class="week">
        <button class="round" data-a="week" data-step="-1">‹</button>
        <strong>${this._week === 0 ? "Cette semaine" : range}</strong>
        <button class="round" data-a="week" data-step="1">›</button>
      </div>
      <div class="cols">
        ${days.map((d) => {
          const k = iso(d);
          return this._dayBox(dayLabel(d), k, byDay.get(k) || [], k === today, k < today);
        }).join("")}
        ${this._dayBox("À placer", "", unplaced, false, false)}
      </div>`;
  }

  _dayBox(label, key, entries, isToday, past) {
    return `
      <section class="box ${isToday ? "today" : ""} ${past ? "past" : ""}">
        <h3>${esc(label)}${isToday ? ' <span class="pill">Aujourd\'hui</span>' : ""}</h3>
        ${entries.map((e) => this._dish(e)).join("")}
        <div class="add" role="button" data-a="add" data-day="${key}">＋ Ajouter un plat</div>
      </section>`;
  }

  _dish(e) {
    const [icon, label] = STOCK[e.stock] || ["", ""];
    const detail = e.stock === "a_acheter" ? e.toBuy.join(", ") : e.stock === "manquera" ? e.beyond.join(", ") : "";
    return `
      <div class="dish">
        <div class="dish-main" role="button" data-a="recipe" data-id="${e.recipeId}">
          <span class="title">${esc(e.title)}</span>
          <span class="meta">${e.servings ? `${e.servings} pers. · ` : ""}<span title="${esc(label)}">${icon}</span> ${esc(detail || label)}</span>
        </div>
        <button class="icon" data-a="move" data-id="${e.id}" title="Déplacer">⇄</button>
        <button class="icon ${this._confirm === e.id ? "danger" : ""}" data-a="remove" data-id="${e.id}" title="Retirer">${this._confirm === e.id ? "Retirer ?" : "✕"}</button>
      </div>`;
  }

  _filtered() {
    const words = norm(this._search).split(/\s+/).filter(Boolean);
    return (this._recipes || []).filter((r) => {
      if (this._tags.size && ![...this._tags].every((t) => (r.tags || []).includes(t))) return false;
      const hay = norm(`${r.title} ${(r.tags || []).join(" ")}`);
      return words.every((w) => hay.includes(w));
    });
  }

  _recipesHtml() {
    if (!this._recipes) return '<p class="empty">Chargement…</p>';
    const tags = [...new Set(this._recipes.flatMap((r) => r.tags || []))].sort((a, b) => a.localeCompare(b, "fr"));
    return `
      <input class="search" data-input="search" type="search" placeholder="Chercher une recette…" value="${esc(this._search)}">
      <div class="tags">${tags.map((t) => `<button class="chip ${this._tags.has(t) ? "on" : ""}" data-a="tag" data-tag="${esc(t)}">${esc(t)}</button>`).join("")}</div>
      <div class="results grid">${this._recipeRows("recipe")}</div>`;
  }

  _recipeRows(action) {
    const list = this._filtered();
    if (!list.length) return '<p class="empty">Aucune recette.</p>';
    return list.map((r) => {
      const status = r.missing.length ? `Manque ${r.missing.length}` : "Faisable";
      return `
        <div class="recipe" role="button" data-a="${action}" data-id="${r.id}">
          ${r.photo ? `<img loading="lazy" src="${esc(this._photo(r.photo))}" alt="">` : '<div class="nophoto">🍽️</div>'}
          <span class="title">${esc(r.title)}</span>
          <span class="meta ${r.missing.length ? "" : "ok"}">${status}${r.menu && r.menu.length ? " · au menu" : ""}</span>
        </div>`;
    }).join("");
  }

  _sheetHtml() {
    const s = this._sheet;
    const close = '<button class="close" data-a="close">✕</button>';
    if (s.kind === "add") {
      const label = s.day ? dayLabel(parseIso(s.day)) : "À placer";
      if (!this._recipes) return `${close}<h2>Ajouter · ${esc(label)}</h2><p class="empty">Chargement…</p>`;
      return `${close}<h2>Ajouter · ${esc(label)}</h2>
        <input class="search" data-input="search" type="search" placeholder="Chercher une recette…" value="${esc(this._search)}">
        <div class="results grid">${this._recipeRows("pick")}</div>`;
    }
    if (s.kind === "move" || s.kind === "plan") {
      const title = s.kind === "move" ? `Déplacer « ${s.entry.title} »` : `Mettre « ${s.recipe.title} » au menu`;
      const start = new Date();
      const days = [...Array(14)].map((_, i) => addDays(start, i));
      return `${close}<h2>${esc(title)}</h2>
        <div class="days">
          ${days.map((d) => `<button class="chip big" data-a="to-day" data-day="${iso(d)}">${i18nDay(d)}</button>`).join("")}
          <button class="chip big" data-a="to-day" data-day="">À placer</button>
        </div>`;
    }
    if (s.kind === "recipe") {
      const r = s.recipe;
      if (!r) return `${close}<p class="empty">Chargement…</p>`;
      const times = [r.prepMinutes && `Préparation ${minutes(r.prepMinutes)}`, r.cookMinutes && `Cuisson ${minutes(r.cookMinutes)}`].filter(Boolean).join(" · ");
      const sections = new Map();
      for (const ing of r.ingredients || []) {
        const k = ing.section || "";
        if (!sections.has(k)) sections.set(k, []);
        sections.get(k).push(ing);
      }
      const dot = { ok: "ok", court: "short", manquant: "missing" };
      return `${close}
        <div class="recipe-head">
          ${r.photo ? `<img src="${esc(this._photo(r.photo))}" alt="">` : ""}
          <div>
            <h2>${esc(r.title)}</h2>
            <p class="meta">${[r.servings && `${r.servings} pers.`, times].filter(Boolean).join(" · ")}</p>
            <p class="meta">${(r.tags || []).map(esc).join(" · ")}</p>
            <button class="primary" data-a="plan">📅 Ajouter au menu</button>
          </div>
        </div>
        <div class="recipe-body">
          <div>
            <h3>Ingrédients</h3>
            ${[...sections].map(([sec, ings]) => `
              ${sec ? `<h4>${esc(sec)}</h4>` : ""}
              <ul class="ings">${ings.map((i) => `
                <li><span class="dot ${dot[i.status] || ""}"></span>
                  ${i.quantity != null ? `<b>${esc(i.quantity)}${i.unit ? ` ${esc(i.unit)}` : ""}</b> ` : ""}${esc(i.label)}${i.note ? ` <span class="meta">(${esc(i.note)})</span>` : ""}
                </li>`).join("")}</ul>`).join("")}
          </div>
          <div>
            <h3>Étapes</h3>
            <ol class="steps">${(r.steps || []).map((st) => `<li>${esc(st)}</li>`).join("")}</ol>
          </div>
        </div>`;
    }
    return close;
  }
}

function i18nDay(d) {
  const t = iso(new Date());
  const k = iso(d);
  if (k === t) return "Aujourd'hui";
  if (k === iso(addDays(new Date(), 1))) return "Demain";
  return `${dayLabel(d)} ${MOIS[d.getMonth()]}`;
}

const STYLE = `
  :host { display: block; }
  ha-card { height: 100%; display: flex; flex-direction: column; overflow: hidden; position: relative; }
  header { display: flex; gap: 8px; padding: 10px 12px; border-bottom: 1px solid var(--divider-color); align-items: center; }
  .tab { font: inherit; font-size: 18px; font-weight: 600; padding: 10px 18px; border-radius: 14px; border: 0; background: transparent; color: var(--secondary-text-color); }
  .tab.on { background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .count { margin-left: 8px; font-size: 14px; background: var(--error-color, #db4437); color: #fff; border-radius: 10px; padding: 1px 8px; }
  .busy { margin-left: auto; font-size: 22px; color: var(--secondary-text-color); }
  main { flex: 1; min-height: 0; overflow-y: auto; padding: 12px; touch-action: pan-y; }
  button, [role=button] { font: inherit; color: inherit; cursor: pointer; }
  .add { text-align: center; box-sizing: border-box; }
  .error { margin: 8px 12px 0; padding: 8px 12px; border-radius: 10px; background: rgba(219,68,55,.15); color: var(--error-color, #db4437); }
  .error button { margin-left: 8px; border: 0; border-radius: 8px; padding: 4px 10px; background: var(--error-color, #db4437); color: #fff; }
  .empty, .hint { color: var(--secondary-text-color); text-align: center; padding: 16px; margin: 0; }
  .cols { columns: 2; column-gap: 12px; }
  .box { break-inside: avoid; margin: 0 0 12px; padding: 10px 12px; border-radius: 14px; background: var(--secondary-background-color, rgba(127,127,127,.08)); }
  .box h3 { margin: 2px 0 8px; font-size: 15px; text-transform: uppercase; letter-spacing: .04em; color: var(--secondary-text-color); }
  .box.today { outline: 2px solid var(--primary-color); }
  .box.past { opacity: .6; }
  .pill { text-transform: none; letter-spacing: 0; font-size: 12px; background: var(--primary-color); color: var(--text-primary-color, #fff); border-radius: 8px; padding: 1px 8px; margin-left: 4px; }
  .line { font-size: 19px; padding: 8px 2px; border-top: 1px solid var(--divider-color); }
  .line:first-of-type { border-top: 0; }
  .week { display: flex; align-items: center; justify-content: center; gap: 16px; margin-bottom: 12px; font-size: 18px; }
  .round { width: 44px; height: 44px; border-radius: 22px; border: 0; background: var(--secondary-background-color, rgba(127,127,127,.15)); font-size: 22px; }
  .dish { display: flex; align-items: center; gap: 6px; padding: 6px 0; border-top: 1px solid var(--divider-color); }
  .dish:first-of-type { border-top: 0; }
  .dish-main { flex: 1; min-width: 0; text-align: left; background: none; border: 0; padding: 4px 0; display: flex; flex-direction: column; }
  .title { font-size: 18px; font-weight: 500; }
  .meta { font-size: 14px; color: var(--secondary-text-color); }
  .meta.ok { color: var(--success-color, #43a047); }
  .icon { min-width: 44px; height: 44px; border-radius: 12px; border: 0; background: rgba(127,127,127,.15); font-size: 18px; padding: 0 10px; }
  .icon.danger { background: var(--error-color, #db4437); color: #fff; font-size: 15px; }
  .add { width: 100%; margin-top: 6px; padding: 10px; border-radius: 12px; border: 1px dashed var(--divider-color); background: none; color: var(--primary-color); font-size: 16px; }
  .search { width: 100%; box-sizing: border-box; font: inherit; font-size: 18px; padding: 10px 14px; border-radius: 12px; border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color); margin-bottom: 10px; }
  .tags, .days { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
  .chip { border: 1px solid var(--divider-color); background: none; border-radius: 16px; padding: 6px 14px; font-size: 15px; }
  .chip.on { background: var(--primary-color); border-color: var(--primary-color); color: var(--text-primary-color, #fff); }
  .chip.big { font-size: 18px; padding: 12px 18px; border-radius: 14px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; }
  .recipe { display: flex; flex-direction: column; text-align: left; border: 0; padding: 0 0 8px; border-radius: 14px; overflow: hidden; background: var(--secondary-background-color, rgba(127,127,127,.08)); }
  .recipe img, .nophoto { width: 100%; height: 110px; object-fit: cover; display: block; background: rgba(127,127,127,.15); }
  .nophoto { display: flex; align-items: center; justify-content: center; font-size: 36px; }
  .recipe .title, .recipe .meta { padding: 0 10px; }
  .recipe .title { margin-top: 6px; font-size: 16px; line-height: 1.25; }
  .sheet { position: absolute; inset: 0; background: rgba(0,0,0,.5); display: flex; }
  .panel { position: relative; flex: 1; margin: 12px; padding: 16px; border-radius: 18px; background: var(--card-background-color); overflow-y: auto; touch-action: pan-y; }
  .panel h2 { margin: 0 56px 12px 0; font-size: 22px; }
  .close { position: absolute; top: 10px; right: 10px; width: 44px; height: 44px; border-radius: 22px; border: 0; background: rgba(127,127,127,.2); font-size: 18px; }
  .recipe-head { display: flex; gap: 16px; margin-bottom: 12px; }
  .recipe-head img { width: 220px; height: 150px; object-fit: cover; border-radius: 14px; flex: none; }
  .recipe-head p { margin: 4px 0; }
  .primary { margin-top: 8px; border: 0; border-radius: 12px; padding: 10px 16px; font-size: 16px; background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .recipe-body { display: grid; grid-template-columns: 2fr 3fr; gap: 20px; }
  .recipe-body h3 { margin: 4px 0 8px; }
  .recipe-body h4 { margin: 10px 0 4px; color: var(--secondary-text-color); }
  .ings { list-style: none; padding: 0; margin: 0; font-size: 17px; }
  .ings li { padding: 4px 0; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 5px; margin-right: 6px; background: var(--disabled-text-color, #888); }
  .dot.ok { background: var(--success-color, #43a047); }
  .dot.short { background: var(--warning-color, #ffa600); }
  .dot.missing { background: var(--error-color, #db4437); }
  .steps { margin: 0; padding-left: 22px; font-size: 17px; line-height: 1.45; }
  .steps li { margin-bottom: 8px; }
`;

// Home Assistant remplace customElements en démarrant. Une carte enregistrée avant ce
// remplacement reste invisible ("Erreur de configuration") : fréquent sur un appareil lent.
function registerCard() {
  if (!customElements.get("home-assistant")) {
    setTimeout(registerCard, 50);
    return;
  }
  if (!customElements.get("ravito-card")) customElements.define("ravito-card", RavitoCard);
}
registerCard();
window.customCards = window.customCards || [];
window.customCards.push({
  type: "ravito-card",
  name: "Ravito",
  description: "Liste de courses, menu de la semaine et recettes de Ravito.",
});

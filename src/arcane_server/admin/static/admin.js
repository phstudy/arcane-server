// Arcane admin UI: vanilla JS over /admin/api. DOM is built with h() (textContent only, no innerHTML).
"use strict";

let CSRF = null;

// ---------- helpers ----------
function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (k === "class") el.className = v;
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return el;
}
const $ = (sel) => document.querySelector(sel);
const num = (n) => (n === null || n === undefined ? "" : Number(n).toLocaleString("zh-TW"));

function fmtTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  const p = (x) => String(x).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function ago(ts) {
  if (!ts) return "—";
  const s = Math.round(Date.now() / 1000 - ts);
  const f = (v, u) => `${v} ${u}${s < 0 ? "後" : "前"}`;
  const a = Math.abs(s);
  if (a < 60) return f(a, "秒");
  if (a < 3600) return f(Math.round(a / 60), "分鐘");
  if (a < 86400) return f(Math.round(a / 3600), "小時");
  return f(Math.round(a / 86400), "天");
}
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.remove("show"), 3500);
}

async function api(method, path, body) {
  const opt = { method, headers: {}, credentials: "same-origin" };
  if (method !== "GET") opt.headers["X-CSRF-Token"] = CSRF || "";
  if (body instanceof FormData) opt.body = body;
  else if (body !== undefined) {
    opt.headers["Content-Type"] = "application/json";
    opt.body = JSON.stringify(body);
  }
  const r = await fetch("/admin/api/" + path, opt);
  let data = null;
  try { data = await r.json(); } catch { data = { error: await r.text().catch(() => r.statusText) }; }
  if (r.status === 401 && path !== "login") { showLogin(); throw new Error("請重新登入"); }
  if (!r.ok) throw new Error((data && data.error) || `${r.status} ${r.statusText}`);
  return data;
}

function table(cols, rows, onClick) {
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, cols.map((c) => h("th", { class: c.num ? "num" : null }, c.label)))),
    h("tbody", {}, rows.map((r) => h("tr", { class: onClick ? "clickable" : null, onclick: onClick ? () => onClick(r) : null },
      cols.map((c) => h("td", { class: c.num ? "num" : null }, c.render ? c.render(r) : (c.num ? num(r[c.key]) : r[c.key]))))))));
}
function kv(pairs) {
  return h("dl", { class: "kv" }, pairs.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, v)]));
}
const onlineChip = (on) => (on ? h("span", { class: "chip ok" }, "在線") : null);
const claimedChip = (c) => (c ? h("span", { class: "chip" }, "已綁定裝置") : h("span", { class: "chip warn" }, "未認領"));

// Searchable item picker: calls onPick({id,name,...}).
function itemPicker(onPick, placeholder = "搜尋道具（名稱 / 英文 / ID）") {
  const input = h("input", { type: "search", placeholder, autocomplete: "off" });
  const list = h("ul", { hidden: true });
  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      const q = input.value.trim();
      list.replaceChildren();
      if (!q) { list.hidden = true; return; }
      const { items } = await api("GET", "items?q=" + encodeURIComponent(q));
      list.replaceChildren(...items.map((it) => h("li", { onclick: () => { onPick(it); input.value = `${it.name}`; list.hidden = true; } },
        `${it.name} `, h("span", { class: "muted" }, `${it.en} · ${it.type} · ${it.id}`))));
      list.hidden = items.length === 0;
    }, 200);
  });
  input.addEventListener("blur", () => setTimeout(() => (list.hidden = true), 200));
  return h("div", { class: "picker" }, input, list);
}

async function guarded(btn, fn) {
  btn.disabled = true;
  try { await fn(); } catch (e) { toast("失敗：" + e.message); } finally { btn.disabled = false; }
}

// ---------- views ----------
const VIEWS = {};

VIEWS.players = async (view) => {
  const q = h("input", { type: "search", placeholder: "搜尋 ID / 名稱 / 公會 / anon_id" });
  const onlyClaimed = h("input", { type: "checkbox" });
  const out = h("div", {});
  const load = async () => {
    const data = await api("GET", `players?q=${encodeURIComponent(q.value)}${onlyClaimed.checked ? "&claimed=1" : ""}`);
    out.replaceChildren(h("p", { class: "muted" }, `${data.players.length} 個帳號，在線 ${data.online}`),
      table([
        { label: "ID", render: (r) => h("span", { class: "mono" }, r.id) },
        { label: "名稱", render: (r) => [r.username, " ", onlineChip(r.online)] },
        { label: "等級", key: "level", num: true },
        { label: "公會", key: "club" },
        { label: "戰力", key: "power", num: true },
        { label: "最後存檔", render: (r) => h("span", { title: fmtTime(r.last_save) }, ago(r.last_save)) },
        { label: "裝置", render: (r) => [claimedChip(r.claimed), " ", h("span", { class: "mono muted" }, r.claimed ? r.anon_id : "")] },
      ], data.players, (r) => (location.hash = "#player/" + r.id)));
  };
  let t = null;
  q.addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
  onlyClaimed.addEventListener("change", load);
  view.append(h("div", { class: "card" }, h("h2", {}, "玩家"),
    h("div", { class: "row" }, h("label", {}, "搜尋", q), h("label", { class: "inline" }, h("span", {}, "只顯示已綁定裝置"), onlyClaimed)), out));
  await load();
};

VIEWS.player = async (view, pid) => {
  const p = await api("GET", "players/" + encodeURIComponent(pid));
  const reload = () => route();
  const currencies = p.items.filter((i) => i.currency);
  const others = p.items.filter((i) => !i.currency);

  // grant/remove
  let picked = null;
  const pickedLabel = h("span", { class: "muted" }, "（未選擇）");
  const amount = h("input", { type: "number", value: "100", step: "1" });
  const grantBtn = h("button", { class: "primary" }, "發放");
  const removeBtn = h("button", { class: "secondary" }, "扣除");
  const doItem = (sign, btn) => guarded(btn, async () => {
    if (!picked) throw new Error("請先選道具");
    const n = parseInt(amount.value, 10);
    if (!(n > 0)) throw new Error("數量要大於 0");
    if (!confirm(`${sign > 0 ? "發放" : "扣除"} ${picked.name} × ${num(n)} 給 ${p.username}？`)) return;
    const r = await api("POST", `players/${pid}/items`, { item_id: picked.id, delta: sign * n });
    toast(`${picked.name}：${num(r.before)} → ${num(r.after)}${r.online ? "（玩家在線，重開遊戲後才會看到）" : ""}`);
    reload();
  });
  grantBtn.onclick = () => doItem(1, grantBtn);
  removeBtn.onclick = () => doItem(-1, removeBtn);

  const level = h("input", { type: "number", min: "1", max: String(p.max_level), value: String(p.level) });
  const levelBtn = h("button", { class: "secondary" }, "設定等級");
  levelBtn.onclick = () => guarded(levelBtn, async () => {
    const r = await api("POST", `players/${pid}/level`, { level: parseInt(level.value, 10) });
    toast(`等級 ${r.before} → ${r.after}`); reload();
  });
  const vipDays = h("input", { type: "number", min: "0", max: "3650", value: "30" });
  const vipBtn = h("button", { class: "secondary" }, "設定 VIP 天數");
  vipBtn.onclick = () => guarded(vipBtn, async () => {
    const r = await api("POST", `players/${pid}/vip`, { days: parseInt(vipDays.value, 10) });
    toast(`VIP 到期：${fmtTime(r.vip_expire)}`); reload();
  });

  const anon = h("input", { type: "text", placeholder: "裝置 anon_id", class: "mono" });
  const bindBtn = h("button", { class: "secondary" }, "綁定裝置");
  bindBtn.onclick = () => guarded(bindBtn, async () => {
    if (!anon.value.trim()) throw new Error("請輸入 anon_id");
    if (!confirm(`讓裝置 ${anon.value.trim()} 下次登入時進入 ${p.username}（${pid}）？\n該裝置目前的帳號會被解除綁定。`)) return;
    const r = await api("POST", `players/${pid}/bind`, { anon_id: anon.value.trim() });
    toast(`已綁定${r.previous_account ? `（原帳號 ${r.previous_account} 解除）` : ""}，請該裝置重開遊戲`); reload();
  });
  const codeOut = h("div", {});
  const codeBtn = h("button", { class: "primary" }, "產生認領碼");
  codeBtn.onclick = () => guarded(codeBtn, async () => {
    const c = await api("POST", `players/${pid}/claim-code`);
    codeOut.replaceChildren(h("div", { class: "code" }, c.code),
      h("p", {}, `把遊戲內的玩家名稱改成這個認領碼，然後完全關閉並重開遊戲，就會進入 ${p.username}。`),
      h("p", { class: "muted" }, `單次使用，${fmtTime(c.expires_at)} 前有效。`));
  });

  view.append(
    h("p", {}, h("button", { class: "link", onclick: () => (location.hash = "#players") }, "← 玩家列表")),
    h("div", { class: "grid2" },
      h("div", { class: "card" }, h("h2", {}, p.username || "(無名稱)", " ", onlineChip(p.online)),
        kv([["ID", h("span", { class: "mono" }, p.id)], ["等級", p.level], ["收藏戰力", num(p.power)],
          ["公會", p.club ? h("button", { class: "link", onclick: () => (location.hash = "#club/" + p.club.id) }, `${p.club.name}（${p.club.role}）`) : "—"],
          ["VIP 到期", [fmtTime(p.vip_expire), p.vip_forced ? h("span", { class: "muted" }, "（伺服器設定：全員 VIP）") : ""]],
          ["建立", fmtTime(p.created)], ["最後存檔", `${fmtTime(p.last_save)}（${ago(p.last_save)}）`],
          ["時區 / 語言", `${p.timezone} / ${p.language}`],
          ["裝置", [claimedChip(p.claimed), " ", h("span", { class: "mono" }, p.anon_id)]]]),
        p.online ? h("p", { class: "note" }, "玩家在線：直接修改道具會立即生效，但客戶端要重開遊戲才會顯示。要讓玩家馬上看到，請改用信箱發送。") : null),
      h("div", { class: "card" }, h("h2", {}, "操作"),
        h("h3", {}, "發放 / 扣除道具或貨幣"),
        h("div", { class: "row" }, h("label", {}, "道具", itemPicker((it) => { picked = it; pickedLabel.textContent = `${it.name}（${it.id}）`; })),
          h("label", {}, "數量", amount)),
        h("p", {}, "已選：", pickedLabel), h("div", { class: "row" }, grantBtn, removeBtn),
        h("h3", {}, "等級 / VIP"),
        h("div", { class: "row" }, h("label", {}, `等級（1–${p.max_level}）`, level), levelBtn),
        h("div", { class: "row" }, h("label", {}, "VIP 天數（0 = 取消）", vipDays), vipBtn),
        p.vip_forced ? h("p", { class: "muted" }, "目前伺服器讓所有人都是 VIP，VIP 設定會在下次載入時被覆蓋。") : null,
        h("h3", {}, "裝置認領"),
        h("div", { class: "row" }, codeBtn), codeOut,
        h("div", { class: "row" }, h("label", {}, "或直接綁定 anon_id（見玩家列表的裝置欄）", anon), bindBtn))),
    h("div", { class: "grid2" },
      h("div", { class: "card" }, h("h2", {}, "貨幣"), table([
        { label: "名稱", render: (r) => [r.name, " ", h("span", { class: "muted" }, r.en)] },
        { label: "數量", key: "count", num: true }], currencies)),
      h("div", { class: "card" }, h("h2", {}, `道具（${others.length}）`), h("div", { class: "scroll" }, table([
        { label: "名稱", render: (r) => [r.name, " ", h("span", { class: "muted" }, r.en)] },
        { label: "類型", key: "type" }, { label: "ID", render: (r) => h("span", { class: "mono muted" }, r.id) },
        { label: "數量", key: "count", num: true }], others)))),
    h("div", { class: "card" }, h("h2", {}, "戰役進度"), table([
      { label: "戰役", key: "name" }, { label: "類型", key: "type" },
      { label: "已開放", key: "open", num: true }, { label: "已勝利", key: "won", num: true },
      { label: "三星", key: "three_star", num: true }, { label: "總關卡", key: "battles", num: true }],
      p.campaigns.filter((c) => c.open > 0))),
    h("div", { class: "grid2" },
      h("div", { class: "card" }, h("h2", {}, `角色（${p.units.length}）`), h("div", { class: "scroll" }, table([
        { label: "角色", key: "name" }, { label: "等級", key: "level", num: true }, { label: "星", key: "stars", num: true },
        { label: "裝備階", key: "gear_tier", num: true }, { label: "戰力", key: "power", num: true }], p.units))),
      h("div", { class: "card" }, h("h2", {}, `法術（${p.spells.length}）`), h("div", { class: "scroll" }, table([
        { label: "法術", key: "name" }, { label: "等級", key: "level", num: true }], p.spells)))),
    h("div", { class: "card" }, h("h2", {}, "此玩家的管理操作紀錄"), auditTable(p.audit)));
};

function auditTable(rows) {
  if (!rows.length) return h("p", { class: "muted" }, "（無）");
  return table([
    { label: "時間", render: (r) => fmtTime(r.ts) }, { label: "操作者", key: "actor" },
    { label: "動作", key: "action" }, { label: "對象", render: (r) => h("span", { class: "mono" }, r.target) },
    { label: "內容", render: (r) => h("span", { class: "mono" }, JSON.stringify(r.detail)) }], rows);
}

VIEWS.clubs = async (view) => {
  const { clubs } = await api("GET", "clubs");
  view.append(h("div", { class: "card" }, h("h2", {}, "公會"), table([
    { label: "名稱", key: "name" }, { label: "ID", render: (r) => h("span", { class: "mono" }, r.id) },
    { label: "成員", key: "members", num: true }, { label: "已綁定裝置", key: "claimed_members", num: true },
    { label: "在線", key: "online", num: true }], clubs, (r) => (location.hash = "#club/" + r.id))));
};

VIEWS.club = async (view, cid) => {
  const c = await api("GET", "clubs/" + encodeURIComponent(cid));
  const war = c.war;
  view.append(
    h("p", {}, h("button", { class: "link", onclick: () => (location.hash = "#clubs") }, "← 公會列表")),
    h("div", { class: "card" }, h("h2", {}, c.name), h("p", { class: "muted" }, c.description || "")),
    h("div", { class: "grid2" },
      h("div", { class: "card" }, h("h2", {}, "突襲"), table([
        { label: "突襲", key: "raid" }, { label: "階層", render: (r) => (r.tier > 0 ? r.tier : "—") },
        { label: "狀態", render: (r) => [r.state, " ", r.active ? h("span", { class: "chip ok" }, "進行中") : null] },
        { label: "剩餘血量 %", render: (r) => (r.health === null ? "—" : r.health) },
        { label: "結束", render: (r) => (r.end ? `${fmtTime(r.end)}（${ago(r.end)}）` : "—") }], c.raids)),
      h("div", { class: "card" }, h("h2", {}, "公會戰"), war ? kv([
        ["場次", war.serial], ["階段", war.phase], ["階段結束", `${fmtTime(war.phase_end)}（${ago(war.phase_end)}）`],
        ["開始", fmtTime(war.start)], ["分數", h("span", { class: "mono" }, JSON.stringify(war.scores || {}))]])
        : h("p", { class: "muted" }, "尚未開始過公會戰"))),
    h("div", { class: "card" }, h("h2", {}, `成員（${c.members.length}）`), table([
      { label: "名稱", render: (r) => [r.username, " ", onlineChip(r.online)] },
      { label: "ID", render: (r) => h("span", { class: "mono" }, r.id) }, { label: "等級", key: "level", num: true },
      { label: "職位", key: "role" }, { label: "裝置", render: (r) => (r.account ? claimedChip(r.claimed) : h("span", { class: "muted" }, "無帳號")) },
      { label: "加入", render: (r) => fmtTime(r.joined_at) }], c.members, (r) => r.account && (location.hash = "#player/" + r.id))));
};

VIEWS.inbox = async (view) => {
  const { presets } = await api("GET", "inbox/presets");
  const target = h("input", { type: "text", placeholder: "玩家 ID，或 all = 所有已綁定裝置的帳號", class: "mono" });
  const preset = h("select", {}, h("option", { value: "" }, "— 自訂文字 —"),
    presets.map((p, i) => h("option", { value: String(i) }, `${p.subject}（${p.subject_key}）`)));
  const subject = h("input", { type: "text", value: "CSR_GIFT_SUBJECT" });
  const body = h("textarea", { rows: "3" }, "CSR_GIFT_BODY");
  const previewBox = h("p", { class: "muted" });
  const showPreview = () => {
    const p = presets.find((x) => x.subject_key === subject.value.trim() && x.body_key === body.value.trim());
    previewBox.textContent = p ? `預覽：${p.subject} — ${p.body}` : "自訂文字：客戶端找不到翻譯鍵時會原樣顯示（實驗性，若顯示異常請改用預設訊息）。";
  };
  preset.addEventListener("change", () => {
    const p = presets[parseInt(preset.value, 10)];
    if (p) { subject.value = p.subject_key; body.value = p.body_key; }
    showPreview();
  });
  subject.addEventListener("input", showPreview);
  body.addEventListener("input", showPreview);
  const ttl = h("input", { type: "number", min: "1", max: "365", value: "7" });
  const atts = [];
  const attList = h("ul", { class: "att-list" });
  let picked = null;
  const count = h("input", { type: "number", min: "1", value: "100" });
  const addBtn = h("button", { class: "secondary", type: "button" }, "加入附件");
  const renderAtts = () => attList.replaceChildren(...atts.map((a, i) => h("li", {}, `${a.name} × ${num(a.count)} `,
    h("button", { class: "link", type: "button", onclick: () => { atts.splice(i, 1); renderAtts(); } }, "移除"))));
  addBtn.onclick = () => {
    const n = parseInt(count.value, 10);
    if (!picked || !(n > 0)) return toast("請選道具並輸入數量");
    atts.push({ item_id: picked.id, name: picked.name, count: n });
    renderAtts();
  };
  const send = h("button", { class: "primary" }, "寄出");
  send.onclick = () => guarded(send, async () => {
    const t = target.value.trim();
    if (!t) throw new Error("請輸入收件人");
    if (!confirm(`寄給 ${t === "all" ? "所有已綁定裝置的帳號" : t}，附件 ${atts.length} 項？`)) return;
    const r = await api("POST", "inbox", { target: t, subject_key: subject.value.trim(), body_key: body.value.trim(),
      ttl_days: parseInt(ttl.value, 10), attachments: atts.map((a) => ({ item_id: a.item_id, count: a.count })) });
    toast(`已寄出給 ${r.recipients} 位玩家`);
  });
  showPreview();
  view.append(h("div", { class: "card" }, h("h2", {}, "寄送信件"),
    h("div", { class: "row" }, h("label", {}, "收件人", target), h("label", {}, "有效天數", ttl)),
    h("label", {}, "預設訊息", preset),
    h("div", { class: "row" }, h("label", {}, "標題（翻譯鍵或文字）", subject)),
    h("label", {}, "內文（翻譯鍵或文字）", body), previewBox,
    h("h3", {}, "附件"),
    h("div", { class: "row" }, h("label", {}, "道具", itemPicker((it) => (picked = it))), h("label", {}, "數量", count), addBtn),
    attList, h("div", { class: "row" }, send)));
};

VIEWS.codes = async (view) => {
  const { codes } = await api("GET", "redemption-codes");
  const code = h("input", { type: "text", class: "mono", maxlength: "64", placeholder: "例如 SPRING2024（不分大小寫、空白）" });
  const maxClaims = h("input", { type: "number", min: "0", value: "0" });
  const expires = h("input", { type: "datetime-local" });
  const items = [];
  const itemList = h("ul", { class: "att-list" });
  let picked = null;
  const count = h("input", { type: "number", min: "1", value: "100" });
  const renderItems = () => itemList.replaceChildren(...items.map((a, i) => h("li", {}, `${a.name} × ${num(a.count)} `,
    h("button", { class: "link", type: "button", onclick: () => { items.splice(i, 1); renderItems(); } }, "移除"))));
  const addBtn = h("button", { class: "secondary", type: "button" }, "加入道具");
  addBtn.onclick = () => {
    const n = parseInt(count.value, 10);
    if (!picked || !(n > 0)) return toast("請選道具並輸入數量");
    items.push({ item_id: picked.id, name: picked.name, count: n });
    renderItems();
  };
  const create = h("button", { class: "primary" }, "建立兌換碼");
  create.onclick = () => guarded(create, async () => {
    if (!items.length) throw new Error("請至少加入一項道具");
    const r = await api("POST", "redemption-codes", { code: code.value, max_claims: parseInt(maxClaims.value, 10) || 0,
      expires_at: expires.value ? Math.floor(new Date(expires.value).getTime() / 1000) : 0,
      items: items.map((a) => ({ item_id: a.item_id, count: a.count })) });
    toast(`已建立 ${r.code}`);
    route();
  });
  const del = (c, btn) => guarded(btn, async () => {
    if (!confirm(`刪除兌換碼 ${c.code}？`)) return;
    await api("DELETE", "redemption-codes/" + encodeURIComponent(c.code));
    route();
  });
  view.append(h("div", { class: "card" }, h("h2", {}, "建立兌換碼"),
    h("p", { class: "muted" }, "玩家在遊戲的設定 → REDEEM CODE 輸入；每位玩家每個碼只能兌換一次。"),
    h("div", { class: "row" }, h("label", {}, "兌換碼", code), h("label", {}, "總次數上限（0 = 不限）", maxClaims),
      h("label", {}, "到期（空白 = 不到期）", expires)),
    h("div", { class: "row" }, h("label", {}, "道具", itemPicker((it) => (picked = it))), h("label", {}, "數量", count), addBtn),
    itemList, h("div", { class: "row" }, create)),
    h("div", { class: "card" }, h("h2", {}, `兌換碼（${codes.length}）`), codes.length ? table([
      { label: "碼", render: (c) => h("span", { class: "mono" }, c.code) },
      { label: "道具", render: (c) => c.items.map(([id, n]) => `${id} × ${num(n)}`).join("、") },
      { label: "已兌換", render: (c) => (c.max_claims ? `${c.claims} / ${c.max_claims}` : String(c.claims)) },
      { label: "到期", render: (c) => (c.expires_at ? fmtTime(c.expires_at) : "—") },
      { label: "", render: (c) => h("button", { class: "link", type: "button", onclick: (e) => del(c, e.currentTarget) }, "刪除") }], codes)
      : h("p", { class: "muted" }, "（無）")));
};

VIEWS.import = async (view) => {
  const file = h("input", { type: "file", accept: ".json,.bin" });
  const previewBtn = h("button", { class: "secondary" }, "讀取檔案");
  const out = h("div", {});
  previewBtn.onclick = () => guarded(previewBtn, async () => {
    if (!file.files[0]) throw new Error("請選擇檔案");
    const fd = new FormData();
    fd.append("file", file.files[0]);
    const r = await api("POST", "import/preview", fd);
    const sel = new Set();
    const replace = h("input", { type: "checkbox" });
    const go = h("button", { class: "primary" }, "匯入所選");
    go.onclick = () => guarded(go, async () => {
      if (!sel.size) throw new Error("請勾選要匯入的玩家");
      const results = [];
      for (const id of sel) {
        const fd2 = new FormData();
        fd2.append("file", file.files[0]);
        fd2.append("player_id", id);
        if (replace.checked) fd2.append("replace", "1");
        const res = await api("POST", "import", fd2);
        results.push(...res.messages);
      }
      out.append(h("pre", { class: "log mono" }, results.join("\n")));
      toast("匯入完成");
    });
    out.replaceChildren(h("p", { class: "muted" }, `${r.source}：${r.players.length} 位玩家`), table([
      { label: "", render: (p) => h("input", { type: "checkbox", onchange: (e) => (e.target.checked ? sel.add(p.id) : sel.delete(p.id)) }) },
      { label: "ID", render: (p) => h("span", { class: "mono" }, p.id) }, { label: "名稱", key: "username" },
      { label: "等級", key: "level", num: true }, { label: "角色數", key: "units", num: true },
      { label: "狀態", render: (p) => [p.exists ? h("span", { class: "chip warn" }, "已存在") : h("span", { class: "chip ok" }, "新帳號"), " ", onlineChip(p.online)] }],
      r.players),
      h("div", { class: "row" }, h("label", {}, h("span", {}, "更新已存在的帳號：一律合併，較新的資料優先、清單取聯集（在線玩家會被拒絕）"), replace), go));
  });
  view.append(h("div", { class: "card" }, h("h2", {}, "匯入封存帳號"),
    h("p", { class: "muted" }, "支援：公會匯出 JSON、單一玩家 JSON、PlayerResponse .bin。匯入的帳號沒有綁定裝置，請到玩家頁面產生認領碼。"),
    h("div", { class: "row" }, h("label", {}, "檔案", file), previewBtn), out));
};

VIEWS.server = async (view) => {
  const s = await api("GET", "server");
  const rot = s.rotation || {};
  const schedRows = (c) => [...c.now.map((r) => ({ when: "進行中", ...r })), ...c.next.map((r) => ({ when: "即將開始", ...r }))];
  const schedCols = [{ label: "種類", key: "kind_label" }, { label: "", key: "when" },
    { label: "名稱", render: (r) => (r.badge ? r.badge + " " : "") + r.name },
    { label: "開始", render: (r) => (r.permanent ? "常駐" : fmtTime(r.begin)) },
    { label: "結束", render: (r) => (r.permanent ? "—" : `${fmtTime(r.end)}（${ago(r.end)}）`) }];
  if (s.join) view.append(h("div", { class: "card join" }, h("h2", {}, "邀請玩家（多人版 App）"),
    h("div", { class: "row" }, h("img", { src: s.join.qr, alt: "加入伺服器的 QR code", width: "160", height: "160" }),
      h("div", {}, h("p", {}, "玩家在多人版 App 點「Scan QR code」掃這個碼，或用手機相機掃描，就會連到這台伺服器。"),
        h("p", {}, h("a", { href: s.join.page, target: "_blank", rel: "noopener" }, "開啟加入頁面（可分享、可投影）")),
        h("p", { class: "muted" }, "位址取自 ARCANE_PUBLIC_BASE_URL，未設定時取自你開啟管理介面的位址（用 127.0.0.1 開時 QR code 無法給別人用）。")))));
  view.append(
    h("div", { class: "grid2" },
      h("div", { class: "card" }, h("h2", {}, "設定（目前生效）"), kv(s.settings.map((x) => [x.name,
        typeof x.value === "boolean" ? h("span", { class: "chip " + (x.value ? "ok" : "") }, x.value ? "開" : "關") : h("span", { class: "mono" }, x.value === null ? "—" : String(x.value))])),
        h("h3", {}, "內容"), kv([["bundle", s.content.bundle_version], ["localization", s.content.loc_version], ["bundles", num(s.content.bundles)]])),
      h("div", { class: "card" }, h("h2", {}, "連線"), kv([["在線玩家", s.online.length ? s.online.join(", ") : "—"], ["快取中的玩家", s.cached_players]]),
        h("h3", {}, "未實作的 RPC（自啟動以來）"),
        Object.keys(s.unimplemented).length ? table([{ label: "RPC", key: "k" }, { label: "次數", key: "v", num: true }],
          Object.entries(s.unimplemented).map(([k, v]) => ({ k, v }))) : h("p", { class: "muted" }, "（無）"),
        h("h3", {}, "認領碼"),
        s.claim_codes.length ? table([{ label: "碼", render: (r) => h("span", { class: "mono" }, r.code) },
          { label: "帳號", key: "public_id" }, { label: "到期", render: (r) => fmtTime(r.expires_at) },
          { label: "狀態", render: (r) => (r.used_at ? `已使用 ${fmtTime(r.used_at)}` : r.expires_at * 1000 < Date.now() ? "已過期" : "有效") }],
          s.claim_codes) : h("p", { class: "muted" }, "（無）"))),
    h("div", { class: "card" }, h("h2", {}, "排程（和遊戲內 News 頁同一份）"),
      rot.error ? h("p", { class: "error" }, rot.error) : [
        ...(rot.categories || []).flatMap((c) => [h("h3", {}, `${c.label}（進行中 ${c.now.length}、即將開始 ${c.next.length}）`),
          c.now.length || c.next.length ? table(schedCols, schedRows(c)) : h("p", { class: "muted" }, "（無）")]),
        h("h3", {}, "排程說明"), h("ul", {}, ...(rot.rules || []).map((x) => h("li", {}, x)))]),
    h("div", { class: "card" }, h("h2", {}, `進行中的戰鬥（${s.pending_battles.length}）`),
      s.pending_battles.length ? table([{ label: "種類", key: "kind" }, { label: "玩家", key: "owner" },
        { label: "key", render: (r) => h("span", { class: "mono" }, r.key) }, { label: "到期", render: (r) => fmtTime(r.expires) },
        { label: "內容", render: (r) => h("span", { class: "mono" }, JSON.stringify(r.value)) }], s.pending_battles)
        : h("p", { class: "muted" }, "（無）")));
};

VIEWS.logs = async (view) => {
  const which = h("select", {}, h("option", { value: "problems" }, "警告與錯誤"), h("option", { value: "all" }, "全部（最後 500 筆）"));
  const out = h("div", {});
  const audit = h("div", {});
  const load = async () => {
    const { logs } = await api("GET", "logs?which=" + which.value);
    out.replaceChildren(logs.length ? h("div", { class: "scroll" }, table([
      { label: "時間", render: (r) => fmtTime(r.ts) },
      { label: "等級", render: (r) => h("span", { class: "chip " + (r.level === "ERROR" || r.level === "CRITICAL" ? "bad" : r.level === "WARNING" ? "warn" : "") }, r.level) },
      { label: "來源", key: "logger" }, { label: "訊息", render: (r) => h("pre", { class: "log mono" }, r.msg) }], logs))
      : h("p", { class: "muted" }, "（無）"));
    audit.replaceChildren(auditTable((await api("GET", "audit")).audit));
  };
  which.addEventListener("change", load);
  view.append(h("div", { class: "card" }, h("h2", {}, "伺服器紀錄"), h("div", { class: "row" }, h("label", {}, "顯示", which),
    h("button", { class: "secondary", onclick: load }, "重新整理")), out),
    h("div", { class: "card" }, h("h2", {}, "管理操作紀錄"), audit));
  await load();
};

// ---------- shell ----------
async function route() {
  const [name, arg] = (location.hash.slice(1) || "players").split("/");
  const tab = { player: "players", club: "clubs" }[name] || name;
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  const view = $("#view");
  view.replaceChildren(h("p", { class: "muted" }, "載入中…"));
  const fn = VIEWS[name] || VIEWS.players;
  const fresh = h("div", {});
  try {
    await fn(fresh, arg && decodeURIComponent(arg));
    view.replaceChildren(fresh);
  } catch (e) {
    view.replaceChildren(h("div", { class: "card" }, h("p", { class: "error" }, "錯誤：" + e.message)));
  }
}

function showLogin() {
  $("#login").hidden = false;
  $("#tabs").hidden = true;
  $("#view").replaceChildren();
}

async function start() {
  const s = await api("GET", "session");
  if (!s.authenticated) return showLogin();
  CSRF = s.csrf;
  $("#who").replaceChildren(s.actor, " ",
    s.password_required ? h("button", { class: "link", onclick: async () => { await api("POST", "logout"); location.reload(); } }, "登出") : "");
  $("#login").hidden = true;
  $("#tabs").hidden = false;
  route();
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("#tabs button").forEach((b) => b.addEventListener("click", () => (location.hash = "#" + b.dataset.tab)));
  window.addEventListener("hashchange", route);
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    try {
      const r = await api("POST", "login", { password: fd.get("password"), name: fd.get("name") });
      CSRF = r.csrf;
      $("#login-error").textContent = "";
      start();
    } catch (err) {
      $("#login-error").textContent = err.message;
    }
  });
  start();
});

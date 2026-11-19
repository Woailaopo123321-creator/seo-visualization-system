/* 全站公共脚本（window.SEO）
 * - escapeHtml / display / request / postJSON：安全输出与 JSON 请求（统一中文错误信息）
 * - toast / loading / empty / failed：提示消息与加载 / 空 / 出错三种状态
 * - fmtTime：UTC 时间 → 本地时间（带时区标注，例如 “2026-11-19 09:29（UTC+8）”）
 * - withButton：按钮忙碌状态（禁用 + 转圈 + aria-busy）
 * - renderTrajectory：ReAct / 工作流轨迹
 * - filterNav / toggleNav / cycleTheme：侧栏搜索、手机抽屉、浅色 / 深色主题
 */
(function () {
  "use strict";

  // ---------- 安全输出与请求 ----------
  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  }
  function display(value) {
    if (value === null || value === undefined) return "";
    return typeof value === "object" ? JSON.stringify(value, null, 2) : String(value);
  }
  async function request(url, options) {
    let res;
    try {
      res = await fetch(url, options);
    } catch (e) {
      throw new Error("网络错误：无法连接服务器，请检查服务是否在运行");
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* 非 JSON 响应 */ }
    if (!res.ok) {
      let msg = (data && (data.detail || data.error)) || ("请求失败（HTTP " + res.status + "）");
      if (res.status === 401 && !(data && data.detail)) msg = "需要管理员登录才能修改数据（左下角「登录」）";
      if (res.status === 403) msg = (data && data.detail) || "没有权限修改数据";
      if (res.status === 429) msg = (data && data.detail) || "请求过于频繁，请稍后再试";
      if (res.status >= 500 && !(data && data.detail)) msg = "服务器出错了，请稍后重试";
      const err = new Error(msg);
      err.status = res.status; err.data = data;
      throw err;
    }
    return data;
  }
  function postJSON(url, body) {
    return request(url, {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body || {})});
  }

  // ---------- 时间：数据库存 UTC，界面显示本地时间 ----------
  function tzLabel(date) {
    const off = -(date || new Date()).getTimezoneOffset();
    const h = Math.trunc(Math.abs(off) / 60), m = Math.abs(off) % 60;
    return "UTC" + (off >= 0 ? "+" : "-") + h + (m ? ":" + String(m).padStart(2, "0") : "");
  }
  function fmtTime(iso, opts) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (isNaN(d)) return String(iso);
    const p = n => String(n).padStart(2, "0");
    const text = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`;
    return (opts && opts.bare) ? text : `${text}（${tzLabel(d)}）`;
  }

  // ---------- 提示消息 ----------
  function toast(message, type, ms) {
    const stack = document.getElementById("toast-stack");
    if (!stack) return;
    const item = document.createElement("div");
    item.className = "toast-item " + (type || "info");
    item.setAttribute("role", type === "error" ? "alert" : "status");
    item.innerHTML = `<span>${escapeHtml(message)}</span><button type="button" aria-label="关闭提示">×</button>`;
    const close = () => { item.classList.add("out"); setTimeout(() => item.remove(), 220); };
    item.querySelector("button").addEventListener("click", close);
    stack.appendChild(item);
    while (stack.children.length > 4) stack.firstElementChild.remove();
    setTimeout(close, ms || (type === "error" ? 6000 : 3200));
  }

  // ---------- 加载 / 空 / 出错 状态 ----------
  function target(el) { return typeof el === "string" ? document.getElementById(el) : el; }
  function loading(el, text, compact) {
    const node = target(el); if (!node) return;
    node.setAttribute("aria-busy", "true");
    node.innerHTML = `<div class="state${compact ? " compact" : ""}" role="status"><span class="spinner" aria-hidden="true"></span><span>${escapeHtml(text || "加载中…")}</span></div>`;
  }
  function empty(el, title, hint, icon) {
    const node = target(el); if (!node) return;
    node.removeAttribute("aria-busy");
    node.innerHTML = `<div class="state"><div class="icon" aria-hidden="true">${escapeHtml(icon || "🗂️")}</div><strong>${escapeHtml(title)}</strong>${hint ? `<span>${escapeHtml(hint)}</span>` : ""}</div>`;
  }
  function failed(el, err, retry) {
    const node = target(el); if (!node) return;
    node.removeAttribute("aria-busy");
    const msg = err && err.message ? err.message : String(err || "出错了");
    node.innerHTML = `<div class="state error" role="alert"><div class="icon" aria-hidden="true">⚠️</div><strong>加载失败</strong><span>${escapeHtml(msg)}</span>${retry ? '<button type="button" class="btn-secondary btn-sm">重试</button>' : ""}</div>`;
    if (retry) node.querySelector("button").addEventListener("click", retry);
  }
  function done(el) { const node = target(el); if (node) node.removeAttribute("aria-busy"); }

  // ---------- 按钮忙碌状态 ----------
  async function withButton(btn, fn, busyText) {
    let label;
    if (btn) {
      label = btn.innerHTML;
      btn.disabled = true; btn.setAttribute("aria-busy", "true");
      btn.textContent = busyText || "处理中…";
    }
    try { return await fn(); }
    finally { if (btn) { btn.disabled = false; btn.removeAttribute("aria-busy"); btn.innerHTML = label; } }
  }

  // ---------- 轨迹 ----------
  const STEP_LABEL = {thought: "思考", action: "行动", observation: "观察", gate: "人工闸门"};
  function renderTrajectory(trajectory, title) {
    let html = `<h3>${escapeHtml(title || "ReAct 轨迹")}</h3>`;
    if (!(trajectory || []).length) return html + '<p class="muted">暂无轨迹。</p>';
    trajectory.forEach(item => {
      let body;
      if (item.type === "action") body = "🔧 " + escapeHtml(item.tool) + (item.input && Object.keys(item.input).length ? "<pre>" + escapeHtml(display(item.input)) + "</pre>" : "");
      else if (item.type === "observation") body = "<pre>" + escapeHtml(display(item.content)) + "</pre>";
      else body = escapeHtml(display(item.content));
      const label = STEP_LABEL[item.type] ? `${STEP_LABEL[item.type]} · ${String(item.type).toUpperCase()}` : String(item.type).toUpperCase();
      html += `<div class="step ${escapeHtml(item.type)}"><strong>${escapeHtml(label)}（第 ${escapeHtml(item.step)} 步）</strong><br>${body}</div>`;
    });
    return html;
  }

  // ---------- 侧栏导航 ----------
  function filterNav(q) {
    q = (q || "").trim().toLowerCase();
    document.querySelectorAll(".app-nav details").forEach(g => {
      let visible = 0;
      g.querySelectorAll("a").forEach(a => {
        const hit = !q || a.textContent.toLowerCase().includes(q) || a.getAttribute("href").includes(q);
        a.classList.toggle("app-hidden", !hit);
        if (hit) visible++;
      });
      g.classList.toggle("app-hidden", visible === 0);
      if (q && visible) g.open = true;
    });
  }
  function toggleNav(force) {
    const open = typeof force === "boolean" ? force : !document.body.classList.contains("nav-open");
    document.body.classList.toggle("nav-open", open);
    const btn = document.getElementById("app-menu-btn");
    if (btn) { btn.setAttribute("aria-expanded", String(open)); btn.setAttribute("aria-label", open ? "关闭导航" : "打开导航"); }
    if (open) { const s = document.querySelector(".app-search"); if (s) setTimeout(() => s.focus(), 50); }
    else if (btn && document.activeElement && document.getElementById("app-sidebar").contains(document.activeElement)) btn.focus();
  }

  // ---------- 主题：自动（跟随系统）→ 浅色 → 深色 ----------
  const THEMES = ["auto", "light", "dark"];
  const THEME_LABEL = {auto: "◐ 自动", light: "☀ 浅色", dark: "☾ 深色"};
  function currentTheme() { return document.documentElement.dataset.theme || "auto"; }
  function applyTheme(t) {
    if (t === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = t;
    try { t === "auto" ? localStorage.removeItem("seo-theme") : localStorage.setItem("seo-theme", t); } catch (e) { /* 隐私模式 */ }
    const btn = document.getElementById("theme-btn");
    if (btn) { btn.textContent = THEME_LABEL[t]; btn.title = "外观：" + THEME_LABEL[t].slice(2) + "（点击切换）"; }
  }
  function cycleTheme() { applyTheme(THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length]); }

  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && document.body.classList.contains("nav-open")) toggleNav(false);
    // “/” 快速聚焦侧栏搜索（输入框里不触发）
    if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
      const s = document.querySelector(".app-search");
      if (s && s.offsetParent !== null) { e.preventDefault(); s.focus(); }
    }
  });
  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(currentTheme());
    document.querySelectorAll("[data-tz-note]").forEach(n => { n.textContent = "时间按本地时区显示（" + tzLabel() + "）"; });
    document.querySelectorAll("time[data-utc]").forEach(n => { n.textContent = fmtTime(n.getAttribute("datetime")); });
    // 手机抽屉里点了链接后自动收起
    const side = document.getElementById("app-sidebar");
    if (side) side.addEventListener("click", e => { if (e.target.closest(".app-nav a")) toggleNav(false); });
  });

  window.SEO = {escapeHtml, display, request, postJSON, renderTrajectory, withButton, toast, loading, empty, failed,
                done, fmtTime, tzLabel, filterNav, toggleNav, cycleTheme};
})();

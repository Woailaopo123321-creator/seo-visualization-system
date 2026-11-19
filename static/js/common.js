(function () {
  const COLORS = ["#0f766e", "#0e7490", "#b45309", "#047857", "#0369a1", "#be123c", "#64748b"];

  function escapeHTML(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function fetchJSON(url, options) {
    let response;
    try {
      response = await fetch(url, options);
    } catch (error) {
      throw new Error("网络请求失败");
    }
    let data = null;
    try {
      data = await response.json();
    } catch (error) {
      throw new Error("服务器没有返回 JSON");
    }
    if (!response.ok) {
      throw new Error((data && data.error) || "请求失败");
    }
    return data;
  }

  function showError(element, error) {
    if (!element) return;
    element.hidden = false;
    element.innerHTML = `<p class="error">${escapeHTML(error.message || "数据加载失败")}</p>`;
  }

  function clearStatus(element) {
    if (!element) return;
    element.textContent = "";
    element.hidden = true;
  }

  function applyChartDefaults() {
    if (typeof Chart === "undefined") {
      throw new Error("图表库未能加载，请检查网络后刷新");
    }
    Chart.defaults.font.family = '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif';
    Chart.defaults.color = "#334155";
    Chart.defaults.plugins.legend.labels.boxWidth = 12;
  }

  function mountChart(canvas, config) {
    const existing = typeof Chart !== "undefined" ? Chart.getChart(canvas) : null;
    if (existing) existing.destroy();
    return new Chart(canvas, config);
  }

  function renderChartCard(canvas, spec) {
    if (!canvas || !spec) return null;
    const badge = document.querySelector(`[data-badge-for="${canvas.id}"]`);
    const caption = document.querySelector(`[data-caption-for="${canvas.id}"]`);
    if (badge) {
      badge.textContent = spec.badge || "";
      badge.className = `badge ${spec.sample ? "badge-sample" : "badge-live"}`;
    }
    if (caption) caption.textContent = spec.caption || "";

    const datasets = (spec.datasets || []).map((item, index) => {
      const color = COLORS[index % COLORS.length];
      const isLine = item.type === "line";
      return {
        type: item.type,
        label: item.label,
        data: item.data,
        backgroundColor: item.backgroundColor || color,
        borderColor: item.borderColor || (isLine ? color : "transparent"),
        borderWidth: isLine ? 2 : 1,
        borderDash: item.dashed ? [6, 4] : undefined,
        pointRadius: 0,
        fill: false,
        stack: item.stack,
        borderRadius: spec.stacked || isLine ? 0 : 6,
        spanGaps: true,
      };
    });

    const isRound = spec.type === "doughnut" || spec.type === "pie";
    const valueAxis = {
      beginAtZero: true,
      stacked: Boolean(spec.stacked),
      suggestedMax: spec.y_max == null ? undefined : spec.y_max,
      ticks: spec.y_max && spec.y_max <= 1
        ? { stepSize: spec.y_max <= 0.4 ? 0.05 : 0.1 }
        : { precision: 0 },
    };
    const labelAxis = { stacked: Boolean(spec.stacked), grid: { display: false } };
    const options = {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 450 },
      indexAxis: spec.horizontal ? "y" : "x",
      plugins: { legend: { display: spec.legend !== false, position: "bottom" } },
    };
    if (!isRound) {
      options.scales = spec.horizontal
        ? { x: valueAxis, y: labelAxis }
        : { x: labelAxis, y: valueAxis };
    } else {
      const values = (datasets[0] && datasets[0].data) || [];
      const sum = values.reduce((total, value) => total + Number(value || 0), 0);
      if (sum > 0.99 && sum < 1.01) {
        options.plugins.tooltip = {
          callbacks: {
            label(context) {
              return `${context.label}: ${(Number(context.raw) * 100).toFixed(0)}%`;
            },
          },
        };
      }
    }
    return mountChart(canvas, {
      type: spec.type,
      data: { labels: spec.labels, datasets },
      options,
    });
  }

  function renderStats(container, stats) {
    if (!container) return;
    container.innerHTML = (stats || []).map((item) => `
      <article class="stat">
        <div class="stat-label">${escapeHTML(item.label)}</div>
        <div class="stat-num">${escapeHTML(item.value)}</div>
        ${item.hint ? `<p class="stat-hint">${escapeHTML(item.hint)}</p>` : ""}
        ${item.badge ? `<span class="badge ${item.sample ? "badge-sample" : "badge-live"}">${escapeHTML(item.badge)}</span>` : ""}
      </article>
    `).join("");
  }

  function renderFields(fields) {
    return `<dl class="fields">${(fields || []).map((field) => `
      <div><dt>${escapeHTML(field.label)}</dt><dd>${escapeHTML(field.value)}</dd></div>
    `).join("")}</dl>`;
  }

  function renderTable(table, columns, rows) {
    if (!table) return;
    const head = `<tr>${columns.map((column) => `<th>${escapeHTML(column.label)}</th>`).join("")}</tr>`;
    const body = (rows || []).map((row) => `
      <tr>${columns.map((column) => `<td>${escapeHTML(row[column.key] ?? "")}</td>`).join("")}</tr>
    `).join("");
    table.innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
  }

  function debounce(fn, wait) {
    let timer = 0;
    return function debounced(...args) {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn(...args), wait);
    };
  }

  function scoreLocally(features, weights, threshold, priority) {
    let total = 0;
    const breakdown = [];
    Object.keys(weights).forEach((key) => {
      const weight = Number(weights[key]);
      const value = Number(features[key] || 0);
      total += value * weight;
      breakdown.push({
        key,
        label: key,
        weight,
        value: Math.round(value * 10000) / 10000,
        contribution: Math.round(value * weight * 10000) / 10000,
      });
    });
    const quality = Math.round(total * 100) / 100;
    const passed = quality >= Number(threshold);
    return {
      quality_score: quality,
      threshold: Number(threshold),
      passed,
      requires_hitl: true,
      priority: priority || "相关性 > 编辑性 > 流量",
      human_gate: passed
        ? "已达阈值，可以进入外展候选，发出前必须人工确认"
        : "未达阈值。若仍要联系，必须人工确认",
      breakdown,
      feature_source: "本地试算",
    };
  }

  window.SEOViz = {
    COLORS,
    escapeHTML,
    fetchJSON,
    showError,
    clearStatus,
    applyChartDefaults,
    mountChart,
    renderChartCard,
    renderStats,
    renderFields,
    renderTable,
    debounce,
    scoreLocally,
  };
})();

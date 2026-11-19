document.addEventListener("DOMContentLoaded", async () => {
  const alertBox = document.getElementById("page-alert");
  const form = document.getElementById("score-form");
  const result = document.getElementById("score-result");
  const list = document.getElementById("candidate-list");
  let requestId = 0;
  let candidates = [];
  let weightMap = {};
  let labelMap = {};
  let threshold = 0.7;
  let priority = "相关性 > 编辑性 > 流量";

  function readFeatures() {
    const features = {};
    form.querySelectorAll("input[type=range]").forEach((input) => {
      features[input.dataset.key] = Math.round(Number(input.value) * 100) / 100;
    });
    return features;
  }

  function labeledBreakdown(breakdown) {
    return (breakdown || []).map((item) => ({
      ...item,
      label: labelMap[item.key] || item.label || item.key,
    }));
  }

  function renderRadar(breakdown) {
    const canvas = document.getElementById("radar-chart");
    SEOViz.mountChart(canvas, {
      type: "radar",
      data: {
        labels: breakdown.map((item) => item.label),
        datasets: [{
          label: "当前特征",
          data: breakdown.map((item) => item.value),
          borderColor: "#0f766e",
          backgroundColor: "rgba(15, 118, 110, 0.18)",
          pointBackgroundColor: "#0f766e",
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 350 },
        plugins: { legend: { position: "bottom" } },
        scales: { r: { min: 0, max: 1, ticks: { stepSize: 0.2 } } },
      },
    });
  }

  function renderResult(data, { animate = false } = {}) {
    const stateClass = data.passed ? "pass" : "fail";
    const stateText = data.passed ? "已达阈值" : "未达阈值";
    const breakdown = labeledBreakdown(data.breakdown);
    const rows = breakdown.map((item) => `
      <tr>
        <td>${SEOViz.escapeHTML(item.label)}</td>
        <td>${Number(item.value).toFixed(2)}</td>
        <td>${Number(item.contribution).toFixed(4)}</td>
      </tr>
    `).join("");
    result.innerHTML = `
      <p class="score-num ${stateClass}${animate ? " is-updating" : ""}">${Number(data.quality_score).toFixed(2)}</p>
      <p class="${stateClass}">${stateText}</p>
      <p>${SEOViz.escapeHTML(data.human_gate)}</p>
      <p class="hint">阈值 ${Number(data.threshold).toFixed(2)} · ${SEOViz.escapeHTML(data.priority)} · ${SEOViz.escapeHTML(data.feature_source || "模型计算")}</p>
      <table>
        <thead><tr><th>维度</th><th>得分</th><th>贡献</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    renderRadar(breakdown);
    if (animate) {
      window.requestAnimationFrame(() => {
        const scoreEl = result.querySelector(".score-num");
        if (scoreEl) scoreEl.classList.remove("is-updating");
      });
    }
  }

  function applyFeatures(features) {
    Object.entries(features).forEach(([key, value]) => {
      const input = form.querySelector(`input[data-key="${key}"]`);
      const output = document.getElementById(`out-${key}`);
      const text = Number(value).toFixed(2);
      if (input) input.value = text;
      if (output) output.textContent = text;
    });
  }

  function markSelected(index) {
    list.querySelectorAll(".candidate").forEach((button) => {
      button.classList.toggle("is-selected", Number(button.dataset.index) === index);
    });
  }

  function previewLocally() {
    const local = SEOViz.scoreLocally(readFeatures(), weightMap, threshold, priority);
    renderResult(local, { animate: true });
  }

  async function submitScore() {
    const current = ++requestId;
    try {
      const data = await SEOViz.fetchJSON("/api/backlinks/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ features: readFeatures() }),
      });
      if (current !== requestId) return;
      renderResult(data, { animate: true });
    } catch (error) {
      if (current !== requestId) return;
      result.innerHTML = `<p class="error">${SEOViz.escapeHTML(error.message)}</p>`;
    }
  }

  const syncServer = SEOViz.debounce(() => {
    submitScore();
  }, 400);

  try {
    SEOViz.applyChartDefaults();
    const data = await SEOViz.fetchJSON("/api/backlinks/scoring");
    candidates = data.candidates || [];
    threshold = Number(data.threshold);
    priority = data.priority || priority;
    weightMap = {};
    labelMap = {};
    (data.weights || []).forEach((item) => {
      weightMap[item.key] = Number(item.weight);
      labelMap[item.key] = item.label;
    });
    SEOViz.renderChartCard(document.getElementById("weights-chart"), data.weights_chart);
    SEOViz.renderChartCard(document.getElementById("candidates-chart"), data.candidates_chart);
    list.innerHTML = candidates.map((item, index) => `
      <button type="button" class="candidate" data-index="${index}">
        <span>${SEOViz.escapeHTML(item.name)}</span>
        <strong class="${item.result.passed ? "pass" : "fail"}">${Number(item.result.quality_score).toFixed(2)}</strong>
      </button>
    `).join("");
    list.addEventListener("click", (event) => {
      const button = event.target.closest(".candidate");
      if (!button) return;
      const index = Number(button.dataset.index);
      const item = candidates[index];
      applyFeatures(item.features);
      markSelected(index);
      renderResult(item.result, { animate: true });
    });
    const defaultIndex = candidates.findIndex((item) => item.name === "默认示例目标");
    if (defaultIndex >= 0) {
      applyFeatures(candidates[defaultIndex].features);
      markSelected(defaultIndex);
    }
    renderResult(data.default_result);
    form.addEventListener("input", (event) => {
      const input = event.target;
      if (!(input instanceof HTMLInputElement) || input.type !== "range") return;
      const output = document.getElementById(`out-${input.dataset.key}`);
      if (output) output.textContent = Number(input.value).toFixed(2);
      markSelected(-1);
      previewLocally();
      syncServer();
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      markSelected(-1);
      submitScore();
    });
    SEOViz.clearStatus(alertBox);
  } catch (error) {
    SEOViz.showError(alertBox, error);
  }
});

document.addEventListener("DOMContentLoaded", async () => {
  const alertBox = document.getElementById("page-alert");
  try {
    SEOViz.applyChartDefaults();
    const data = await SEOViz.fetchJSON("/api/backlinks/competitors");
    const caption = document.getElementById("competitor-caption");
    if (caption) caption.textContent = data.caption;
    SEOViz.renderStats(document.getElementById("stats"), data.stats);
    SEOViz.renderChartCard(document.getElementById("domains-chart"), data.domains_chart);
    SEOViz.renderChartCard(document.getElementById("types-chart"), data.types_chart);
    SEOViz.renderChartCard(document.getElementById("research-chart"), data.research_chart);
    const recommendation = document.getElementById("recommendation");
    if (recommendation) recommendation.textContent = data.recommendation;
    const patterns = document.getElementById("patterns");
    if (patterns) {
      patterns.innerHTML = (data.patterns || [])
        .map((pattern) => `<span class="tag">${SEOViz.escapeHTML(pattern)}</span>`)
        .join("");
    }
    SEOViz.renderTable(document.getElementById("gap-table"), [
      { key: "domain", label: "域名" },
      { key: "overlap", label: "重叠竞品数" },
      { key: "pattern", label: "模式" },
      { key: "note", label: "说明" },
    ], data.gap_rows);
    SEOViz.clearStatus(alertBox);
  } catch (error) {
    SEOViz.showError(alertBox, error);
  }
});

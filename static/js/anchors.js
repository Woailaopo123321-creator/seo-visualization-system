document.addEventListener("DOMContentLoaded", async () => {
  const alertBox = document.getElementById("page-alert");
  try {
    SEOViz.applyChartDefaults();
    const data = await SEOViz.fetchJSON("/api/backlinks/anchors");
    const total = document.getElementById("anchor-total");
    if (total) total.textContent = `合计 ${data.total} 条。${data.caption}`;
    SEOViz.renderChartCard(document.getElementById("share-chart"), data.share_chart);
    SEOViz.renderChartCard(document.getElementById("count-chart"), data.count_chart);
    SEOViz.renderTable(document.getElementById("anchor-table"), [
      { key: "type", label: "类型" },
      { key: "count", label: "条数" },
      { key: "share_label", label: "占比" },
      { key: "example", label: "示例锚文本" },
      { key: "natural", label: "怎么看" },
    ], data.items);
    SEOViz.clearStatus(alertBox);
  } catch (error) {
    SEOViz.showError(alertBox, error);
  }
});

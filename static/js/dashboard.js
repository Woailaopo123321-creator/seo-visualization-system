document.addEventListener("DOMContentLoaded", async () => {
  const alertBox = document.getElementById("page-alert");
  try {
    SEOViz.applyChartDefaults();
    const data = await SEOViz.fetchJSON("/api/dashboard");
    SEOViz.renderStats(document.getElementById("stats"), data.stats);
    SEOViz.renderChartCard(document.getElementById("weights-chart"), data.weights_chart);
    SEOViz.renderChartCard(document.getElementById("candidates-chart"), data.candidates_chart);
    SEOViz.clearStatus(alertBox);
  } catch (error) {
    SEOViz.showError(alertBox, error);
  }
});

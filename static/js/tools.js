document.addEventListener("DOMContentLoaded", async () => {
  const alertBox = document.getElementById("page-alert");
  try {
    SEOViz.applyChartDefaults();
    const data = await SEOViz.fetchJSON("/api/backlinks/tools");
    const caption = document.getElementById("tools-caption");
    if (caption) caption.textContent = data.caption;
    (data.stages || []).forEach((stage) => {
      const slot = document.querySelector(`[data-stage="${stage.id}"]`);
      if (slot) slot.innerHTML = SEOViz.renderFields(stage.observation_fields);
    });
    const external = document.getElementById("external-tools");
    if (external) {
      external.innerHTML = (data.external_tools || []).map((item) => `
        <article class="link-card">
          <strong>${SEOViz.escapeHTML(item.task_label)}</strong>
          <p class="tool-name">${SEOViz.escapeHTML(item.recommended)}</p>
          <span>${SEOViz.escapeHTML(item.reason)}</span>
          <span>${SEOViz.escapeHTML(item.human_gate)}</span>
        </article>
      `).join("");
    }
    SEOViz.renderChartCard(document.getElementById("funnel-chart"), data.funnel_chart);
    SEOViz.clearStatus(alertBox);
  } catch (error) {
    SEOViz.showError(alertBox, error);
  }
});

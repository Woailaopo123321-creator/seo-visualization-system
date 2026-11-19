document.addEventListener("DOMContentLoaded", async () => {
  const alertBox = document.getElementById("page-alert");
  try {
    SEOViz.applyChartDefaults();
    const data = await SEOViz.fetchJSON("/api/workflow");
    const caption = document.getElementById("workflow-caption");
    if (caption) caption.textContent = data.caption;
    const badge = document.getElementById("run-badge");
    if (badge) badge.textContent = data.finished_label ? `${data.badge} · ${data.finished_label}` : data.badge;
    const answer = document.getElementById("answer");
    if (answer) answer.innerHTML = SEOViz.renderFields(data.answer_fields);
    const steps = document.getElementById("steps");
    if (steps) {
      steps.innerHTML = (data.steps || []).map((step) => `
        <article class="step-card">
          <h3>
            <span>步骤 ${SEOViz.escapeHTML(step.step)} · ${SEOViz.escapeHTML(step.stage_label || "")}</span>
          </h3>
          ${(step.events || []).map((event) => `
            <div class="event">
              <div class="event-type ${SEOViz.escapeHTML(event.type)}">${SEOViz.escapeHTML(event.type_label)}</div>
              <div>${SEOViz.renderFields(event.fields)}</div>
            </div>
          `).join("")}
        </article>
      `).join("");
    }
    SEOViz.renderChartCard(document.getElementById("score-chart"), data.score_chart);
    SEOViz.clearStatus(alertBox);
  } catch (error) {
    SEOViz.showError(alertBox, error);
  }
});

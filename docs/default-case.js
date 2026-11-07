"use strict";
// This script runs after app.js. Only the bundled synthetic workbook is public.
async function loadDefaultCase() {
  if (state.busy) return;
  state.busy = true;
  const button = $("#restore-default");
  button.disabled = true;
  $("#file-input").disabled = true;
  try {
    const result = await (await api('/api/default')).json();
    state.data = result;
    state.severity = "Todos"; state.findingQuery = ""; state.eventQuery = "";
    state.page = 0; state.hour = null;
    $("#finding-search").value = ""; $("#event-search").value = "";
    renderCase(); showView('overview');
    notice('Ejemplo sintético cargado. Explora los resultados o cambia el Excel para investigar tus propios datos.');
  } catch (error) { notice(error.message, true); }
  finally { state.busy = false; button.disabled = false; $("#file-input").disabled = false; }
}
$("#restore-default").addEventListener('click', loadDefaultCase);
const sourceObserver = new MutationObserver(() => {
  const demo = state.data?.id === 'bundled-demo';
  $("#dataset-status").textContent = demo ? 'EJEMPLO SINTÉTICO' : 'EXCEL PERSONALIZADO';
  $("#dataset-status").classList.toggle('custom-dataset', !demo);
});
sourceObserver.observe($("#case-filename"), {childList:true});
for (const key of ['analyst','client','company','reference']) {
  const input = $(`#case-${key}`);
  input.addEventListener('input', () => {
    $("#case-context-preview").textContent = ['analyst','client','company','reference']
      .map(k => $(`#case-${k}`).value.trim()).filter(Boolean).join(' · ');
  });
  input.dispatchEvent(new Event('input'));
}
loadDefaultCase();

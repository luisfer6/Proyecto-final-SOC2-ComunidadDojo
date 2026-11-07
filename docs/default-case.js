"use strict";
// This script runs after app.js. The bundled project workbook is public.
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
    notice(`Excel del proyecto cargado: ${number(result.metadata.rows)} registros disponibles. Explora el análisis o selecciona otro Excel.`);
  } catch (error) { notice(error.message, true); }
  finally { state.busy = false; button.disabled = false; $("#file-input").disabled = false; }
}
$("#restore-default").addEventListener('click', loadDefaultCase);
const sourceObserver = new MutationObserver(() => {
  const included = state.data?.id === 'bundled-case';
  $("#dataset-status").textContent = included ? 'EXCEL DEL PROYECTO' : 'EXCEL PERSONALIZADO';
  $("#dataset-status").classList.toggle('custom-dataset', !included);
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

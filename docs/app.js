"use strict";
const $ = (selector) => document.querySelector(selector);
const state = {data:null, view:"overview", severity:"Todos", findingQuery:"", eventQuery:"", hour:null, page:0, busy:false, ollama:false, ollamaMessage:""};
const titles = {
  overview:["Resumen de la investigación","Una vista de la evidencia y las señales que merecen tu atención."],
  findings:["Hallazgos con fundamento.","Revisa qué ocurrió, por qué importa y qué falta por validar."],
  events:["Explora la evidencia.","Cada evento conserva sus campos originales y su ubicación en el archivo."],
  correlations:["Conecta las señales.","Asociaciones explícitas para orientar la investigación, sin asumir causalidad."],
  report:["Del análisis al informe.","Un documento trazable para el equipo técnico y la dirección."],
};
const riskClass = {"Crítico":"critical","Alto":"high","Medio":"medium","Bajo":"low"};
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const number = (value) => new Intl.NumberFormat("es").format(value);
const badge = (severity) => `<span class="pill severity-${riskClass[severity] || "low"}">${esc(severity)}</span>`;
function notice(message, error=false) {
  $("#notice").textContent = message;
  $("#notice").className = `notice${error?" error":""}`;
}
function showView(view) {
  if (!state.data) {
    notice("Selecciona un Excel o CSV para comenzar la investigación.");
    $("#file-input").focus();
    return;
  }
  state.view = view;
  document.querySelectorAll(".view").forEach(el=>el.classList.toggle("hidden",el.id!==`view-${view}`));
  document.querySelectorAll(".nav-item").forEach(el=> {
    const selected = el.dataset.view === view;
    el.classList.toggle("active",selected);
    if(selected) el.setAttribute("aria-current","page"); else el.removeAttribute("aria-current");
  });
  $("#page-title").textContent = titles[view][0];
  $("#page-description").textContent = titles[view][1];
  $("#upload-section").classList.toggle("hidden", view !== "overview");
  if(view==="events") renderEvents();
  if(view==="findings") renderFindings();
}
function setConnection(connected) {
  $("#connection").dataset.status=connected?"online":"offline";
  $("#connection-label").textContent="Análisis en tu navegador";
}
async function api(url, options={}) {
  if(window.socBrowser) return window.socBrowser.api(url,options);
  let response;
  try {
    response = await fetch(url,options);
  } catch {
    setConnection(false);
    throw new Error("No se pudo conectar con el servidor local. Ejecuta iniciar.cmd en la carpeta del proyecto, deja esa ventana abierta y vuelve a seleccionar el Excel.");
  }
  setConnection(true);
  if(!response.ok) {
    const error = await response.json().catch(()=>({}));
    throw new Error(typeof error.detail === "string" ? error.detail : `No se pudo completar la operación (${response.status}).`);
  }
  return response;
}
async function upload(file) {
  if(!file || state.busy) return;
  if(!/\.(xlsx|csv)$/i.test(file.name)) return notice("Selecciona un archivo Excel .xlsx o CSV .csv.",true);
  if(file.size>10*1024*1024) return notice("El archivo supera el máximo de 10 MB.",true);
  state.busy=true;
  $("#loading").classList.remove("hidden");
  $("#file-input").disabled=true;
  $("#timezone").disabled=true;
  $("#clear-case").disabled=true;
  $("#notice").classList.add("hidden");
  try {
    const form = new FormData();
    form.append("file",file);
    if($("#timezone").value !== "") form.append("timezone_offset",$("#timezone").value);
    const result = await (await api("/api/analyze",{method:"POST",body:form})).json();
    const previous=state.data?.id;
    state.data=result;
    state.severity="Todos"; state.findingQuery=""; state.eventQuery="";state.page=0;state.hour=null;
    $("#finding-search").value="";$("#event-search").value="";
    renderCase();
    showView("overview");
    if(previous) await api(`/api/cases/${previous}`,{method:"DELETE"});
    notice(`${number(result.summary.events)} eventos únicos analizados. ${number(result.summary.findings)} hallazgos disponibles para revisión.`);
  } catch(error) {
    notice(error.message,true);
  } finally {
    state.busy=false;
    $("#loading").classList.add("hidden");
    $("#file-input").disabled=false;$("#timezone").disabled=false;$("#clear-case").disabled=false;
    $("#file-input").value="";
  }
}
function renderCase() {
  const d=state.data, s=d.summary;
  $("#empty-state").classList.add("hidden");
  $("#case-content").classList.remove("hidden");
  $("#download-top").classList.remove("hidden");
  $("#breadcrumb-current").textContent="Análisis de evidencia";
  $("#nav-count").textContent=s.findings;
  $("#case-filename").textContent=d.metadata.filename;
  $("#case-filename").title=d.metadata.filename;
  $("#case-rows").textContent=`${number(d.metadata.rows)} filas · ${d.metadata.sheets.filter(s=>!s.skipped).length} hoja(s)`;
  const stats=[
    ["Eventos analizados",number(s.events),"Únicos · Duplicados preservados","≡",""],
    ["Hallazgos detectados",number(s.findings),`${s.severity.Crítico} críticos · ${s.severity.Alto} altos`,"◎","emphasis"],
    ["Equipos observados",number(s.hosts),`${s.users} cuentas en el archivo`,"▦",""],
    ["Asociaciones a investigar",number(s.hypotheses),"Número de incidentes por determinar","◇",""],
  ];
  $("#stats").innerHTML=stats.map(([label,value,note,icon,cls])=>`<article class="stat ${cls}"><div class="stat-top">${label}<span class="stat-icon" aria-hidden="true">${icon}</span></div><div class="stat-value">${value}</div><div class="stat-note">${note}</div></article>`).join("");
  renderTimeline();
  $("#risk-chart").innerHTML=Object.entries(s.severity).map(([risk,count])=>`<button class="risk-row" data-risk="${esc(risk)}" aria-label="Ver ${count} hallazgos de criticidad ${esc(risk)}"><span class="risk-label">${risk}</span><span class="risk-track"><svg viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true"><rect class="risk-${riskClass[risk]}" width="${s.findings ? Math.max(0,count/s.findings*100) : 0}" height="6" rx="3"/></svg></span><span class="risk-value">${count}</span></button>`).join("")+`<div class="risk-total">${s.findings} hallazgos · Selecciona una criticidad para filtrar</div>`;
  $("#top-findings").innerHTML=d.findings.slice(0,4).map(f=>`<div class="finding-preview"><span class="finding-icon" aria-hidden="true">⌁</span><div class="text"><button data-finding="${f.id}">${esc(f.title)}</button><small>${f.id} · ${esc(f.hosts.join(", "))} · ${f.evidence.length} evidencias</small></div>${badge(f.severity)}</div>`).join("") || '<p class="fine-print">No se detectaron coincidencias con las reglas actuales. Revisa la cobertura antes de concluir.</p>';
  $("#ai-summary").textContent=`${d.ai.name} · ${d.ai.status}. ${d.ai.candidates.length} eventos priorizados para una segunda revisión.`;
  $("#ai-candidates").innerHTML=d.ai.candidates.slice(0,3).map(c=>`<div class="ai-candidate"><button class="text-button" data-event="${c.ref}">${c.ref} →</button><span>Score ${c.score.toFixed(3)}</span></div>`).join("");
  $("#quality-count").textContent=`· ${d.metadata.warnings.length} notas`;
  $("#quality-content").innerHTML=d.metadata.warnings.map(w=>`<p>${esc(w)}</p>`).join("")+
    `<p>Campos vacíos: ${esc(JSON.stringify(d.metadata.missing_fields))}</p>`+
    d.metadata.sheets.map(s=>`<p>Hoja ${esc(s.name)}: ${s.rows} filas ${s.skipped?"(omitida)":""}.<br><code>${esc(JSON.stringify(s.mapping))}</code></p>`).join("")+
    `<p>SHA-256: <code>${d.metadata.sha256}</code></p>`;
  renderFindings();renderCorrelations();renderReport();
}
function renderTimeline() {
  const all=state.data.timeline;
  // A scroll-free chart shows the first 24 buckets; the complete timeline is in the PDF/JSON.
  const buckets=all.slice(0,24), max=Math.max(1,...buckets.map(b=>b.events));
  const width=600, height=165, bottom=143, left=32, plot=550;
  const step=plot/Math.max(buckets.length,1), barWidth=Math.min(48,step*.6);
  let svg=`<svg viewBox="0 0 ${width} ${height}" role="group" aria-label="Actividad por hora. Barras seleccionables con teclado.">`;
  for(let i=0;i<4;i++) {
    const y=bottom-i*40;
    svg+=`<line class="chart-grid" x1="${left}" y1="${y}" x2="590" y2="${y}"/><text class="chart-label" x="22" y="${y+3}" text-anchor="end">${Math.round(max*i/3)}</text>`;
  }
  buckets.forEach((b,i)=>{
    const h=b.events/max*120, fh=b.flagged/max*120, x=left+step*i+(step-barWidth)/2;
    const label=`${b.hour}, ${b.clock}: ${b.events} eventos, ${b.flagged} con señal`;
    svg+=`<rect class="chart-bar" data-bucket="${i}" role="button" tabindex="0" aria-label="${esc(label)}" x="${x}" y="${bottom-h}" width="${barWidth}" height="${h}" rx="3"><title>${esc(label)}</title></rect><rect class="chart-flagged" x="${x}" y="${bottom-fh}" width="${barWidth}" height="${fh}" rx="2"/>`;
    if(buckets.length<=12 || i%2===0) svg+=`<text class="chart-label" x="${x+barWidth/2}" y="160" text-anchor="middle">${esc(b.hour.slice(-2))}:00</text>`;
  });
  svg+="</svg>";
  $("#timeline-chart").innerHTML=buckets.length?svg:'<p class="fine-print">No hay fechas interpretables para construir la cronología.</p>';
  $("#timeline-caption").textContent=all.length?`${all[0].hour.slice(0,10)} · ${new Set(all.map(b=>b.clock)).size} dominio(s) temporal(es). ${all.length>24?"Mostrando los primeros 24 intervalos. ":""}La hora original se conserva cuando no hay zona declarada.`:"";
}
function renderFindings() {
  $("#severity-filters").innerHTML=["Todos",...Object.keys(riskClass)].map(r=>`<button class="filter-pill ${state.severity===r?"active":""}" data-risk="${r}" aria-pressed="${state.severity===r}">${r} ${r==="Todos"?state.data.findings.length:state.data.summary.severity[r]}</button>`).join("");
  const q=state.findingQuery.toLowerCase();
  const findings=state.data.findings.filter(f=>(state.severity==="Todos"||f.severity===state.severity)&&JSON.stringify(f).toLowerCase().includes(q));
  $("#findings-list").innerHTML=findings.map(f=>`<article class="finding-card"><div>${badge(f.severity)}<span class="finding-tag">${f.id} / ${esc(f.category)} / ${f.rule}</span><h3>${esc(f.title)}</h3><p>${esc(f.observation)}</p><div class="finding-meta"><span>Equipo: ${esc(f.hosts.join(", ")||"No disponible")}</span><span>${f.evidence.length} evidencias</span><span>Confianza: ${esc(f.confidence)}</span></div></div><button class="button secondary" data-finding="${f.id}">Revisar evidencia ↗</button></article>`).join("") || '<div class="empty-message">No hay hallazgos que coincidan con estos filtros.</div>';
}
function renderEvents() {
  const q=state.eventQuery.toLowerCase();
  const list=state.data.events.filter(e=>JSON.stringify(e.raw).toLowerCase().includes(q)||e.ref.toLowerCase().includes(q))
    .filter(e=>!state.hour || (e.clock===state.hour.clock && (e.utc||e.timestamp).slice(0,13)===state.hour.hour));
  const pages=Math.ceil(list.length/50);state.page=Math.max(0,Math.min(state.page,pages-1));
  $("#events-count").textContent=`${number(list.length)} eventos${state.hour?` · ${state.hour.hour}`:""}`;
  $("#events-body").innerHTML=list.slice(state.page*50,state.page*50+50).map(e=>`<tr><td><button class="text-button" data-event="${e.ref}">${e.ref} ↗</button><small>${esc(e.log_id)}${e.duplicate_of?" · Duplicado":""}</small></td><td>${esc(e.timestamp)}<small>${esc(e.clock)}</small></td><td>${esc(e.host||"—")}</td><td>${esc(e.event_id)}<small>${esc(e.provider)}</small></td><td>${esc(e.user||"—")}</td><td>${esc(e.source_ip||"—")}</td><td>${esc(e.result||"—")}</td></tr>`).join("") || '<tr><td colspan="7">No hay eventos que coincidan con el filtro.</td></tr>';
  $("#page-info").textContent=`Página ${list.length?state.page+1:0} de ${pages} · 50 filas por página`;
  $("#previous-page").disabled=state.page===0;
  $("#next-page").disabled=state.page+1>=pages;
}
function renderCorrelations() {
  $("#correlations-list").innerHTML=state.data.incidents.map(c=>`<article class="panel correlation-card"><span class="pill pending">${c.id} · Hipótesis</span><h3>${esc(c.title)}</h3><div class="entity-line">${esc(c.host)} · ${esc(c.user)} · ${esc(c.source_ip)}</div><p>${esc(c.reason)}</p><div class="reference-list">${c.findings.map(id=>`<button class="reference-button" data-finding="${id}">${id} ↗</button>`).join("")}${c.evidence.map(id=>`<button class="reference-button" data-event="${id}">${id}</button>`).join("")}</div></article>`).join("") || '<div class="empty-message">No se encontraron asociaciones que cumplan las claves y el intervalo definidos. Revisa los hallazgos por separado.</div>';
}
function renderReport() {
  const d=state.data;
  $("#executive-summary").innerHTML=d.narrative.facts.map(f=>`<p>${esc(f)}</p>`).join("");
  $("#report-limitations").innerHTML=d.limitations.map(l=>`<p>${esc(l)}</p>`).join("");
  $("#file-hash").textContent=d.metadata.sha256;
  $("#assist-button").disabled=!state.ollama || !d.findings.length;
  $("#ollama-status").textContent=state.ollama ? (d.findings.length ? state.ollamaMessage + " La selección se realiza sólo al solicitarla." : "No hay hallazgos para priorizar.") : state.ollamaMessage;
}
function dialog(title,html) {
  $("#dialog-title").textContent=title;$("#dialog-content").innerHTML=html;
  if(!$("#detail-dialog").open) $("#detail-dialog").showModal();
  $("#detail-dialog").scrollTop=0;
}
function showFinding(id) {
  const f=state.data?.findings.find(f=>f.id===id);if(!f)return;
  const labels=[["Observación","observation"],["Justificación de criticidad","rationale"],["Alternativa legítima","alternative"],["Impacto condicionado","impact"],["Validación propuesta","validation"],["Acción propuesta","action"]];
  dialog(`${f.id} · ${f.title}`,`${badge(f.severity)} <span class="finding-tag">Confianza: ${esc(f.confidence)} · ${f.rule}</span>`+
    labels.map(([label,key])=>`<h3>${label}</h3><p>${esc(f[key])}</p>`).join("")+
    `<h3>Evidencias exactas · ${f.evidence.length} filas</h3><p>Abre una referencia para consultar todos los campos originales.</p><div class="reference-list">${f.evidence.map(ref=>`<button class="reference-button" data-event="${ref}">${ref}</button>`).join("")}</div>`);
}
function showEvent(ref) {
  const e=state.data?.events.find(e=>e.ref===ref);if(!e)return;
  dialog(`${ref} · ${e.log_id||"Evento sin ID"}`,`<p>Hoja: <strong>${esc(e.sheet)}</strong> · Fila física: <strong>${e.row}</strong><br>Dominio temporal: ${esc(e.clock)} · Hora UTC: ${esc(e.utc||"No determinada")}${e.duplicate_of?`<br>Duplicado exacto de ${esc(e.duplicate_of)}`:""}</p><dl>${Object.entries(e.raw).map(([k,v])=>`<div class="raw-field"><dt>${esc(k)}</dt><dd>${esc(v)||"—"}</dd></div>`).join("")}</dl>`);
}
async function download(kind,button) {
  if(!state.data)return;
  const label=button.textContent;button.disabled=true;button.textContent="Preparando descarga…";
  try {
    const response=await api(`/api/cases/${state.data.id}/${kind==="pdf"?"report.pdf":"evidence.json"}`);
    const url=URL.createObjectURL(await response.blob()), link=document.createElement("a");
    link.href=url;link.download=`SOC-Lens-${kind==="pdf"?"informe.pdf":"evidencias.json"}`;link.click();
    setTimeout(()=>URL.revokeObjectURL(url),10000);
    notice(kind==="pdf"?"Resumen técnico PDF generado. El JSON conserva todas las evidencias y referencias.":"JSON generado con todas las filas originales y el análisis.");
  } catch(error) {notice(error.message,true);}
  finally {button.disabled=false;button.textContent=label;}
}
document.addEventListener("click",event=>{
  const view=event.target.closest("[data-view]");if(view)showView(view.dataset.view);
  const risk=event.target.closest("[data-risk]");if(risk&&state.data){state.severity=risk.dataset.risk;showView("findings");}
  const finding=event.target.closest("[data-finding]");if(finding)showFinding(finding.dataset.finding);
  const evidence=event.target.closest("[data-event]");if(evidence)showEvent(evidence.dataset.event);
  const bucket=event.target.closest("[data-bucket]");if(bucket){state.hour=state.data.timeline[Number(bucket.dataset.bucket)];state.page=0;showView("events");}
});
document.addEventListener("keydown",event=>{
  if(event.target.matches("[data-bucket]")&&["Enter"," "].includes(event.key)){event.preventDefault();event.target.dispatchEvent(new MouseEvent("click",{bubbles:true}));}
});
$("#close-dialog").addEventListener("click",()=>$("#detail-dialog").close());
$("#file-input").addEventListener("change",e=>upload(e.target.files[0]));
$("#dropzone").addEventListener("dragover",e=>{e.preventDefault();$("#dropzone").classList.add("dragging");});
$("#dropzone").addEventListener("dragleave",()=>$("#dropzone").classList.remove("dragging"));
$("#dropzone").addEventListener("drop",e=>{e.preventDefault();$("#dropzone").classList.remove("dragging");upload(e.dataTransfer.files[0]);});
$("#finding-search").addEventListener("input",e=>{state.findingQuery=e.target.value;renderFindings();});
$("#event-search").addEventListener("input",e=>{state.eventQuery=e.target.value;state.page=0;renderEvents();});
$("#reset-events").addEventListener("click",()=>{state.eventQuery="";state.hour=null;state.page=0;$("#event-search").value="";renderEvents();});
$("#previous-page").addEventListener("click",()=>{state.page--;renderEvents();});
$("#next-page").addEventListener("click",()=>{state.page++;renderEvents();});
$("#download-top").addEventListener("click",e=>download("pdf",e.currentTarget));
$("#download-report").addEventListener("click",e=>download("pdf",e.currentTarget));
$("#download-json").addEventListener("click",e=>download("json",e.currentTarget));
$("#clear-case").addEventListener("click",async()=>{
  try {
    await api(`/api/cases/${state.data.id}`,{method:"DELETE"});state.data=null;
    location.reload();
  } catch(error){notice(error.message,true);}
});
$("#assist-button").addEventListener("click",async()=>{
  const button=$("#assist-button");button.disabled=true;button.textContent="Priorizando en local…";
  try {
    state.data.narrative=await(await api(`/api/cases/${state.data.id}/assistant`,{method:"POST"})).json();
    renderReport();notice("Resumen priorizado con IA local. Se conservaron únicamente frases sustentadas por evidencia.");
  } catch(error){notice(error.message,true);}
  finally{button.disabled=!state.ollama;button.textContent="Priorizar con Ollama";}
});
api("/api/health").then(r=>r.json()).then(health=>{
  state.ollama=health.ollama_available;
  state.ollamaMessage=health.ollama_message;
  if(state.data)renderReport();
}).catch(error=>{notice(error.message,true);});

window.addEventListener("soc-ollama-status",event=>{state.ollama=event.detail.ollama_available;state.ollamaMessage=event.detail.ollama_message;if(state.data)renderReport();});

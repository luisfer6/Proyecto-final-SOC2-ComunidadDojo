// Uso con un runner Playwright compatible. SOC_TEST_XLSX apunta a un archivo local.
// El archivo, las capturas y el PDF no se agregan al repositorio.
import path from "node:path";
import assert from "node:assert/strict";

export default async function run(page, ui) {
  const file=process.env.SOC_TEST_XLSX;
  assert(file, "Define SOC_TEST_XLSX con la ruta del Excel de prueba.");
  const before=await ui.snapshot();
  assert(before.includes("Seleccionar archivo Excel"), before);
  await page.getByLabel("Seleccionar archivo Excel").setInputFiles(file);
  await page.locator("#case-content:not(.hidden)").waitFor({timeout:90000});
  await page.locator("#loading.hidden").waitFor({state:"attached",timeout:90000});
  const stats=await page.locator("#stats").innerText();
  assert(stats.includes("Eventos analizados"));
  if(process.env.SOC_EXPECTED_EVENTS) assert(stats.includes(process.env.SOC_EXPECTED_EVENTS));
  await page.screenshot({path:path.resolve("artifacts/dashboard.png"),fullPage:true});

  await page.locator("#risk-chart [data-risk='Alto']").click();
  await page.getByRole("button",{name:"Revisar evidencia ↗"}).first().click();
  assert(await page.locator("#detail-dialog").isVisible());
  await page.locator("#dialog-content [data-event]").first().click();
  assert(await page.locator(".raw-field").count()>=4);
  const exactEvidence=await page.locator("#dialog-title").innerText();
  await page.getByRole("button",{name:"Cerrar detalle"}).click();

  await page.locator(".nav-item[data-view='events']").click();
  await page.getByLabel("Buscar eventos").fill("vssadmin");
  assert((await page.locator("#events-count").innerText()).startsWith("1 eventos"));
  await page.locator("#events-body [data-event]").first().click();
  assert((await page.locator("#dialog-content").innerText()).includes("delete shadows"));
  await page.getByRole("button",{name:"Cerrar detalle"}).click();
  await page.getByRole("button",{name:"Limpiar filtros"}).click();
  await page.getByRole("button",{name:"Siguiente →"}).click();
  assert((await page.locator("#page-info").innerText()).startsWith("Página 2"));

  await page.locator(".nav-item[data-view='correlations']").click();
  assert(await page.locator(".correlation-card").count()>0);
  await page.locator(".nav-item[data-view='report']").click();
  const downloadPromise=page.waitForEvent("download",{timeout:90000});
  await page.getByRole("button",{name:"↓ Descargar PDF",exact:true}).click();
  const download=await downloadPromise;
  await download.saveAs(path.resolve("artifacts/informe-seguridad.pdf"));
  const jsonPromise=page.waitForEvent("download");
  await page.getByRole("button",{name:"↓ Descargar evidencias JSON"}).click();
  const json=await jsonPromise;
  await json.saveAs(path.resolve("artifacts/analisis-evidencias.json"));
  await page.locator(".nav-item[data-view='overview']").click();
  await page.locator(".chart-bar").first().press("Enter");
  assert((await page.locator("#events-count").innerText()).includes("·"));
  await page.locator(".nav-item[data-view='overview']").click();

  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:path.resolve("artifacts/movil.png"),fullPage:true});
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
  assert(!overflow,"La página desborda horizontalmente en móvil.");
  const after=await ui.snapshot();
  // Delete temporary server-side case; exported deliverables remain on disk.
  await page.getByRole("button",{name:"Eliminar caso"}).click();
  await page.locator("#empty-state:not(.hidden)").waitFor();
  return {stats,exactEvidence,pdf:download.suggestedFilename(),mobileOverflow:overflow,after};
}

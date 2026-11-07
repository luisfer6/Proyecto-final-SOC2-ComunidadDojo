/* The workbook is processed only in this worker's memory. */
let runtime;
let queue = Promise.resolve();
const PYODIDE_URL = 'https://cdn.jsdelivr.net/pyodide/v0.29.3/full/';

async function engine() {
  if (!runtime) runtime = (async () => {
    postMessage({progress:'Preparando el motor en tu navegador. La primera carga descarga las dependencias…'});
    importScripts(PYODIDE_URL + 'pyodide.js');
    const py = await loadPyodide({indexURL:PYODIDE_URL});
    await py.loadPackage(['micropip','scikit-learn','pillow']);
    await py.runPythonAsync("import micropip\nawait micropip.install(['openpyxl==3.1.5', 'defusedxml==0.7.1', 'reportlab==4.4.9'])");
    py.FS.mkdirTree('/soc/app');
    for (const name of ['__init__','analysis','ingest','report','selection']) {
      const response = await fetch(`./python/${name}.py?v=ccc9e18b37d3`);
      if (!response.ok) throw new Error('No se pudo descargar el motor de análisis. Revisa tu conexión y vuelve a cargar la página.');
      py.FS.writeFile(`/soc/app/${name}.py`, await response.text());
    }
    await py.runPythonAsync("import sys, json\nsys.path.insert(0, '/soc')\nfrom app.ingest import read_workbook\nfrom app.analysis import analyze\nfrom app.report import make_pdf\nfrom app.selection import selection_request, selected_narrative\ncase = None");
    return py;
  })();
  return runtime;
}

async function handle({id, action, data}) {
  let py;
  try {
    py = await engine();
    let result;
    if (action === 'analyze') {
      postMessage({progress:'Analizando en tu navegador: validación, reglas y modelo estadístico…'});
      py.FS.writeFile('/upload.data', new Uint8Array(data.bytes));
      py.globals.set('filename', data.filename);
      py.globals.set('offset_json', JSON.stringify(data.offset));
      py.globals.set('case_id', data.caseId);
      try {
        result = JSON.parse(await py.runPythonAsync("with open('/upload.data', 'rb') as workbook:\n    events, metadata = read_workbook(workbook.read(), filename, json.loads(offset_json))\ncandidate = analyze(events, metadata)\ncandidate['id'] = case_id\ncase = candidate\ndel candidate, events, metadata\njson.dumps(case, ensure_ascii=False)"));
      } finally { py.FS.unlink('/upload.data'); }
    } else if (action === 'restore') {
      py.globals.set('case_json', JSON.stringify(data.case));
      await py.runPythonAsync('case = json.loads(case_json)\ndel case_json');
      result = {restored:true};
    } else if (action === 'delete') {
      await py.runPythonAsync('case = None\nimport gc\ngc.collect()');
      result = {deleted:true};
    } else if (action === 'pdf') {
      const proxy = await py.runPythonAsync('make_pdf(case)');
      const bytes = proxy.toJs();
      proxy.destroy();
      postMessage({id, result:bytes}, [bytes.buffer]);
      return;
    } else if (action === 'json') {
      result = await py.runPythonAsync('json.dumps(case, ensure_ascii=False, indent=2)');
    } else if (action === 'request') {
      py.globals.set('model', data.model);
      result = JSON.parse(await py.runPythonAsync('json.dumps(selection_request(case["findings"], model))'));
    } else if (action === 'selection') {
      py.globals.set('payload_json', JSON.stringify(data.payload));
      py.globals.set('model', data.model);
      result = JSON.parse(await py.runPythonAsync('narrative = selected_narrative(case, json.loads(payload_json), model)\ncase["narrative"] = narrative\njson.dumps(narrative, ensure_ascii=False)'));
    } else throw new Error('Operación no admitida.');
    postMessage({id, result});
  } catch (error) {
    const message = String(error.message || error).trim().split('\n').filter(Boolean).at(-1).replace(/^ValueError: /, '');
    postMessage({id, error:message, initFailed:!py});
  }
}
self.onmessage = event => { queue = queue.then(() => handle(event.data)); };

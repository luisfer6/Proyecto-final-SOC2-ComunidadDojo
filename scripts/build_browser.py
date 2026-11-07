"""Genera la web estática con el Excel predeterminado del proyecto."""
from pathlib import Path
import shutil
import json
import sys
import argparse
import hashlib

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.ingest import read_workbook
from app.analysis import analyze
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT / 'docs', help='Carpeta publicable (por defecto: docs)')
args = parser.parse_args()
OUT = args.output.resolve()
OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'python').mkdir(exist_ok=True)
for name in ('__init__', 'ingest', 'analysis', 'report', 'selection'):
    shutil.copyfile(ROOT / 'app' / f'{name}.py', OUT / 'python' / f'{name}.py')
for name in ('browser.js', 'browser-worker.js', 'default-case.js', 'guia-ollama.html'):
    shutil.copyfile(ROOT / 'web' / name, OUT / name)
shutil.copyfile(ROOT / 'static/styles.css', OUT / 'styles.css')
script = (ROOT / 'static/app.js').read_text(encoding='utf-8')
script = script.replace('async function api(url, options={}) {', 'async function api(url, options={}) {\n  if(window.socBrowser) return window.socBrowser.api(url,options);')
script = script.replace('connected?"Motor local activo":"Motor no disponible"', '"Análisis en tu navegador"')
script += '''\nwindow.addEventListener("soc-ollama-status",event=>{state.ollama=event.detail.ollama_available;state.ollamaMessage=event.detail.ollama_message;if(state.data)renderReport();});\n'''
(OUT / 'app.js').write_text(script,encoding='utf-8')
html = (ROOT / 'static/index.html').read_text(encoding='utf-8')
html = html.replace('href="/static/styles.css"', 'href="./styles.css"').replace('src="/static/app.js"','src="./app.js"').replace('href="/"','href="./"')
html = html.replace('<script src="./app.js"', '<script src="./browser.js" defer></script>\n  <script src="./app.js"')
html = html.replace('</head>', '  <script src="./default-case.js" defer></script>\n</head>')
start = html.index('<div id="dropzone"')
end = html.index('<div class="upload-options">', start)
html = html[:start] + '''<div id="dropzone" class="dropzone">
          <button id="choose-excel" class="upload-choose" type="button" aria-label="Elegir archivo Excel o CSV">
            <span class="upload-icon" aria-hidden="true">↥</span>
            <span><strong>Arrastra aquí el archivo .xlsx o .csv</strong> o haz clic para seleccionarlo</span>
            <small>XLSX / CSV · Hasta 10 MB · Todas las hojas compatibles · Procesamiento en tu navegador</small>
          </button>
          <input id="file-input" type="file" accept=".xlsx,.csv" aria-label="Seleccionar archivo Excel o CSV" hidden>
          <button id="restore-default" class="button secondary" type="button">Usar Excel del reto</button>
        </div>
        ''' + html[end:]
html = html.replace('<section id="upload-section"', '''<section class="dataset-intro panel"><div><span class="eyebrow">LABORATORIO DE INVESTIGACIÓN</span><h2>Explora. Investiga. Documenta.</h2><p>Un caso listo para explorar y tus propios datos cuando los necesites.</p></div><span class="pill local">100% estático · Sin servidor de análisis</span></section>
      <section id="upload-section"''')
html = html.replace('<div class="upload-options">', '''<div class="dataset-actions"><span id="dataset-status" class="dataset-badge">EXCEL DEL RETO DISPONIBLE</span><a href="./data/SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx" download class="text-button">↓ Descargar Excel incluido</a></div><details class="case-settings" open><summary>Datos del caso <span>Se incluyen en el PDF y JSON</span></summary><div class="case-fields"><label for="case-analyst">Analista<input id="case-analyst" maxlength="120" value="Analista SOC L2" autocomplete="off"></label><label for="case-client">Cliente<input id="case-client" maxlength="120" value="Cliente corporativo (CORP)" autocomplete="off"></label><label for="case-company">Consultora<input id="case-company" maxlength="120" value="Comunidad Dojo" autocomplete="off"></label><label for="case-reference">Referencia<input id="case-reference" maxlength="120" placeholder="Ej. SOC-2026-001" autocomplete="off"></label></div><p class="fine-print">Los cambios se conservan durante esta sesión. Al recargar puedes volver a elegir el Excel del reto o un archivo propio.</p></details><div class="upload-options">''')
html = html.replace('<h3>Resumen ejecutivo</h3>', '<p id="case-context-preview" class="fine-print"></p><h3>Resumen ejecutivo</h3>')
html = html.replace('Comprobando motor local…','Análisis en tu navegador').replace('data-status="checking"','data-status="online"')
html = html.replace('Tu evidencia, en local','Tu evidencia, en tu navegador').replace('Los registros se analizan en este equipo. Sin envíos a servicios externos.', 'El archivo se procesa en esta pestaña. Sus datos no se envían al alojamiento.')
html = html.replace('Los casos permanecen en memoria durante una hora o hasta que los elimines. Al reiniciar el servidor se borran.', 'El caso permanece en la memoria de esta pestaña. Al recargarla o cerrarla se borra. Guarda tu PDF y JSON antes de salir.')
html = html.replace('<section id="empty-state"', '<p class="fine-print">Pulsa «Usar Excel del reto» para cargar el archivo incluido. Para analizar otro Excel o CSV o generar un PDF se descarga el motor y sus dependencias. El archivo se procesa en esta pestaña. <a href="./guia-ollama.html" target="_blank" rel="noopener">Cómo conectar Ollama local</a>.</p>\n      <section id="empty-state"')
html = html.replace('<button id="assist-button"', '''<div class="ollama-connect"><label for="ollama-model">Modelo local</label><input id="ollama-model" value="qwen3:4b" maxlength="120" spellcheck="false"><button id="connect-ollama" class="button secondary">Conectar Ollama en este equipo</button><small id="ollama-connection-status" role="status">Cada visitante utiliza su propia instalación de Ollama. Se envían sólo IDs, regla, criticidad y cantidad de evidencias.</small><p><a href="./guia-ollama.html" target="_blank" rel="noopener">Guía de conexión</a></p></div><button id="assist-button"''')
(OUT / 'index.html').write_text(html,encoding='utf-8')
data_dir = OUT / 'data'
data_dir.mkdir(exist_ok=True)
workbook = ROOT / 'web' / 'data' / 'SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx'
shutil.copyfile(workbook, data_dir / workbook.name)
case = analyze(*read_workbook(workbook.read_bytes(), workbook.name))
case['id'] = 'bundled-case'
(data_dir / 'default-case.json').write_text(json.dumps(case, ensure_ascii=False), encoding='utf-8')
(OUT / '.nojekyll').touch()
with (OUT / 'styles.css').open('a', encoding='utf-8') as css:
    css.write((ROOT / 'web' / 'browser.css').read_text(encoding='utf-8'))
with (OUT / 'styles.css').open('a',encoding='utf-8') as css:
    css.write('\n.ollama-connect{margin:18px 0}.ollama-connect label{display:block;font-size:1rem}.ollama-connect input{width:100%;padding:10px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--ink);margin:8px 0 12px}\n')
# Different datasets and application versions must not reuse a previous Pages cache.
revision = hashlib.sha256((data_dir / 'default-case.json').read_bytes()).hexdigest()[:12]
engine_revision = hashlib.sha256(b''.join((OUT / 'python' / f'{name}.py').read_bytes() for name in ('__init__', 'ingest', 'analysis', 'report', 'selection')) + (OUT / 'browser-worker.js').read_bytes()).hexdigest()[:12]
worker_path = OUT / 'browser-worker.js'
worker_path.write_text(worker_path.read_text(encoding='utf-8').replace(
    './python/${name}.py', f'./python/${{name}}.py?v={engine_revision}'), encoding='utf-8')
browser_path = OUT / 'browser.js'
browser_path.write_text(browser_path.read_text(encoding='utf-8').replace(
    './data/default-case.json', f'./data/default-case.json?v={revision}').replace(
    './browser-worker.js', f'./browser-worker.js?v={engine_revision}'), encoding='utf-8')
for asset in ('styles.css', 'browser.js', 'app.js', 'default-case.js'):
    revision = hashlib.sha256((OUT / asset).read_bytes()).hexdigest()[:12]
    html = html.replace(f'"./{asset}"', f'"./{asset}?v={revision}"')
(OUT / 'index.html').write_text(html, encoding='utf-8')
print(f'Edición navegador generada en {OUT}')

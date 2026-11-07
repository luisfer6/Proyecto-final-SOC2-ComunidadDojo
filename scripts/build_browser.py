"""Genera la web estática e incluye únicamente el ejemplo sintético explícito."""
from pathlib import Path
import shutil
import json
import sys
import argparse

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
html = html.replace('Comienza con tu evidencia', 'Tu Excel, tu investigación').replace('Arrastra aquí tu exportación SIEM o selecciona un archivo.', 'Ya tienes un ejemplo cargado. Arrastra otro Excel para reemplazarlo.').replace('Seleccionar Excel<input', 'Cambiar Excel<input')
html = html.replace('<section id="upload-section"', '''<section class="dataset-intro panel"><div><span class="eyebrow">LABORATORIO DE INVESTIGACIÓN</span><h2>Explora. Investiga. Documenta.</h2><p>Un caso listo para explorar y tus propios datos cuando los necesites.</p></div><span class="pill local">100% estático · Sin servidor de análisis</span></section>
      <section id="upload-section"''')
html = html.replace('<div class="upload-options">', '''<div class="dataset-actions"><span id="dataset-status" class="dataset-badge">EJEMPLO SINTÉTICO</span><a href="./data/demo-sintetica.xlsx" download class="text-button">↓ Descargar Excel incluido</a><button id="restore-default" class="button secondary" type="button">↺ Restaurar ejemplo</button></div><details class="case-settings" open><summary>Datos del caso <span>Se incluyen en el PDF y JSON</span></summary><div class="case-fields"><label for="case-analyst">Analista<input id="case-analyst" maxlength="120" value="Analista SOC L2" autocomplete="off"></label><label for="case-client">Cliente<input id="case-client" maxlength="120" value="Cliente corporativo (CORP)" autocomplete="off"></label><label for="case-company">Consultora<input id="case-company" maxlength="120" value="Comunidad Dojo" autocomplete="off"></label><label for="case-reference">Referencia<input id="case-reference" maxlength="120" placeholder="Ej. SOC-2026-001" autocomplete="off"></label></div><p class="fine-print">Los cambios se conservan durante esta sesión. Al recargar se vuelve al ejemplo incluido.</p></details><div class="upload-options">''')
html = html.replace('<h3>Resumen ejecutivo</h3>', '<p id="case-context-preview" class="fine-print"></p><h3>Resumen ejecutivo</h3>')
html = html.replace('Comprobando motor local…','Análisis en tu navegador').replace('data-status="checking"','data-status="online"')
html = html.replace('Tu evidencia, en local','Tu evidencia, en tu navegador').replace('Los registros se analizan en este equipo. Sin envíos a servicios externos.', 'El Excel se procesa en esta pestaña. Sus datos no se envían al alojamiento.')
html = html.replace('Los casos permanecen en memoria durante una hora o hasta que los elimines. Al reiniciar el servidor se borran.', 'El caso permanece en la memoria de esta pestaña. Al recargarla o cerrarla se borra. Guarda tu PDF y JSON antes de salir.')
html = html.replace('<section id="empty-state"', '<p class="fine-print">El ejemplo se abre al instante. Para analizar otro Excel o generar un PDF se descarga el motor y sus dependencias. El Excel se procesa en esta pestaña. <a href="./guia-ollama.html" target="_blank" rel="noopener">Cómo conectar Ollama local</a>.</p>\n      <section id="empty-state"')
html = html.replace('<button id="assist-button"', '''<div class="ollama-connect"><label for="ollama-model">Modelo local</label><input id="ollama-model" value="qwen3:4b" maxlength="120" spellcheck="false"><button id="connect-ollama" class="button secondary">Conectar Ollama en este equipo</button><small id="ollama-connection-status" role="status">Cada visitante utiliza su propia instalación de Ollama. Se envían sólo IDs, regla, criticidad y cantidad de evidencias.</small><p><a href="./guia-ollama.html" target="_blank" rel="noopener">Guía de conexión</a></p></div><button id="assist-button"''')
(OUT / 'index.html').write_text(html,encoding='utf-8')
data_dir = OUT / 'data'
data_dir.mkdir(exist_ok=True)
demo = ROOT / 'artifacts' / 'demo-sintetica.xlsx'
if not demo.exists():
    from scripts.generate_demo import main as generate_demo
    generate_demo()
shutil.copyfile(demo, data_dir / demo.name)
case = analyze(*read_workbook(demo.read_bytes(), demo.name))
case['id'] = 'bundled-demo'
(data_dir / 'default-case.json').write_text(json.dumps(case, ensure_ascii=False), encoding='utf-8')
(OUT / '.nojekyll').touch()
with (OUT / 'styles.css').open('a', encoding='utf-8') as css:
    css.write((ROOT / 'web' / 'browser.css').read_text(encoding='utf-8'))
with (OUT / 'styles.css').open('a',encoding='utf-8') as css:
    css.write('\n.ollama-connect{margin:18px 0}.ollama-connect label{display:block;font-size:1rem}.ollama-connect input{width:100%;padding:10px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--ink);margin:8px 0 12px}\n')
print(f'Edición navegador generada en {OUT}')

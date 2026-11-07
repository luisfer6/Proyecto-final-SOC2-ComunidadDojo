# Edición estática de SOC Lens

Ejecuta `.venv\Scripts\python.exe scripts\build_browser.py` desde la raíz.
La web publicable queda en `docs/` y puede alojarse
en un servicio estático, incluido GitHub Pages. Sirve esa carpeta por HTTP;
abrir `index.html` directamente con `file://` no permite cargar sus recursos.

Al abrir, muestra el análisis precalculado del Excel versionado en
`web/data/SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`. Ese archivo y su
análisis se publican por petición del autor. Para cambiarlo permanentemente,
reemplaza el archivo fuente y vuelve a generar y publicar la web.
GitHub Actions usa el mismo Excel; no genera ni incluye el demo.

El visitante puede cambiar el archivo con **Cambiar Excel** o arrastrarlo,
descargar el original y volver al caso inicial con **Restaurar Excel del proyecto**.
Los archivos del visitante se procesan en memoria y no cambian el Excel
predeterminado de otros visitantes. Al recargar vuelve el Excel del proyecto.

Los campos de analista, cliente, consultora y referencia se incluyen en
las exportaciones PDF y JSON. El caso incluido se visualiza sin cargar Python;
para analizar otros Excel o generar un PDF se descargan Pyodide y sus
dependencias. Se requiere conexión en esa primera descarga. Ollama es opcional.

Cada push a `main` genera y publica `docs/` mediante `.github/workflows/pages.yml`.
La carpeta también está versionada para poder publicarla desde una rama.
`index.html` de la raíz redirige a `docs/` si Pages todavía sirve la raíz.
Para la publicación alternativa de Sites, usa
`python scripts/build_browser.py --output sites/soc-lens-browser/dist`.

# Guion de demostración · Máximo 5 minutos

El video lo graba el autor. Preparación: iniciar `iniciar.cmd`, disponer del
Excel autorizado y abrir `http://127.0.0.1:8000`. No mostrar secretos ni publicar
archivos de investigación en el repositorio.

| Tiempo | Pantalla y explicación |
|---|---|
| 0:00–0:35 | Presentar SOC Lens: analizar Excel, detectar señales y producir un informe trazable. Explicar que alerta, hipótesis e incidente son conceptos distintos. |
| 0:35–1:05 | Mostrar arquitectura en README: FastAPI, openpyxl, reglas, Isolation Forest, ReportLab y navegador sin CDN. Indicar procesamiento local. |
| 1:05–1:40 | Cargar Excel. Explicar la zona «no declarada», cifras de eventos únicos, equipos, criticidades y notas de cobertura. |
| 1:40–2:30 | Filtrar un hallazgo crítico/alto. Leer observación, alternativa y validación. Abrir una referencia hoja/fila y mostrar el comando original sin ejecutarlo. |
| 2:30–3:10 | Buscar un evento y seleccionar una barra de la cronología. Mostrar correlaciones: claves, intervalo y por qué no confirman una cadena causal. |
| 3:10–3:40 | Mostrar IA local: variables, score relativo, semilla reproducible. Si Ollama está disponible, priorizar el resumen; explicar que sólo selecciona IDs y no agrega hechos. |
| 3:40–4:35 | Generar y abrir PDF: resumen, hallazgos, justificación, impacto condicionado, plan y anexo de evidencia exacta. Mostrar SHA-256 y descarga JSON. |
| 4:35–5:00 | Mostrar pruebas y estructura del código. Cerrar con limitaciones y enlace al repositorio publicado sin skills ni Excel. |

Si usas `artifacts/demo-sintetica.xlsx`, identifica expresamente los datos como
sintéticos. Una ejecución de comandos aparece sólo como texto de un registro;
la aplicación no reproduce ataques.

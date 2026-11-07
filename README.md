# SOC Lens

Aplicación web para investigar exportaciones SIEM en Excel o CSV. Detecta patrones
de autenticación, privilegios, comandos, administración remota, actividad web,
persistencia y transferencias; conserva la evidencia de cada hallazgo y genera
un informe PDF con resumen ejecutivo y anexo técnico.

**Un hallazgo es una señal para investigar. La aplicación no confirma por sí sola
un incidente ni atribuye actividad a un actor.** Las correlaciones se presentan
como hipótesis con claves, ventana y limitaciones explícitas.

## Abrir desde GitHub Pages

**[Abrir SOC Lens](https://luisfer6.github.io/Proyecto-final-SOC2-ComunidadDojo/)**

Pulsa **Usar Excel del reto** para cargar
`SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx`, incluido en el repositorio.
También puedes arrastrar un Excel o CSV propio o hacer clic en la zona de carga. Puedes editar
analista, cliente, consultora y referencia y descargar un resumen técnico PDF de 4 páginas para el reto, además del JSON
con toda la evidencia. El resumen contiene alcance, catálogo de hallazgos, tres
prioridades técnicas, cronología, observables y plan de acción.
Los archivos elegidos se procesan en la memoria de tu navegador; no se suben a
GitHub. Al recargar puedes elegir de nuevo el Excel del reto o uno propio. No necesitas instalar Python ni iniciar
un servidor. El motor de análisis se descarga desde CDN cuando se necesita;
la primera carga de otro Excel o del PDF requiere conexión y puede tardar.
Ollama es opcional y utiliza la instalación de cada visitante.

Cada actualización de `main` ejecuta `.github/workflows/pages.yml`: verifica el
análisis, genera la web y publica en Pages. En **Settings → Pages → Source** debe
estar seleccionado **GitHub Actions**. El estado se consulta en la pestaña
**Actions**, workflow **Publicar SOC Lens en GitHub Pages**.

Para regenerar los archivos publicables localmente:

```powershell
.\.venv\Scripts\python.exe scripts/build_browser.py
```

La salida es `docs/`, con rutas relativas compatibles con la URL del repositorio.
El generador utiliza el archivo versionado en `web/data/`. Para cambiar
permanentemente el Excel incluido, reemplázalo allí y vuelve a publicar. El Excel que el
visitante selecciona sólo reemplaza su caso en esa pestaña.

## Estructura del proyecto

| Carpeta | Contenido |
|---|---|
| `web/` | Adaptador, worker y controles de la edición de navegador |
| `static/` | Interfaz compartida con la edición local |
| `app/` | Reglas, lectura del Excel, PDF y API local opcional |
| `scripts/` | Generación de la web publicable y utilidades de prueba |
| `docs/` | Web estática generada y documentación |
| `tests/` | Pruebas del análisis y exportaciones |
| `.github/workflows/` | Verificación y publicación automática |

`sites/` contiene una publicación alternativa de desarrollo y se excluye del
repositorio. GitHub Pages utiliza la salida de `docs/`.

## Edición local opcional: inicio rápido en Windows

Requisito: Python 3.14 y acceso a internet sólo para instalar dependencias.
El entorno de desarrollo se verificó con CPython 3.14 en Windows.

1. Ejecuta `iniciar.cmd` desde el explorador o la terminal.
2. Abre **http://127.0.0.1:8000**.
3. Selecciona el Excel, conserva «zona no declarada» salvo que conozcas el desfase.
4. Revisa el dashboard, los hallazgos, las filas originales y las correlaciones.
5. En «Informe técnico», descarga PDF y JSON.

El primer inicio crea `.venv` e instala las versiones fijadas. Los siguientes
arranques reutilizan el entorno. No es necesario Node, Sentinel, una cuenta cloud
ni una clave de API. `Ctrl+C` detiene el servidor.

Instalación manual (PowerShell, sin cambiar su política de ejecución):

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

En Linux/macOS, usa `.venv/bin/python`. Esos sistemas no fueron validados en esta
entrega; `requirements.txt` define los rangos y `requirements.lock.txt` las versiones
del entorno probado.

## Excel y CSV admitidos

Se admiten `.xlsx` y `.csv`. Los CSV deben usar UTF-8 (con o sin BOM) o UTF-16
con BOM y separadores de coma, punto y coma, tabulador o barra vertical.
Usan las mismas cabeceras y límites de filas, columnas y celdas que Excel;
se conservan los valores originales como texto, incluidos comandos que empiecen por `=`.
El límite de tamaño para CSV es 10 MB.


Primera fila: cabeceras únicas. Se procesan todas las hojas compatibles; las hojas
omitidas se declaran en calidad/cobertura. Máximos: 10 MB comprimidos, 60 MB
descomprimidos, 30 000 eventos, 60 columnas, 8000 caracteres/celda y 500 hallazgos.
Si se excede el límite de hallazgos se rechaza el análisis completo, sin informe parcial.

| Campo | Cabecera recomendada | Uso |
|---|---|---|
| Fecha **obligatoria** | `Timestamp` | ISO 8601, `YYYY-MM-DD HH:mm:ss` o celda fecha de Excel |
| Equipo **obligatorio** | `Hostname` | Host que registra el evento |
| ID de evento **obligatorio** | `Event_ID` | Código Windows o identificador de fuente |
| Fuente **obligatoria** | `Log_Source` | Security, System, PowerShell, Sysmon, Proxy, IIS o Firewall |
| ID de registro | `Log_ID` | ID de origen, no necesariamente único |
| Identidad | `User` | Cuenta registrada |
| IP de origen | `Source_IP` | No se resuelven dominios ni se consulta reputación |
| Destino | `Destination` | Texto original |
| Descripción | `Event_Description` | Descripción original |
| Comando | `Process_CommandLine` | Nunca se ejecuta |
| Resultado | `Result` | Valor del origen, sin inferir resultado de comandos |
| Severidad del SIEM | `Severity` | No sustituye la criticidad calculada |

Se admiten alias comunes, definidos en `app/ingest.py`. Esquemas no reconocidos
deben renombrarse en una copia de la exportación; el programa no adivina mappings.
Las fórmulas se rechazan: exporta valores. No se normalizan hosts similares.
Una fila sin campos necesarios para una regla no se usa para inventar entidades.

Referencias `S1-R58`: hoja 1, fila física 58 del Excel. Cada fila conserva los
campos originales y su hash; el archivo completo tiene SHA-256. Duplicados exactos
se conservan pero se excluyen de detección. Fechas sin zona no se convierten a UTC:
se agrupan por hoja bajo el supuesto declarado de relojes comparables. Una zona
manual es un **desfase fijo**, no infiere cambios de horario de verano.

## IA y rigor analítico

- **IA disponible por defecto:** Isolation Forest de scikit-learn, entrenado en
  cada archivo, con semilla 42. Variables: frecuencia de proveedor/evento,
  host, cuenta e IP; longitud de comando; bytes salientes y hora cíclica.
  Requiere 30 eventos únicos. Muestra hasta 10 scores superiores a 0.65.
  Son prioridades de revisión, no probabilidades de ataque.
- **Redacción automática verificable:** texto ensamblado de recuentos, reglas,
  observaciones y referencias reales. Incluye alternativas benignas, impacto
  condicionado, validaciones, mitigación propuesta y limitaciones.
- **Ollama opcional:** un modelo local puede elegir hasta 5 hallazgos para destacar.
  No redacta afirmaciones libres: el backend admite únicamente IDs existentes
  sin repetición y utiliza frases verificadas. Los logs originales no entran al
  prompt; se pasan IDs de hallazgo, regla, criticidad y cantidad de evidencias.

Si ya tienes Ollama y un modelo descargado, inicia Ollama y establece su nombre
antes de arrancar la aplicación:

```powershell
$env:OLLAMA_MODEL = "nombre-de-tu-modelo-local"
.\iniciar.cmd
```

El único destino permitido es `http://127.0.0.1:11434/api/chat`; no es configurable
desde el navegador. El botón solicita explícitamente la selección. Si Ollama
no está disponible o devuelve un esquema inválido, conserva el informe previo.
La entrega no instala ni descarga un modelo. La vía Ollama requiere validación
con un runtime real; el validador y los fallos de configuración tienen pruebas.

## Arquitectura y reglas

En GitHub Pages, el navegador ejecuta las reglas Python mediante Pyodide en un
Web Worker. El archivo incluido está precalculado para mostrar el dashboard de inmediato.
PDF, cambios de Excel y selección opcional con Ollama utilizan el mismo motor.
El esquema siguiente corresponde a la edición local opcional:

```text
Navegador: HTML / CSS / JavaScript (sin CDN)
    │ XLSX local
    ▼
FastAPI → openpyxl + límites de entrada
    │ filas originales / reloj / SHA-256
    ▼
Reglas explicables + Isolation Forest
    │ hallazgos / hipótesis / alternativas / evidencia
    ├── Dashboard, explorador y correlaciones
    ├── Redacción factual → ReportLab → PDF
    ├── JSON completo descargable
    └── Ollama local opcional → selección validada → resumen
```

Consulta [reglas y alcance](docs/reglas.md), [guion del video](docs/video.md) y
[publicación](docs/publicacion.md). `app/analysis.py` contiene reglas, modelo y
correlaciones; `app/ingest.py`, normalización; `app/report.py`, PDF;
`app/assistant.py`, selección con LLM; `app/main.py`, API y ciclo de casos.

## Privacidad y uso local

En Pages se publica el Excel del proyecto y su análisis, con autorización del
autor. Ambos son accesibles públicamente. Los Excel del visitante se
procesan en la memoria de su pestaña y no modifican el repositorio. El motor y
sus dependencias se descargan de CDN; al usar Ollama se envía la selección de
hallazgos a la instalación local que el visitante conecta explícitamente.

La aplicación escucha en loopback. No tiene autenticación multiusuario: no debe
exponerse directamente a una red. Host y origen se validan, las respuestas tienen
`no-store` y CSP, los logs se renderizan como texto. Las cargas multipart pueden
utilizar almacenamiento temporal del sistema, cerrado al finalizar la petición.
Los análisis se guardan sólo en memoria, hasta 4 casos por proceso, durante una
hora; limpieza cada minuto. «Eliminar caso» y detener el servidor los retiran.
Las descargas PDF/JSON permanecen donde el usuario las guarde.

El código no ejecuta comandos de los registros, no enriquece observables en
terceros y no realiza contención. Los rangos de documentación se identifican como
tales. Los hallazgos no dependen de que el SIEM haya marcado un evento como alto.
La cobertura es heurística: no es un motor universal ni un SIEM de producción.

## Verificación y demostración reproducible

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/generate_demo.py
```

Carga `artifacts/demo-sintetica.xlsx`: todos sus eventos son **sintéticos** y no
se ejecutan las líneas de comando incluidas. Las pruebas cubren ventanas móviles,
fuentes incorrectas, falsos positivos, claves de correlación, duplicados, zonas,
fórmulas, inyección de texto, exfiltración candidata, IA reproducible, validación
LLM, exportación PDF/JSON, vencimiento y eliminación de casos.

`scripts/browser_smoke.mjs` verifica con un runner Playwright compatible la carga,
el filtrado, el detalle, las referencias, la paginación, el PDF, el JSON, los
gráficos con teclado, la vista móvil y la eliminación. Requiere `SOC_TEST_XLSX`;
las capturas y entregables se guardan en `artifacts/`.

## Entrega

El video, de hasta cinco minutos, lo graba el autor. El PDF se genera desde la
aplicación; los artefactos de una investigación nunca se publican por defecto.
`.gitignore` excluye `.devin/` completo, Excel, PDF, artefactos, secretos y entornos;
las excepciones de Excel son las copias autorizadas del archivo del proyecto en
`web/data/` y `docs/data/`, publicadas intencionadamente para la web.
Las skills y el material de los cursos no forman parte del código publicable.

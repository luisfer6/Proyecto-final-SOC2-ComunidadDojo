# Publicación en GitHub Pages

La aplicación estática se abre en:

https://luisfer6.github.io/Proyecto-final-SOC2-ComunidadDojo/

El workflow `.github/workflows/pages.yml` verifica el código, genera el Excel
sintético y la edición de navegador y publica únicamente `docs/`. En Settings →
Pages → Source, usa **GitHub Actions**. Se ejecuta al subir a `main` o con
**Run workflow** en Actions. No se instala un backend en GitHub Pages.

Para reconstruir localmente, ejecuta `python scripts/build_browser.py` con las
dependencias de `requirements.lock.txt` instaladas. Para previsualizar:
`python -m http.server 8000 --directory docs`, y abre http://localhost:8000.

Como alternativa sin workflow, Pages puede publicar la rama `main`, carpeta
`/docs`. La raíz también tiene un enlace de entrada a esa carpeta.

El único Excel publicable es `docs/data/demo-sintetica.xlsx`, creado por
`scripts/generate_demo.py`; `docs/data/default-case.json` contiene su análisis
sintético. Los archivos de los visitantes se procesan en su navegador y nunca
se guardan en el repositorio.

## Contenido excluido

El contenido publicable es el código, documentación, pruebas y scripts de
demostración. `.devin/` se excluye completo para no copiar las skills, las
transcripciones de cursos, el requerimiento local ni el Excel aportado.
`artifacts/` sólo publica `.gitkeep`; los PDF, JSON, capturas y XLSX de casos
reales permanecen locales. No publicar el JSON de un caso real: contiene
registros originales. La excepción sintética de la web se describe arriba.

Antes de subir:

```powershell
git status --short
git ls-files
git check-ignore .devin/requerimientos/REQ-0001-SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx
```

Una vez autenticado con GitHub CLI en la cuenta **luisfer6**, un repositorio
privado permite revisar la entrega antes de decidir su visibilidad:

```powershell
gh auth login
gh repo create luisfer6/Proyecto-final-SOC2-ComunidadDojo --private --source . --remote origin --push
```

Si el repositorio ya existe, no crear otro ni reemplazar su historial; añadir su
remote y revisar el historial antes de integrar. La creación/subida requiere una
sesión GitHub autenticada. Un remote local o una URL propuesta no acreditan que
el proyecto haya sido publicado.

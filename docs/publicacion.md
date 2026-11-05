# Publicación del código

El contenido publicable es el código, documentación, pruebas y scripts de
demostración. `.devin/` se excluye completo para no copiar las skills, las
transcripciones de cursos, el requerimiento local ni el Excel aportado.
`artifacts/` sólo publica `.gitkeep`; los PDF, JSON, capturas y XLSX permanecen
locales. No publicar el JSON del caso: contiene registros originales.

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

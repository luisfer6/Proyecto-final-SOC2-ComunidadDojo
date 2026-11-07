"""PDF reproducible desde el mismo resultado que alimenta el dashboard, con formato SOC L2."""
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def register_font():
    candidates = [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                  Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
                  Path(__import__("reportlab").__file__).parent / "fonts" / "Vera.ttf"]
    for path in candidates:
        if path.exists():
            if "Evidence" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("Evidence", str(path)))
            return "Evidence"
    return "Helvetica"


FONT = register_font()

# Paleta corporativa SOC
COLOR_HEADER_BG = colors.HexColor("#1F3864")
COLOR_HEADER_TEXT = colors.white
COLOR_ROW_ALT = colors.HexColor("#F2F2F2")
COLOR_BORDER = colors.HexColor("#BFBFBF")

COLOR_CRITICO = colors.HexColor("#C00000")
COLOR_ALTO = colors.HexColor("#ED7D31")
COLOR_MEDIO = colors.HexColor("#FFC000")
COLOR_BAJO = colors.HexColor("#70AD47")


def get_severity_color(severity):
    s = str(severity).lower()
    if "crítico" in s or "critical" in s: return COLOR_CRITICO
    if "alto" in s or "high" in s: return COLOR_ALTO
    if "medio" in s or "medium" in s: return COLOR_MEDIO
    if "bajo" in s or "low" in s: return COLOR_BAJO
    return colors.HexColor("#54647e")


def make_pdf(result):
    output = BytesIO()
    styles = getSampleStyleSheet()

    for name in ("Normal", "Title", "Heading1", "Heading2", "Heading3"):
        styles[name].fontName = FONT
        if name.startswith("Heading"):
            styles[name].textColor = COLOR_HEADER_BG
            styles[name].keepWithNext = True

    styles["Normal"].fontSize = 9
    styles["Normal"].leading = 12
    styles["Normal"].spaceAfter = 6

    styles.add(ParagraphStyle("CoverTitle", fontName=FONT, fontSize=16, leading=20, textColor=COLOR_HEADER_BG, spaceAfter=15, keepWithNext=True))
    styles.add(ParagraphStyle("CoverSubtitle", fontName=FONT, fontSize=12, leading=15, textColor=colors.gray, spaceAfter=20, keepWithNext=True))
    styles.add(ParagraphStyle("TableText", fontName=FONT, fontSize=8, leading=10, wordWrap="CJK"))
    styles.add(ParagraphStyle("TableTextBold", fontName=FONT, fontSize=8, leading=10, wordWrap="CJK", textColor=colors.black))

    story = []

    def p(value, style="Normal"):
        if value is None: value = ""
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "\ufffd", str(value))
        return Paragraph(escape(value).replace("\n", "<br/>").replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>"), styles[style])

    def add(value, style="Normal"):
        story.append(p(value, style))

    def make_table(rows, widths, is_header_dark=True):
        cells = []
        for i, row in enumerate(rows):
            cell_row = []
            for cell in row:
                if isinstance(cell, Paragraph):
                    cell_row.append(cell)
                else:
                    style = "TableTextBold" if (i == 0 and is_header_dark) else "TableText"
                    # Forzar negrita si la celda incluye HTML bold manual en la primera columna o filas clave
                    if "<b>" in str(cell): style = "TableTextBold"
                    cell_row.append(p(cell, style))
            cells.append(cell_row)

        t = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")

        ts = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("BOX", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]

        if is_header_dark:
            ts.extend([
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, 0), COLOR_HEADER_TEXT),
            ])
            # Forzar color de texto blanco en la cabecera para los Párrafos
            for col in range(len(widths)):
                cells[0][col].style.textColor = colors.white

        # Alternar colores de fila
        for i in range(1, len(rows)):
            if i % 2 == 0:
                ts.append(("BACKGROUND", (0, i), (-1, i), COLOR_ROW_ALT))

        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Spacer(1, 8))

    m = result["metadata"]
    context = m.get("case_context", {})

    # ------------------ PORTADA / ENCABEZADO ------------------
    add("BOOTCAMP ANALISTA SOC NIVEL 2", "CoverSubtitle")
    add("Informe técnico de investigación de incidentes de seguridad", "CoverTitle")

    meta_table = [
        ["Cliente", context.get("client") or "Cliente corporativo (CORP)"],
        ["Elaborado por", context.get("analyst") or "Analista SOC L2 (Generado por Motor)"],
        ["Consultora", context.get("company") or "No indicada"],
        ["Referencia", context.get("reference") or "No indicada"],
        ["Archivo analizado", m['filename']],
        ["Periodo analizado", f"{result['timeline'][0]['clock']} - {result['timeline'][-1]['clock']}" if result.get("timeline") else "N/D"],
        ["Fecha del informe", result['generated_at']],
        ["Clasificación", "CONFIDENCIAL - uso exclusivo del cliente"]
    ]
    make_table(meta_table, [45*mm, 125*mm], is_header_dark=False)
    add(f"SHA-256 del archivo original: {m['sha256']}")
    story.append(Spacer(1, 10))

    # ------------------ 1. RESUMEN EJECUTIVO ------------------
    add("1. Resumen ejecutivo", "Heading1")
    add(f"Se analizaron {m.get('rows', 0)} eventos exportados correspondientes al archivo provisto. El motor de análisis correlacionó los eventos sospechosos en {len(result.get('findings', []))} hallazgos estructurados.")
    for fact in result["narrative"]["facts"]:
        add(f"• {fact}")
    add(result["narrative"]["review"])

    # Conteo rápido de criticidades
    crit_counts = {"Crítico": 0, "Alto": 0, "Medio": 0, "Bajo": 0}
    for f in result.get("findings", []):
        sev = f.get("severity", "Informativo").capitalize()
        if sev in crit_counts: crit_counts[sev] += 1

    resumen_crit = f"<b>Severidades identificadas:</b> {crit_counts['Crítico']} Crítico(s), {crit_counts['Alto']} Alto(s), {crit_counts['Medio']} Medio(s)."
    add(resumen_crit)

    # ------------------ 2. ALCANCE Y METODOLOGÍA ------------------
    add("2. Alcance y metodología", "Heading1")
    add("El procesamiento se realizó mediante análisis de heurística y reglas correlacionales. Las reglas evalúan proveedor, Event_ID y campos concretos (fuerza bruta, éxito posterior, acceso a objetos masivos, transferencias).")

    metodologia_table = [
        ["Criticidad", "Criterio aplicado", "Tiempo de respuesta"],
        ["Crítico", "Impacto confirmado o inminente: exfiltración, destrucción de copias, ejecución remota, compromiso lateral.", "Inmediato (< 1 h)"],
        ["Alto", "Actividad maliciosa clara (persistencia, privilegios, ataque dirigido) sin impacto confirmado.", "< 4 h"],
        ["Medio", "Anomalía o intento sin éxito; requiere verificación.", "< 24 h"],
        ["Bajo", "Informativo o de higiene de seguridad.", "Planificado"]
    ]
    make_table(metodologia_table, [30*mm, 100*mm, 40*mm])

    # ------------------ 3. HALLAZGOS IDENTIFICADOS ------------------
    add("3. Hallazgos identificados", "Heading1")
    if not result.get("findings"):
        add("Ninguna regla produjo hallazgos. Esto no demuestra ausencia de actividad maliciosa.")
    else:
        hallazgos_table = [["ID", "Hallazgo", "Criticidad", "Ventana", "Activos/Cuentas"]]
        for f in result["findings"]:
            activos = f"{', '.join(f.get('hosts', []))} / {', '.join(f.get('users', []))}"
            ventana = f"{f.get('start', 'N/D').split(' ')[-1]} - {f.get('end', 'N/D').split(' ')[-1]}" # Solo la hora para acortar
            hallazgos_table.append([f['id'], f['title'], f['severity'].upper(), ventana, activos[:50]])
        make_table(hallazgos_table, [20*mm, 60*mm, 25*mm, 25*mm, 40*mm])

    # ------------------ 4. DETALLE TÉCNICO DE CADA HALLAZGO ------------------
    add("4. Detalle técnico de cada hallazgo", "Heading1")

    # Mapa de eventos para extracción rápida
    event_map = {e["ref"]: e for e in result.get("events", [])}

    for f in result.get("findings", []):
        add(f"{f['id']} - {f['title']}", "Heading2")

        # Tabla resumen del hallazgo
        f_meta = [
            ["Criticidad", f"<b><font color='{get_severity_color(f['severity']).hexval()}'>{f['severity'].upper()}</font></b>"],
            ["Ventana", f"{f.get('start', 'N/D')} - {f.get('end', 'N/D')}"],
            ["Equipos", ", ".join(f.get('hosts', [])) or "N/D"],
            ["Cuentas", ", ".join(f.get('users', [])) or "N/D"],
            ["Regla Asociada", f.get('rule', 'N/D')],
            ["Eventos asociados", str(len(f.get('evidence', [])))]
        ]
        make_table(f_meta, [40*mm, 130*mm], is_header_dark=False)

        add("EXPLICACIÓN TÉCNICA", "Heading3")
        add(f"<b>Observación:</b> {f.get('observation', 'N/D')}")
        add(f"<b>Justificación:</b> {f.get('rationale', 'N/D')}")
        add(f"<b>Alternativa legítima:</b> {f.get('alternative', 'N/D')}")

        add("EVIDENCIAS EN LOS LOGS", "Heading3")
        ev_table = [["Ref", "Hora", "Equipo / Hoja", "Evento / ID", "Usuario", "Detalle Clave"]]

        for ref in f.get("evidence", [])[:10]: # Limitar a 10 para no desbordar el PDF por cada hallazgo
            if ref in event_map:
                ev = event_map[ref]
                raw = ev.get("raw", {})

                # Extracción heurística de campos comunes de SIEM
                hora = ev.get("clock", ev.get("utc", ""))
                equipo = raw.get("Computer", raw.get("DestinationHostname", ev.get("sheet", "N/D")))
                evento = raw.get("EventID", ev.get("log_id", "N/D"))
                usuario = raw.get("TargetUserName", raw.get("SubjectUserName", raw.get("SourceUserName", "N/D")))

                # Resumir el payload descartando llaves vacías
                detalle = ", ".join([f"{k}:{v}" for k, v in raw.items() if v and k not in ["Computer", "EventID", "TargetUserName", "SubjectUserName"]])
                detalle_truncado = detalle[:90] + "..." if len(detalle) > 90 else detalle

                ev_table.append([ref, str(hora)[:19], str(equipo), str(evento), str(usuario), detalle_truncado])

        if len(f.get("evidence", [])) > 10:
            ev_table.append(["...", "...", "...", "...", "...", f"(+ {len(f['evidence']) - 10} eventos similares de la misma alerta)"])

        make_table(ev_table, [15*mm, 25*mm, 30*mm, 25*mm, 25*mm, 50*mm])

        add("CRITICIDAD Y JUSTIFICACIÓN / IMPACTO", "Heading3")
        add(f.get('impact', 'No documentado.'))

        add("PLAN DE ACCIÓN SUGERIDO", "Heading3")
        action_table = [
            ["INVESTIGAR (Validación)", "CONTENER / REMEDIAR (Acción)"],
            [f.get('validation', 'N/D'), f.get('action', 'N/D')]
        ]
        make_table(action_table, [85*mm, 85*mm])
        story.append(Spacer(1, 15))

    # ------------------ 5. LÍNEA DE TIEMPO CONSOLIDADA ------------------
    story.append(PageBreak())
    add("5. Línea de tiempo consolidada", "Heading1")
    if result.get("timeline"):
        tl_table = [["Hora / Dominio", "Eventos únicos", "Eventos Flaggeados (Regla)"]]
        for t in result["timeline"]:
            tl_table.append([f"{t['hour']} · {t['clock']}", str(t["events"]), str(t["flagged"])])
        make_table(tl_table, [70*mm, 50*mm, 50*mm])
    else:
        add("No hay línea de tiempo disponible.")

    # ------------------ 6. OBSERVABLES / IoC ------------------
    add("6. Indicadores de compromiso y Observables (IoC)", "Heading1")
    add("Inventario de entidades extraídas. La aparición en registros no convierte automáticamente una IP en maliciosa; requiere validación externa de reputación.")
    if result.get("observables"):
        ioc_table = [["Valor (IP / Entidad)", "Clasificación", "Apariciones"]]
        for o in result["observables"]:
            ioc_table.append([str(o["value"]), str(o["kind"]), str(o["count"])])
        make_table(ioc_table, [70*mm, 70*mm, 30*mm])
    else:
        add("No se extrajeron observables.")

    # ------------------ 7. RECOMENDACIONES GENERALES ------------------
    add("7. Recomendaciones generales de seguridad", "Heading1")
    recomendaciones = [
        "Autenticación multifactor (MFA) obligatoria para VPN, RDP, correo y cuentas privilegiadas.",
        "Políticas de bloqueo de cuenta y detección de password spraying en el SIEM.",
        "Gestión de cuentas privilegiadas: modelo por niveles (tiering), cuentas admin nominativas separadas del uso habitual.",
        "Protección de Endpoints: EDR activo, bloqueo de ejecución desde carpetas temporales y restricción de PowerShell (Constrained Language Mode).",
        "Segmentación de red: restringir RDP/SMB directo entre estaciones de trabajo y servidores; habilitar únicamente flujos justificados."
    ]
    for r in recomendaciones:
        add(f"• {r}")

    story.append(Spacer(1, 15))
    for limit in result.get("limitations", []):
        add(f"<i>Nota operativa: {limit}</i>", "TableText")

    story.append(PageBreak())
    add("Anexo A. Evidencia original citada", "Heading1")
    cited = {ref for finding in result.get("findings", []) for ref in finding["evidence"]}
    for event in result.get("events", []):
        if event["ref"] not in cited:
            continue
        add(f"{event['ref']} · Hoja: {event['sheet']} · Fila: {event['row']}", "Heading3")
        for key, value in event["raw"].items():
            add(f"{key}: {value}")
    if not cited:
        add("No hay filas citadas por los hallazgos actuales.")

    # ------------------ PIE DE PÁGINA ------------------
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.HexColor("#65748b"))
        canvas.drawString(20*mm, 15*mm, "Analista SOC N2 (Motor de Análisis Automático)")
        canvas.drawCentredString(105*mm, 15*mm, "CONFIDENCIAL")
        canvas.drawRightString(190*mm, 15*mm, f"Página {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=25*mm,
                            title="Informe Técnico SOC L2", author="SOC L2")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

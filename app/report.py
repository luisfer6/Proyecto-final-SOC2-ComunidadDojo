"""PDF reproducible desde el mismo resultado que alimenta el dashboard."""
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def register_font():
    candidates = [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                  Path("/System/Library/Fonts/Supplemental/Arial.ttf")]
    for path in candidates:
        if path.exists():
            if "Evidence" not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont("Evidence", str(path)))
            return "Evidence"
    return "Helvetica"


FONT = register_font()


def make_pdf(result):
    output = BytesIO()
    styles = getSampleStyleSheet()
    for name in ("Normal", "Title", "Heading1", "Heading2", "Heading3"):
        styles[name].fontName = FONT
        styles[name].textColor = colors.HexColor("#17243b")
    styles["Normal"].fontSize = 9
    styles["Normal"].leading = 14
    styles["Normal"].spaceAfter = 7
    styles.add(ParagraphStyle("EvidenceText", fontName=FONT, fontSize=7, leading=10, wordWrap="CJK", spaceAfter=5))
    styles.add(ParagraphStyle("Muted", fontName=FONT, fontSize=8, leading=12, textColor=colors.HexColor("#54647e")))
    story = []

    def p(value, style="Normal"):
        # ReportLab's XML parser must never interpret text originating in logs.
        value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "\ufffd", str(value))
        return Paragraph(escape(value).replace("\n", "<br/>"), styles[style])

    def add(value, style="Normal"):
        story.append(p(value, style))

    def table(rows, widths):
        cells = [[p(cell, "EvidenceText") for cell in row] for row in rows]
        t = Table(cells, colWidths=widths, repeatRows=1, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0fb")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, 0), (-1, 0), .5, colors.HexColor("#aab9d0")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 8))

    m, s = result["metadata"], result["summary"]
    add("SOC LENS  /  INVESTIGACIÓN L2", "Muted")
    add("Informe de seguridad", "Title")
    add("Análisis de evidencia · Borrador para revisión humana", "Heading2")
    add(f"Archivo: {m['filename']}")
    add(f"Generado (UTC): {result['generated_at']} · Motor: {result['version']}")
    add(f"SHA-256 del XLSX: {m['sha256']}", "EvidenceText")
    add("1. Resumen ejecutivo", "Heading1")
    for fact in result["narrative"]["facts"]:
        add(fact)
    add(result["narrative"]["review"])
    add(f"Método de redacción: {result['narrative']['mode']}.")
    add("La criticidad prioriza la revisión por impacto potencial. No constituye una confirmación de daño, una atribución de actor ni una declaración de compromiso.")
    add("2. Alcance, integridad y metodología", "Heading1")
    add(f"{m['rows']} filas recibidas; {m['unique_rows']} únicas; {m['duplicates']} duplicados exactos; {m['invalid_dates']} fechas no interpretables. Se mantienen las filas originales y referencias hoja/fila.")
    add(f"Desfase horario declarado por el usuario (minutos respecto de UTC): {m['timezone_offset_minutes'] if m['timezone_offset_minutes'] is not None else 'no proporcionado'}. Fechas sin zona no se convierten a UTC.")
    for sheet in m["sheets"]:
        add(f"Hoja {sheet['name']}: {sheet['rows']} filas; {'omitida por esquema' if sheet['skipped'] else 'procesada'}. Mapeo: {sheet['mapping']}", "EvidenceText")
    for warning in m["warnings"]:
        add(warning)
    add("Las reglas evalúan proveedor, Event_ID y campos concretos. Fuerza bruta: al menos 5 fallos/10 min; éxito posterior: al menos 3 fallos de la misma cuenta/host/IP en 15 min; acceso a objetos: 10 eventos/5 min; transferencia: 50 MB/10 min. Ventanas solapadas pueden formar un episodio más largo. Los umbrales son heurísticos y no un baseline.")
    add("Las asociaciones entre hallazgos requieren host, cuenta e IP comunes y no más de 30 minutos entre dos evidencias. Se presentan pares; no se fusionan transitivamente como incidentes.")
    add(f"IA: {result['ai']['name']} · {result['ai']['library']} · estado: {result['ai']['status']} · semilla: 42.")
    add(result["ai"]["note"])
    add("Variables del modelo: " + "; ".join(result["ai"]["features"]) + ".")
    add("3. Hallazgos y plan específico", "Heading1")
    if not result["findings"]:
        add("Ninguna regla produjo hallazgos. Esto no demuestra ausencia de actividad maliciosa.")
    for f in result["findings"]:
        add(f"{f['id']} · {f['title']}", "Heading2")
        add(f"Criticidad: {f['severity']} · Confianza: {f['confidence']} · Regla: {f['rule']} · {f['status']}")
        add(f"Activos observados: {', '.join(f['hosts']) or 'no disponibles'}; cuentas: {', '.join(f['users']) or 'no disponibles'}.")
        add(f"Intervalo de evidencia (hora original): {f['start']} — {f['end']}.")
        for label, field in [("Observación", "observation"), ("Justificación", "rationale"),
                             ("Alternativa legítima", "alternative"), ("Impacto condicionado", "impact"),
                             ("Validación propuesta", "validation"), ("Acción propuesta", "action")]:
            add(f"{label}: {f[field]}")
        add("Evidencias exactas en anexo: " + ", ".join(f["evidence"]), "EvidenceText")
    add("4. Cronología y asociaciones", "Heading1")
    table([["Hora / dominio temporal", "Eventos únicos", "Con señal de regla"]] +
          [[f"{t['hour']} · {t['clock']}", t["events"], t["flagged"]] for t in result["timeline"]], [105*mm, 30*mm, 35*mm])
    for c in result["incidents"]:
        add(f"{c['id']} · {c['title']} · {c['status']}", "Heading3")
        add(f"Hallazgos: {', '.join(c['findings'])}. Claves: host={c['host']}; cuenta={c['user']}; IP={c['source_ip']}; reloj={c['clock']}. Evidencia del vínculo: {', '.join(c['evidence'])}.")
        add(c["reason"])
    if not result["incidents"]:
        add("Sin asociaciones que cumplan todas las claves y la ventana. Esto no descarta incidentes.")
    add("5. Observables", "Heading1")
    add("Inventario de IP de origen. No se consultó reputación externa. La aparición en registros no convierte una IP en IOC.")
    table([["IP", "Clasificación", "Eventos"]] +
          [[o["value"], o["kind"], o["count"]] for o in result["observables"]], [45*mm, 105*mm, 20*mm])
    add("6. Plan de acción y recomendaciones", "Heading1")
    for title, body in [
        ("P1 · Investigar y preservar · Analista L2 / IR", "Preservar el XLSX con su hash, obtener eventos originales y EDR de los activos citados. Validar primero hallazgos críticos y altos. Cierre: otro analista reproduce la evidencia y se confirma o refuta cada hipótesis."),
        ("P2 · Contener condicionalmente · Responsable IR / TI", "Si se acredita actividad no autorizada, aprobar aislamiento de equipos o revocación de sesiones con el dueño del servicio. Riesgo: interrupción de negocio. Cierre: la contención autorizada se verifica en telemetría y queda documentada; no ejecutada por esta aplicación."),
        ("P3 · Remediar · Administradores / dueño del activo", "Tras determinar causa y alcance, corregir accesos, retirar persistencia confirmada y recuperar desde copias verificadas. Cierre: cambios aprobados, pruebas de restauración y ausencia de recurrencia durante un periodo acordado con cobertura acreditada."),
        ("Prevención · Seguridad / TI", "Aplicar MFA, mínimo privilegio, segmentación, protección de respaldos y recolección centralizada. Registrar zona horaria, LogonId y GUID de procesos. Validar controles con ejercicios autorizados y medir detecciones con datos etiquetados."),
        ("Handoff propuesto a IR/L3", "Adjuntar hash, filas, cronología, cuentas/hosts, hipótesis, alternativas y faltantes. Pregunta: ¿qué actividad fue autorizada y qué sesiones/procesos vinculan las señales? Escalar si se confirma daño, alcance sensible o necesidad forense. No se ha enviado este paquete ni ejecutado contención."),
    ]:
        add(title, "Heading3")
        add(body)
    add("7. Limitaciones y estado operativo", "Heading1")
    for limit in result["limitations"]:
        add(limit)
    add("Estado: investigación propuesta; número y existencia de incidentes confirmados no determinables automáticamente. El informe es un cierre documental, no un cierre operativo.")
    story.append(PageBreak())
    add("Anexo A · Evidencia exacta", "Heading1")
    add("Se incluyen todas las filas citadas por los hallazgos, una vez por referencia, con todos sus campos originales. El JSON descargable conserva además todas las filas del libro y las normalizaciones. Las entidades XML se muestran como texto; no se ejecutan comandos, fórmulas ni enlaces.")
    refs = {r for f in result["findings"] for r in f["evidence"]}
    for e in result["events"]:
        if e["ref"] not in refs:
            continue
        add(f"{e['ref']} · Hoja {e['sheet']} · Fila {e['row']} · {e['log_id'] or 'sin Log_ID'}", "Heading3")
        add(f"Hora UTC: {e['utc'] or 'no determinada'} · Dominio: {e['clock']} · SHA-256 de la fila: {e['fingerprint']}", "EvidenceText")
        for field, value in e["raw"].items():
            value = f"{field}: {value}"
            # Bounded paragraphs avoid oversized, unsplittable table cells.
            for start in range(0, len(value), 1800):
                add(value[start:start+1800], "EvidenceText")
    if result["ai"]["candidates"]:
        add("Anexo B · Priorización estadística", "Heading1")
        table([["Referencia", "Score (no probabilidad)", "Contexto verificable"]] +
              [[c["ref"], c["score"], c["reason"]] for c in result["ai"]["candidates"]], [30*mm, 40*mm, 100*mm])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.HexColor("#65748b"))
        canvas.drawString(20*mm, 12*mm, "SOC Lens · Evidencia local · Pendiente de validación humana")
        canvas.drawRightString(190*mm, 12*mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=18*mm, bottomMargin=22*mm,
                            title="SOC Lens - Informe de seguridad", author="SOC Lens")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

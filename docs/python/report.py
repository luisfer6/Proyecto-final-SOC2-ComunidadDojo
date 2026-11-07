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
    """Resumen técnico: alcance, catálogo, prioridades y respuesta; evidencia completa en JSON."""
    from reportlab.platypus import KeepTogether

    output = BytesIO()
    styles = getSampleStyleSheet()
    for name in ('Normal', 'Title', 'Heading1', 'Heading2', 'Heading3'):
        styles[name].fontName = FONT
        styles[name].textColor = COLOR_HEADER_BG
    styles['Normal'].fontSize = 9
    styles['Normal'].leading = 12
    styles['Normal'].spaceAfter = 6
    styles['Heading1'].fontSize = 15
    styles['Heading1'].leading = 19
    styles['Heading1'].spaceBefore = 10
    styles['Heading1'].spaceAfter = 8
    styles['Heading2'].fontSize = 11
    styles['Heading2'].leading = 14
    styles['Heading2'].spaceBefore = 10
    styles.add(ParagraphStyle('Cell', fontName=FONT, fontSize=8, leading=10, textColor=COLOR_HEADER_BG))
    styles.add(ParagraphStyle('HeadCell', parent=styles['Cell'], textColor=colors.white))
    styles.add(ParagraphStyle('Small', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#54647e')))
    story = []
    meta, summary = result['metadata'], result['summary']
    context = meta.get('case_context', {})
    findings = result.get('findings', [])
    event_map = {e['ref']: e for e in result.get('events', [])}

    def clean(value):
        return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', str('' if value is None else value))

    def short(value, limit=130):
        text = clean(value)
        return text if len(text) <= limit else text[:limit - 3] + '...'

    def p(value, style='Normal'):
        return Paragraph(escape(clean(value)).replace('\n', '<br/>'), styles[style])

    def add(value, style='Normal'):
        story.append(p(value, style))

    def table(rows, widths, dense=False):
        cells = [[p(v, 'HeadCell' if i == 0 else 'Cell') for v in row] for i, row in enumerate(rows)]
        t = Table(cells, colWidths=[w * mm for w in widths], repeatRows=1, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_HEADER_BG),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F3F5F8')]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6), ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 2 if dense else 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2 if dense else 5),
            ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#FF7A45')),
        ]))
        story.append(t)
        story.append(Spacer(1, 7))

    # 1. Compact identification instead of a separate cover.
    add('SOC LENS / BOOTCAMP ANALISTA SOC NIVEL 2', 'Small')
    add('Informe técnico de seguridad', 'Title')
    add('Resumen técnico - borrador para revisión del analista', 'Small')
    table([
        ['Datos del caso', 'Identificación'],
        ['Cliente / Analista', f"{context.get('client') or 'Cliente corporativo (CORP)'} / {context.get('analyst') or 'Analista SOC L2'}"],
        ['Consultora / Referencia', f"{context.get('company') or 'No indicada'} / {context.get('reference') or 'Sin referencia'}"],
        ['Archivo / Fecha', f"{meta['filename']} / {result['generated_at'][:10]}"],
    ], [39, 139])
    add('1. Resumen ejecutivo', 'Heading1')
    add(f"Se analizaron {summary['events']} eventos únicos de {summary['hosts']} equipos y {summary['users']} cuentas. "
        f"Se identificaron {summary['findings']} hallazgos y {summary['flagged_events']} eventos con señal, "
        f"con {summary['hypotheses']} asociaciones contextuales para investigar.")
    add('Conclusión técnica: existen señales que requieren validación. No se confirma automáticamente ningún incidente, compromiso de cuenta ni ejecución exitosa de un comando.')
    table([['Crítico', 'Alto', 'Medio', 'Bajo'], [str(summary['severity'].get(s, 0)) for s in ('Crítico', 'Alto', 'Medio', 'Bajo')]], [44.5] * 4)
    add('Prioridad inmediata: preservar los registros de los hallazgos críticos y altos, confirmar la actividad con los responsables y verificar el resultado real antes de contener.', 'Normal')
    add('2. Alcance y metodología', 'Heading1')
    dated = sorted(e['timestamp'] for e in result.get('events', []) if e.get('timestamp'))
    add(f"Periodo: {dated[0] if dated else 'No disponible'} - {dated[-1] if dated else 'No disponible'}. Se conserva la hora y el dominio temporal del registro.")
    add('Fuente: exportación SIEM en Excel. Detección mediante reglas explicables y priorización estadística con Isolation Forest cuando hay datos suficientes. Las correlaciones son hipótesis contextuales y no demuestran causalidad.')
    add('La criticidad expresa prioridad de revisión. Faltan validación humana, contexto de negocio y claves completas de sesión/proceso para confirmar impacto. Las IP de documentación no se atribuyen a actores reales.')
    add(f"SHA-256 del archivo original: {meta['sha256']}", 'Small')

    # 2. All findings for the challenge workbook; cap only unusually large cases.
    story.append(PageBreak())
    add('3. Hallazgos identificados', 'Heading1')
    limit = 30
    add(f"Catálogo de {min(len(findings), limit)} de {len(findings)} hallazgos, ordenado por prioridad. Referencias completas y campos originales disponibles en el JSON.", 'Small')
    rows = [['ID', 'Hallazgo', 'Equipos', 'Criticidad', 'Evidencias']]
    for f in findings[:limit]:
        rows.append([f['id'], short(f['title'], 88), short(', '.join(f['hosts']), 38), f['severity'],
                     f"{len(f['evidence'])} filas\n{f['evidence'][0] if f['evidence'] else '-'}"])
    if not findings:
        rows.append(['-', 'Sin coincidencias con las reglas actuales', '-', '-', '0'])
    table(rows, [15, 76, 32, 22, 33], dense=True)
    add('Los títulos y equipos se abrevian en esta tabla. El detalle íntegro de todos los hallazgos se conserva en el dashboard y JSON.', 'Small')

    # 3. Three distinct rules, with representative evidence rather than every log row.
    story.append(PageBreak())
    add('4. Detalle técnico priorizado', 'Heading1')
    selected, rules = [], set()
    for f in findings:
        if f['rule'] not in rules:
            selected.append(f)
            rules.add(f['rule'])
        if len(selected) == 3:
            break
    add('Selección de hasta tres reglas distintas de mayor prioridad. Se resume la observación, su interpretación y la validación propuesta.', 'Small')
    for f in selected:
        block = [p(f"{f['id']} - {f['severity']} - {short(f['title'], 100)}", 'Heading2')]
        block.append(p(f"Equipos: {short(', '.join(f['hosts']), 90)}. Ventana: {f['start']} - {f['end']}. Regla: {f['rule']}.", 'Small'))
        for label, key in [('Observación', 'observation'), ('Justificación', 'rationale'), ('Impacto potencial', 'impact'), ('Alternativa legítima', 'alternative'), ('Validar', 'validation')]:
            block.append(p(f"{label}: {short(f.get(key, 'No documentado'), 260)}"))
        block.append(p(f"Evidencia: {', '.join(f['evidence'][:4])}" + (f"; {len(f['evidence'])} filas en total." if len(f['evidence']) > 4 else '.'), 'Small'))
        story.append(KeepTogether(block))
    if not selected:
        add('No hay hallazgos que priorizar. La ausencia de coincidencias no acredita ausencia de actividad no autorizada.')

    # 4. Supporting technical summary without a bulk appendix.
    story.append(PageBreak())
    add('5. Línea de tiempo consolidada', 'Heading1')
    timeline = result.get('timeline', [])
    table([['Hora original', 'Eventos únicos', 'Con señal']] + [[t['hour'], t['events'], t['flagged']] for t in timeline[:8]], [98, 40, 40])
    if len(timeline) > 8:
        add(f"Se muestran 8 de {len(timeline)} intervalos. Cronología completa en JSON.", 'Small')
    add('6. Indicadores y observables', 'Heading1')
    observables = sorted(result.get('observables', []), key=lambda o: -o['count'])
    add('; '.join(f"{o['value']} ({o['kind']}, {o['count']} registros)" for o in observables[:8]) or 'No se extrajeron observables.')
    add('Su presencia no demuestra actividad maliciosa. Los rangos de documentación son compatibles con el contexto de un reto.', 'Small')
    add('7. Plan de acción recomendado', 'Heading1')
    table([
        ['Investigar', 'Contener si se confirma', 'Remediar y verificar'],
        ['Preservar logs y tiempos; validar sesiones, MFA, propietarios y cambios autorizados.',
         'Acordar el impacto con L2/IR; limitar accesos y revocar sesiones sólo tras confirmar actividad no autorizada.',
         'Corregir la causa; revisar privilegios, MFA, segmentación y respaldos; comprobar recuperación y recurrencia.'],
    ], [59, 59, 60])
    add('Anexo A. Referencias de evidencia representativa', 'Heading2')
    for f in selected:
        event = event_map.get(f['evidence'][0]) if f['evidence'] else None
        if event:
            detail = event.get('command') or next((v for k, v in event['raw'].items() if 'command' in k.lower() and v), '') or event.get('description', '')
            add(f"{event['ref']} | {event.get('log_id', '')} | {event.get('timestamp', '')} | {event.get('host', '')} | Evento {event.get('event_id', '')}. {short(detail, 230)}", 'Small')
    add('Este PDF es un resumen: textos largos, observables y evidencias se condensan. Descarga el JSON para conservar todas las filas, referencias y hallazgos originales.', 'Small')

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor('#D8DFE8'))
        canvas.line(16 * mm, 15 * mm, 194 * mm, 15 * mm)
        canvas.setFont(FONT, 8)
        canvas.setFillColor(COLOR_HEADER_BG)
        canvas.drawString(16 * mm, 10 * mm, short(context.get('reference') or 'SOC Lens - Resumen técnico', 65))
        canvas.drawRightString(194 * mm, 10 * mm, f'CONFIDENCIAL | Página {doc.page}')
        canvas.restoreState()

    doc = SimpleDocTemplate(output, pagesize=A4, rightMargin=16 * mm, leftMargin=16 * mm,
                            topMargin=14 * mm, bottomMargin=21 * mm,
                            title='Resumen técnico SOC L2', author=context.get('analyst') or 'SOC L2')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

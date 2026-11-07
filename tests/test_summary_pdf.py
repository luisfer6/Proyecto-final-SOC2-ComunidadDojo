from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from app.analysis import analyze
from app.ingest import read_workbook
from app.report import make_pdf


def test_challenge_summary_is_short_and_preserves_catalog_and_context():
    source = Path(__file__).resolve().parents[1] / 'web/data/SOC_L2_Logs_Ampliados_Multiples_Incidentes.xlsx'
    result = analyze(*read_workbook(source.read_bytes(), source.name))
    result['metadata']['case_context'] = {'analyst': 'Analista de prueba', 'reference': 'SOC-RESUMEN-01'}
    reader = PdfReader(BytesIO(make_pdf(result)))
    assert len(reader.pages) <= 4
    text = '\n'.join(page.extract_text() for page in reader.pages)
    for heading in ('Resumen ejecutivo', 'Alcance y metodología', 'Hallazgos identificados',
                    'Detalle técnico priorizado', 'Línea de tiempo', 'Indicadores', 'Plan de acción',
                    'Anexo A', 'Analista de prueba', 'SOC-RESUMEN-01'):
        assert heading in text
    for finding in result['findings']:
        assert finding['id'] in text
    assert result['metadata']['sha256'] in text.replace('\n', '')
    assert 'No se confirma automáticamente' in text

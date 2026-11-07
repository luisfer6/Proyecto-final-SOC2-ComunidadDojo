"""Contrato compartido por Ollama local y la edición para navegador."""
import json


def validate_selection(payload, allowed):
    if not isinstance(payload, dict) or set(payload) != {"selected_ids"}:
        raise ValueError("Respuesta IA inválida: se esperaba sólo selected_ids.")
    ids = payload["selected_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 5 or any(not isinstance(i, str) for i in ids):
        raise ValueError("La IA debe seleccionar entre 1 y 5 IDs.")
    if len(set(ids)) != len(ids) or any(i not in allowed for i in ids):
        raise ValueError("La IA devolvió referencias inexistentes o duplicadas.")
    return ids


def selection_request(findings, model):
    catalog = {f["id"]: f for f in findings}
    if not catalog:
        raise ValueError("No hay hallazgos para priorizar.")
    facts = [{"id": f["id"], "rule": f["rule"], "severity": f["severity"], "evidence_count": len(f["evidence"])} for f in catalog.values()]
    return {
        "model": model, "stream": False, "think": False,
        "options": {"temperature": 0, "num_predict": 256, "num_ctx": 8192},
        "format": {"type": "object", "properties": {"selected_ids": {"type": "array", "items": {"type": "string", "enum": list(catalog)}, "minItems": 1, "maxItems": 5}}, "required": ["selected_ids"], "additionalProperties": False},
        "messages": [
            {"role": "system", "content": "Prioriza hasta 5 hallazgos SOC para un resumen, primero críticos y altos. Devuelve sólo IDs existentes en selected_ids. No confirmes incidentes ni agregues hechos."},
            {"role": "user", "content": json.dumps(facts)},
        ],
    }


def selected_narrative(result, payload, model):
    catalog = {f["id"]: f for f in result["findings"]}
    ids = validate_selection(payload, catalog)
    return {
        "mode": f"Selección asistida por Ollama ({model}); frases ensambladas desde evidencia verificada",
        "facts": result["narrative"]["facts"][:3] + [
            f"{i}: {catalog[i]['title']}. {catalog[i]['observation']} Evidencia: {', '.join(catalog[i]['evidence'])}." for i in ids],
        "review": "Borrador asistido por IA local para revisión humana. La selección no modifica los hallazgos ni su criticidad.",
    }

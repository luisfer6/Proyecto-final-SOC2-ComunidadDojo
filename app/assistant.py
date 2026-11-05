"""Asistente Ollama opcional: selecciona frases verificadas, no inventa texto."""
import json
import os
import re

import httpx


def validate_selection(payload, allowed):
    if not isinstance(payload, dict) or set(payload) != {"selected_ids"}:
        raise ValueError("Respuesta IA inválida: se esperaba sólo selected_ids.")
    ids = payload["selected_ids"]
    if not isinstance(ids, list) or not 1 <= len(ids) <= 5 or any(not isinstance(i, str) for i in ids):
        raise ValueError("La IA debe seleccionar entre 1 y 5 IDs.")
    if len(set(ids)) != len(ids) or any(i not in allowed for i in ids):
        raise ValueError("La IA devolvió referencias inexistentes o duplicadas.")
    return ids


async def assist(result):
    model = os.getenv("OLLAMA_MODEL", "")
    if not model or not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,120}", model):
        raise ValueError("Ollama no está configurado. Define OLLAMA_MODEL y ejecuta el modelo local. El análisis IA estadístico ya está disponible.")
    # Fixed loopback endpoint: a browser or log cannot choose an arbitrary URL.
    catalog = {f["id"]: f for f in result["findings"]}
    if not catalog:
        raise ValueError("No hay hallazgos para priorizar.")
    # No raw logs or user-provided strings are passed to the language model.
    facts = [{"id": f["id"], "rule": f["rule"], "severity": f["severity"], "evidence_count": len(f["evidence"])} for f in catalog.values()]
    request = {
        "model": model, "stream": False, "options": {"temperature": 0},
        "format": {"type": "object", "properties": {"selected_ids": {"type": "array", "items": {"type": "string", "enum": list(catalog)}, "minItems": 1, "maxItems": 5}}, "required": ["selected_ids"], "additionalProperties": False},
        "messages": [
            {"role": "system", "content": "Prioriza hasta 5 hallazgos SOC para un resumen, primero críticos y altos. Devuelve sólo IDs existentes en selected_ids. No confirmes incidentes ni agregues hechos."},
            {"role": "user", "content": json.dumps(facts)},
        ],
    }
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        response = await client.post("http://127.0.0.1:11434/api/chat", json=request)
        response.raise_for_status()
        if len(response.content) > 100_000:
            raise ValueError("La respuesta IA excede el tamaño permitido.")
        payload = json.loads(response.json()["message"]["content"])
    ids = validate_selection(payload, catalog)
    return {
        "mode": f"Selección asistida por Ollama ({model}); frases ensambladas desde evidencia verificada",
        "facts": result["narrative"]["facts"][:3] + [
            f"{i}: {catalog[i]['title']}. {catalog[i]['observation']} Evidencia: {', '.join(catalog[i]['evidence'])}." for i in ids],
        "review": "Borrador asistido por IA local para revisión humana. La selección no modifica los hallazgos ni su criticidad.",
    }

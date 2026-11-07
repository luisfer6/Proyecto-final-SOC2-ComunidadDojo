"""Asistente Ollama opcional: selecciona frases verificadas, no inventa texto."""
import json
import os
import re

import httpx

from .selection import validate_selection, selection_request, selected_narrative


async def ollama_status():
    model = os.getenv("OLLAMA_MODEL", "")
    status = {"ollama_configured": bool(model), "ollama_available": False, "ollama_model": model}
    if not model:
        return {**status, "ollama_message": "Ollama no está configurado. Inicia la aplicación con iniciar-con-ia.cmd."}
    try:
        async with httpx.AsyncClient(timeout=3, trust_env=False) as client:
            response = await client.get("http://127.0.0.1:11434/api/tags")
            response.raise_for_status()
            names = {m["name"] for m in response.json().get("models", [])}
        available = model in names or (":" not in model and model + ":latest" in names)
        return {**status, "ollama_available": available, "ollama_message": f"{model} disponible en este equipo." if available else f"Descarga el modelo {model} en Ollama y actualiza la página."}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {**status, "ollama_message": "Ollama no está iniciado. Abre iniciar-con-ia.cmd y actualiza la página."}


async def assist(result):
    model = os.getenv("OLLAMA_MODEL", "")
    if not model or not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,120}", model):
        raise ValueError("Ollama no está configurado. Define OLLAMA_MODEL y ejecuta el modelo local. El análisis IA estadístico ya está disponible.")
    request = selection_request(result["findings"], model)
    async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=5), trust_env=False) as client:
        response = await client.post("http://127.0.0.1:11434/api/chat", json=request)
        response.raise_for_status()
        if len(response.content) > 100_000:
            raise ValueError("La respuesta IA excede el tamaño permitido.")
        payload = json.loads(response.json()["message"]["content"])
    return selected_narrative(result, payload, model)

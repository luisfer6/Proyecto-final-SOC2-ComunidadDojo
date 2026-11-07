"""Reglas explicables e IA no supervisada. Una alerta no confirma un incidente."""
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import ipaddress
import re

import numpy as np
from sklearn.ensemble import IsolationForest
import sklearn

VERSION = "1.0.0"
RISK = {"Crítico": 0, "Alto": 1, "Medio": 2, "Bajo": 3}
DOCUMENTATION_NETS = tuple(ipaddress.ip_network(n) for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32"))
LIMITS = [
    "Hallazgos e hipótesis requieren validación humana; no se confirma automáticamente ningún incidente.",
    "No hay baseline histórico, inventario de activos críticos, autorización de cambios ni contexto de negocio.",
    "Sin LogonId, ProcessGuid, ParentGuid y telemetría de origen no se demuestra una cadena causal entre procesos o sesiones.",
    "Se conservan nombres de host tal como aparecen: por ejemplo, DC01 y DC-01 no se fusionan.",
    "La severidad del SIEM se conserva como dato; la criticidad de cada hallazgo se calcula con criterios explícitos.",
]


def provider(e, kind):
    p = e["provider"].casefold()
    names = {
        "security": ("security", "microsoft-windows-security-auditing"),
        "system": ("system", "service control manager"),
        "powershell": ("powershell", "microsoft-windows-powershell"),
        "proxy": ("proxy",), "iis": ("iis",), "firewall": ("firewall",),
        "sysmon": ("sysmon", "microsoft-windows-sysmon"),
    }
    return p in names[kind]


def event_is(e, ids, kind="security"):
    return e["event_id"] in ids and provider(e, kind)


def network_kind(value):
    try:
        ip = ipaddress.ip_address(value)
        if any(ip.version == net.version and ip in net for net in DOCUMENTATION_NETS):
            return "Documentación (RFC 5737/3849)"
        if ip.is_global:
            return "Pública; reputación no consultada"
        return "Privada / reservada"
    except ValueError:
        return "No es una IP literal"


def groups(events, fields):
    result = defaultdict(list)
    for e in events:
        if e["seconds"] is not None and all(e.get(f) for f in fields):
            result[(e["clock"], *(e[f].casefold() for f in fields))].append(e)
    return result.values()


def windows(events, seconds):
    """Disjoint episodes. Every emitted episode is bounded by an explicit window."""
    remaining = sorted(events, key=lambda e: (e["seconds"], e["ref"]))
    window = []
    for e in remaining:
        if window and e["seconds"] - window[0]["seconds"] > seconds:
            yield window
            window = []
        window.append(e)
    if window:
        yield window


def bursts(events, seconds, threshold):
    """Sliding threshold; merge overlapping qualifying windows without double counts."""
    queue, episode = deque(), {}
    for e in sorted(events, key=lambda e: (e["seconds"], e["ref"])):
        while queue and e["seconds"] - queue[0]["seconds"] > seconds:
            queue.popleft()
        queue.append(e)
        if len(queue) >= threshold:
            refs = {x["ref"] for x in queue}
            if episode and not refs.intersection(episode):
                yield list(episode.values())
                episode = {}
            episode.update({x["ref"]: x for x in queue})
    if episode:
        yield list(episode.values())


def analyze(events, metadata):
    unique = [e for e in events if not e["duplicate_of"]]
    findings = []

    def add(rule, title, category, severity, evidence, observation, rationale, alternative, validate, impact, confidence="Media"):
        if len(findings) >= 500:
            raise ValueError("El archivo genera más de 500 hallazgos. Divide la exportación por periodo o activo; no se emitió un informe parcial.")
        evidence = sorted({e["ref"]: e for e in evidence}.values(), key=lambda e: (e["seconds"] is None, e["seconds"] or 0, e["ref"]))
        if not evidence:
            return
        findings.append({
            "id": f"H-{len(findings)+1:03}", "rule": rule, "title": title,
            "category": category, "severity": severity, "confidence": confidence,
            "status": "Pendiente de validación", "evidence": [e["ref"] for e in evidence],
            "hosts": sorted({e["host"] for e in evidence if e["host"]}),
            "users": sorted({e["user"] for e in evidence if e["user"]}),
            "sources": sorted({e["source_ip"] for e in evidence if e["source_ip"]}),
            "start": evidence[0]["timestamp"], "end": evidence[-1]["timestamp"],
            "observation": observation, "rationale": rationale, "alternative": alternative,
            "validation": validate, "impact": impact,
            "action": "Preservar registros y validar con el propietario. Contener sólo tras confirmar actividad no autorizada y aprobar el impacto.",
        })

    failures = [e for e in unique if event_is(e, {"4625"})]
    successes = [e for e in unique if event_is(e, {"4624"})]
    failure_index = defaultdict(list)
    for e in failures:
        if e["seconds"] is not None and e["host"] and e["source_ip"] and e["user"]:
            failure_index[(e["clock"], e["host"].casefold(), e["source_ip"].casefold(), e["user"].casefold())].append(e)
    for group in groups(failures, ("host", "source_ip")):
        for batch in bursts(group, 600, 5):
            accounts = {e["user"] for e in batch if e["user"]}
            add("AUTH-01", "Ráfaga de autenticaciones fallidas", "Fuerza bruta", "Alto", batch,
                f"{len(batch)} eventos 4625 en ventanas solapadas de 10 minutos con al menos 5 fallos; {len(accounts)} cuentas, mismo host y origen.",
                "La concentración de fallos puede corresponder a fuerza bruta o password spraying; no prueba acceso.",
                "Credenciales caducadas, servicio mal configurado o prueba autorizada.",
                "Revisar códigos de fallo, LogonType, MFA, propietario de IP y confirmar si las cuentas reconocen los intentos.",
                "Posible acceso no autorizado si alguna credencial fue obtenida.", "Alta en el patrón; baja en compromiso")
    for e in successes:
        if e["seconds"] is None:
            continue
        previous = [f for f in failure_index.get((e["clock"], e["host"].casefold(), e["source_ip"].casefold(), e["user"].casefold()), [])
                    if 0 < e["seconds"] - f["seconds"] <= 900]
        if len(previous) >= 3:
            add("AUTH-02", "Acceso exitoso después de fallos", "Inicio sospechoso", "Alto", previous + [e],
                f"{len(previous)} fallos y un evento 4624 posterior en 15 minutos; coinciden cuenta, host y origen.",
                "El éxito posterior eleva la prioridad, pero no demuestra que la cuenta esté comprometida.",
                "Usuario legítimo que corrige una contraseña o cliente que reintenta.",
                "Obtener LogonId, MFA y confirmación del titular; correlacionar actividad dentro de esa sesión.",
                "Posible uso de credenciales válidas por un tercero.")
        if e["source_ip"] and network_kind(e["source_ip"]).startswith("Pública"):
            add("AUTH-03", "Autenticación desde IP pública", "Inicio sospechoso", "Medio", [e],
                f"Evento 4624 con Source_IP={e['source_ip']}. La dirección es globalmente enrutable.",
                "Un acceso externo requiere contrastar la política del servicio; no se ha consultado reputación.",
                "VPN, teletrabajo o gateway autorizado.",
                "Verificar NAT/VPN, ubicación autorizada, MFA y tipo de inicio de sesión.",
                "Posible exposición de un servicio de autenticación.")

    # 4672 records privileges on a new logon; it does NOT prove elevation.
    for group in groups([e for e in unique if event_is(e, {"4672"})], ("host", "user")):
        for batch in windows(group, 1800):
            add("PRIV-01", "Privilegios especiales en una sesión", "Privilegios", "Medio", batch,
                f"{len(batch)} eventos 4672: privilegios especiales asignados al iniciar sesión.",
                "Revisar cuentas privilegiadas. 4672 por sí solo no demuestra escalamiento ni falta de autorización.",
                "Sesión administrativa o cuenta de servicio autorizada.",
                "Revisar privilegios concretos, LogonId, grupos de la cuenta y cambio aprobado.",
                "Si la sesión fuera abusiva, el alcance podría incluir operaciones administrativas.")
    for e in unique:
        if event_is(e, {"4728", "4732", "4756", "4704"}):
            add("PRIV-02", "Cambio de permisos o membresía", "Privilegios", "Alto", [e],
                f"Evento {e['event_id']} que registra modificación de permisos o membresía.",
                "Puede habilitar elevación de permisos; se debe verificar el grupo y la autorización.",
                "Alta o cambio de rol aprobado.",
                "Obtener actor, miembro, grupo/privilegio destino y ticket de cambio.",
                "Posible ampliación de acceso no autorizada.")
        process = event_is(e, {"4688"}) or event_is(e, {"1"}, "sysmon") or event_is(e, {"4104"}, "powershell")
        command = e["command"]
        script = command + (" " + e["description"] if event_is(e, {"4104"}, "powershell") else "")
        if process:
            patterns = [
                ("PROC-01", r"(?:powershell|pwsh)(?:\.exe)?.*?-(?:enc(?:odedcommand)?|e)\b", "PowerShell con comando codificado", "Comandos", "Alto", "El parámetro de codificación está presente; no se ha decodificado ni ejecutado su contenido.", "Automatización administrativa codificada.", "Recuperar script original, firma, proceso padre y autorización.", "Posible ocultación de instrucciones."),
                ("PROC-02", r"\bvssadmin(?:\.exe)?\s+delete\s+shadows\b|\bwbadmin(?:\.exe)?\s+delete\s+(?:catalog|systemstatebackup)", "Comando de eliminación de respaldos", "Comandos", "Crítico", "La línea de comando solicita eliminar respaldos; el registro de proceso no acredita que la eliminación se completara.", "Mantenimiento de respaldos aprobado.", "Comprobar resultado, inventario de snapshots y tarea de mantenimiento; priorizar preservación.", "Si se completó, podría dificultar la recuperación de datos."),
                ("PROC-03", r"(?:procdump.*lsass|comsvcs.*minidump|sekurlsa::)", "Comando compatible con acceso a credenciales", "Comandos", "Crítico", "La sintaxis coincide con extracción de memoria o credenciales; no prueba que haya obtenido secretos.", "Diagnóstico o ejercicio autorizado.", "Revisar EDR, árbol de procesos, permisos y artefactos producidos.", "Posible exposición de credenciales."),
                ("PROC-04", r"\b(?:tar(?:\.exe)?\s+.*(?:-c|-a)|7z(?:\.exe)?\s+a\s|compress-archive\b)", "Creación de archivo comprimido", "Preparación de datos", "Medio", "Se registra un comando de creación de archivo; no prueba exfiltración ni contenido.", "Respaldo o empaquetado legítimo.", "Verificar archivos de entrada/salida, tamaño y actividad posterior de la misma instancia.", "Podría facilitar agrupación de datos para transferencia."),
                ("LAT-01", r"\bpsexec(?:\.exe)?\b|\bwmic(?:\.exe)?.*/node:|\bwinrs(?:\.exe)?.*-r:|\bschtasks(?:\.exe)?.*/s\s", "Comando de administración remota", "Movimiento lateral", "Alto", "La sintaxis permite ejecutar o programar acciones remotas; el éxito y destino requieren corroboración.", "Administración remota autorizada.", "Verificar destino, LogonId, EDR de ambos hosts y ticket.", "Posible ejecución en otros equipos."),
                ("DISC-01", r"\bnet(?:\.exe)?\s+view\b|get-localgroupmember|get-smbshare", "Enumeración de cuentas o recursos", "Reconocimiento", "Bajo", "Se observa sintaxis de enumeración; no demuestra uso malicioso de los resultados.", "Inventario o soporte técnico.", "Validar tarea, cuenta y contexto de la sesión.", "Podría facilitar identificación de recursos."),
                ("PROC-05", r"(?:invoke-webrequest|downloadstring|curl(?:\.exe)?\s).*(?:https?://)", "Comando de descarga", "Comandos", "Medio", "La línea solicita recuperar contenido remoto; no establece reputación ni ejecución.", "Actualización o instalación autorizada.", "Recuperar URL, firma y hash del archivo mediante fuentes internas autorizadas.", "Posible introducción de código no confiable."),
            ]
            for rule, pattern, title, category, severity, reason, alternative, validation, impact in patterns:
                if re.search(pattern, script, re.I):
                    add(rule, title, category, severity, [e], f"Coincidencia de sintaxis en {e['event_id']}: {script}", reason, alternative, validation, impact)
            if "iis apppool\\" in e["user"].casefold() and re.search(r"\b(?:cmd|powershell|pwsh)(?:\.exe)?\b", command, re.I):
                add("WEB-02", "Intérprete de comandos bajo cuenta IIS", "Actividad web", "Alto", [e],
                    f"Proceso {command} registrado con la cuenta {e['user']}.",
                    "Un intérprete bajo una cuenta web requiere revisión urgente; falta proceso padre para demostrar explotación.",
                    "Aplicación que ejecuta utilidades de sistema como parte de su función.",
                    "Obtener árbol de procesos, request ID, contenido ASPX y cambios del sitio.",
                    "Posible ejecución de comandos en el servidor web.")
        if event_is(e, {"4698"}) or event_is(e, {"7045"}, "system"):
            add("PERSIST-01", "Nuevo servicio o tarea programada", "Persistencia", "Alto" if re.search(r"programdata|\\temp\\|powershell", command, re.I) else "Medio", [e],
                f"Evento {e['event_id']}: {e['description']}. Configuración registrada: {command or 'no disponible'}.",
                "El mecanismo puede permitir ejecución persistente; creación no equivale a persistencia maliciosa.",
                "Instalador, actualización o mantenimiento legítimo.",
                "Validar firma, ruta, propietario, fecha de instalación y cambio aprobado.",
                "Posible ejecución recurrente no autorizada.")
        if event_is(e, {"1102"}) or event_is(e, {"104"}, "system"):
            add("AUDIT-01", "Borrado de registro de auditoría", "Evasión", "Alto", [e],
                f"Evento {e['event_id']} de borrado de log.",
                "Reduce visibilidad y puede ocultar actividad.",
                "Rotación o mantenimiento aprobado.", "Recuperar copia central y confirmar actor/autorización.",
                "Pérdida de evidencia para la investigación.")
        # Explicit source hostname and LogonType avoid inferring movement from mere timing.
        source_match = re.search(r"\bsource=([A-Za-z0-9_.-]+)", e["description"], re.I)
        if event_is(e, {"4624"}) and re.search(r"\bLogonType=3\b", e["description"], re.I) and source_match:
            add("LAT-02", "Acceso de red con equipo de origen explícito", "Movimiento lateral", "Medio", [e],
                f"Evento 4624 de tipo 3 en {e['host']}; la descripción declara origen {source_match[1]}, cuenta {e['user']} e IP {e['source_ip']}.",
                "Es un acceso de red observado; sólo constituye movimiento lateral malicioso si se demuestra uso no autorizado.",
                "Acceso habitual a recursos compartidos.",
                "Confirmar resolución host-IP, LogonId, autorización y actividad en origen/destino.",
                "Posible uso de una cuenta para acceder a otro sistema.")

    web = [e for e in unique if event_is(e, {"HTTP_ACCESS"}, "iis") and re.search(r"[?&](?:cmd|exec|command)=", e["command"], re.I)]
    for group in groups(web, ("host", "source_ip")):
        for batch in windows(group, 900):
            add("WEB-01", "Solicitudes web con parámetro de comando", "Actividad web", "Alto", batch,
                f"{len(batch)} solicitudes con parámetros cmd/exec/command. Respuestas: {dict(Counter(e['result'] for e in batch))}.",
                "Patrón compatible con interacción con una webshell; HTTP 200 no demuestra ejecución.",
                "Prueba autorizada o parámetro legítimo de aplicación.",
                "Verificar contenido del archivo, logs del sitio y proceso hijo asociado al request.",
                "Posible ejecución remota si el endpoint interpreta esos parámetros.")

    reads = [e for e in unique if event_is(e, {"4663"}) and e["destination"]]
    for group in groups(reads, ("host", "user", "source_ip", "destination")):
        for batch in bursts(group, 300, 10):
            add("DATA-01", "Ráfaga de accesos a objetos", "Acceso a datos", "Medio", batch,
                f"{len(batch)} eventos 4663 en ventanas solapadas de 5 minutos con al menos 10 accesos; coinciden host, cuenta, IP y destino.",
                "Volumen que requiere contexto; 4663 no demuestra extracción ni modificación por sí solo.",
                "Respaldo, antivirus, indexación o consulta por lotes.",
                "Revisar AccessMask, objetos, finalidad de la cuenta y baseline comparable.",
                "Posible recopilación de documentos.")
    outgoing = [e for e in unique if provider(e, "proxy") and re.search(r"\bbytes_out=\d+\b", e["command"])]
    for group in groups(outgoing, ("host", "user", "source_ip", "destination")):
        for batch in windows(group, 600):
            total = sum(int(re.search(r"\bbytes_out=(\d+)\b", e["command"])[1]) for e in batch)
            if total >= 50_000_000:
                add("DATA-02", "Volumen elevado de transferencia saliente", "Transferencia de datos", "Alto", batch,
                    f"{total:,} bytes_out sumados en {len(batch)} registros de proxy, dentro de 10 minutos, con host, usuario, origen y destino comunes.",
                    "Umbral heurístico de 50 MB decimales; no prueba que los datos sean sensibles ni que la transferencia sea no autorizada.",
                    "Sincronización, backup o carga de documentos autorizada.",
                    "Validar destino, autorización, DLP y contenido transferido; confirmar unidades del campo bytes_out.",
                    "Posible divulgación de información si el contenido y destino no estaban autorizados.")
    # Multi-host logons are a candidate, never a causal chain.
    for group in groups(successes, ("user", "source_ip")):
        for batch in windows(group, 900):
            if len({e["host"].casefold() for e in batch}) >= 3:
                add("LAT-03", "Autenticaciones en varios equipos", "Movimiento lateral", "Medio", batch,
                    f"{len(batch)} inicios exitosos en {len({e['host'] for e in batch})} hosts durante 15 minutos, misma cuenta e IP.",
                    "La dispersión es un candidato de investigación; una IP compartida no identifica al actor.",
                    "Administración, servicios distribuidos o NAT.",
                    "Revisar tipo de sesión, dispositivos de origen y baseline de la cuenta.",
                    "Posible ampliación del acceso a múltiples sistemas.")

    ai = anomaly_model(unique)
    if ai["candidates"]:
        candidates = [e for e in unique if e["ref"] in {c["ref"] for c in ai["candidates"]}]
        add("ML-01", "Eventos atípicos para este archivo", "Anomalía IA", "Bajo", candidates,
            f"{len(candidates)} eventos priorizados por Isolation Forest según rareza, longitud de comando, bytes salientes y horario observado.",
            "Un puntaje de anomalía es relativo al archivo; no es probabilidad de ataque ni confirma un incidente.",
            "Operaciones legítimas poco frecuentes o exportación con población sesgada.",
            "Comparar con un periodo representativo y revisar cada fila; validar rendimiento con casos etiquetados.",
            "No determinable sólo con el modelo.", "Baja para amenaza")
    findings.sort(key=lambda f: (RISK[f["severity"]], f["start"], f["id"]))
    incidents = correlate(findings, unique)
    observed = sorted({e["source_ip"] for e in unique if e["source_ip"]})
    timeline = defaultdict(lambda: {"events": 0, "flagged": 0})
    flagged = {r for f in findings if f["rule"] != "ML-01" for r in f["evidence"]}
    for e in unique:
        if e["seconds"] is not None:
            hour = (e["utc"] or e["timestamp"])[:13]
            bucket = (e["clock"], hour)
            timeline[bucket]["events"] += 1
            timeline[bucket]["flagged"] += e["ref"] in flagged
    summary = {
        "events": len(unique), "findings": len(findings), "hypotheses": len(incidents),
        "hosts": len({e["host"] for e in unique if e["host"]}),
        "users": len({e["user"] for e in unique if e["user"]}),
        "severity": {s: sum(f["severity"] == s for f in findings) for s in RISK},
        "flagged_events": len(flagged), "confirmed_incidents": 0,
    }
    limits = list(LIMITS)
    if any(network_kind(ip).startswith("Documentación") for ip in observed):
        limits.append("Hay IP de rangos de documentación; no se interpretan como IP públicas reales ni se les atribuye reputación. Son compatibles con un ejercicio sintético.")
    return {
        "version": VERSION, "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata, "summary": summary, "events": events, "findings": findings,
        "incidents": incidents, "ai": ai, "limitations": limits,
        "observables": [{"value": ip, "kind": network_kind(ip), "count": sum(e["source_ip"] == ip for e in unique),
                         "status": "Observable; no IOC confirmado"} for ip in observed],
        "timeline": [{"clock": clock, "hour": hour, **values} for (clock, hour), values in sorted(timeline.items())],
        "narrative": executive(summary, findings),
    }


def anomaly_model(events):
    info = {"name": "Isolation Forest", "library": f"scikit-learn {sklearn.__version__}",
            "seed": 42, "status": "No evaluable", "candidates": [],
            "features": ["frecuencia de Event_ID/proveedor", "frecuencia de host", "frecuencia de usuario",
                         "frecuencia de origen", "longitud de comando", "log(1+bytes_out)", "hora cíclica"],
            "note": "Modelo local no supervisado entrenado sólo con este archivo. Máximo 10 candidatos con score > 0.65; el score no es probabilidad. No establece normalidad histórica."}
    if len(events) < 30:
        info["note"] += " Se requieren al menos 30 eventos únicos."
        return info
    counters = [Counter((e["provider"], e["event_id"]) for e in events)]
    counters += [Counter(e[k] for e in events) for k in ("host", "user", "source_ip")]
    matrix = []
    for e in events:
        hour = ((e["seconds"] or 0) % 86400) / 3600
        byte_match = re.search(r"\bbytes_out=(\d+)\b", e["command"])
        keys = [(e["provider"], e["event_id"]), e["host"], e["user"], e["source_ip"]]
        matrix.append([c[k] / len(events) for c, k in zip(counters, keys)] +
                      [len(e["command"]), np.log1p(int(byte_match[1]) if byte_match else 0),
                       np.sin(hour * np.pi / 12), np.cos(hour * np.pi / 12)])
    model = IsolationForest(n_estimators=120, max_samples=min(256, len(events)), random_state=42, n_jobs=1)
    scores = -model.fit(np.array(matrix)).score_samples(np.array(matrix))
    ranked = sorted(zip(events, scores), key=lambda item: (-item[1], item[0]["ref"]))
    info.update(status="Ejecutado localmente", training_rows=len(events),
                candidates=[{"ref": e["ref"], "score": round(float(score), 4),
                             "reason": f"Comando: {len(e['command'])} caracteres; frecuencia evento/proveedor: {counters[0][(e['provider'], e['event_id'])]}/{len(events)}."}
                            for e, score in ranked if score > 0.65][:10])
    return info


def correlate(findings, events):
    """Conservative pairwise associations; no transitive account/IP chain."""
    by_ref = {e["ref"]: e for e in events}
    candidates = []
    eligible = [f for f in findings if f["rule"] not in ("ML-01", "PRIV-01", "LAT-03")]
    for i, a in enumerate(eligible):
        for b in eligible[i+1:]:
            if a["category"] == b["category"]:
                continue
            link = None
            for ra in a["evidence"]:
                ea = by_ref[ra]
                if ea["seconds"] is None or not ea["host"] or not ea["user"] or not ea["source_ip"]:
                    continue
                for rb in b["evidence"]:
                    eb = by_ref[rb]
                    if eb["seconds"] is None:
                        continue
                    same_entities = all(ea[k].casefold() == eb[k].casefold() for k in ("host", "user", "source_ip", "clock"))
                    if same_entities and abs(ea["seconds"] - eb["seconds"]) <= 1800:
                        link = {"host": ea["host"], "user": ea["user"], "source_ip": ea["source_ip"],
                                "clock": ea["clock"], "evidence": [ra, rb]}
                        break
                if link:
                    break
            if link:
                candidates.append({"id": f"C-{len(candidates)+1:03}", "findings": [a["id"], b["id"]],
                                   "title": f"{a['category']} + {b['category']}",
                                   "status": "Hipótesis, no incidente confirmado",
                                   "reason": "Coinciden host, cuenta e IP en un intervalo máximo de 30 minutos. Asociación contextual; faltan claves de sesión/proceso para establecer causalidad.",
                                   **link})
    return candidates


def executive(summary, findings):
    facts = [f"Se analizaron {summary['events']} eventos únicos de {summary['hosts']} equipos y {summary['users']} cuentas.",
             f"Se generaron {summary['findings']} hallazgos: {summary['severity']['Crítico']} críticos, {summary['severity']['Alto']} altos, {summary['severity']['Medio']} medios y {summary['severity']['Bajo']} bajos.",
             f"Hay {summary['hypotheses']} asociaciones contextuales que requieren investigación. El número real de incidentes no es determinable con validación automática."]
    facts += [f"{f['id']}: {f['title']}. {f['observation']} Evidencia: {', '.join(f['evidence'])}." for f in findings[:5]]
    return {"mode": "Redacción automática de hechos verificados", "facts": facts,
            "review": "Borrador para revisión del analista. Las acciones propuestas no se han ejecutado."}

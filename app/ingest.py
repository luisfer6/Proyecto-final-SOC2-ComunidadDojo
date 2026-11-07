"""Parseo acotado de XLSX y CSV. Nunca evalúa fórmulas ni abre enlaces del libro."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import csv
import json
import re
import unicodedata
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook

MAX_UPLOAD = 10 * 1024 * 1024
MAX_ROWS = 30_000
MAX_COLUMNS = 60
MAX_CELL = 8_000
FIELDS = {
    "log_id": ("Log_ID", "RecordId", "EventRecordID", "ID"),
    "timestamp": ("Timestamp", "TimeCreated", "TimeGenerated", "Fecha", "DateTime"),
    "host": ("Hostname", "Computer", "Host", "Equipo"),
    "event_id": ("Event_ID", "EventID", "EventCode"),
    "user": ("User", "AccountName", "TargetUserName", "Usuario"),
    "source_ip": ("Source_IP", "IpAddress", "SourceIP", "src_ip"),
    "destination": ("Destination", "DestinationIP", "Destino", "dst"),
    "provider": ("Log_Source", "Provider", "Source", "Channel"),
    "description": ("Event_Description", "Message", "Description", "Descripcion"),
    "command": ("Process_CommandLine", "CommandLine", "Command", "Comando"),
    "result": ("Result", "Outcome", "Resultado"),
    "source_severity": ("Severity", "Level", "Severidad"),
}


def key(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", text.lower())


def text(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    return str(value)


def parse_time(value, offset, sheet):
    """Return sortable seconds and a clock domain, without guessing a time zone."""
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        if dt.tzinfo is None and offset is not None:
            dt = dt.replace(tzinfo=timezone(timedelta(minutes=offset)))
        if dt.tzinfo is None:
            return (dt - datetime(1970, 1, 1)).total_seconds(), f"sin-zona:{sheet}", ""
        normalized = dt.astimezone(timezone.utc)
        return normalized.timestamp(), "UTC", normalized.isoformat()
    except (ValueError, TypeError, OverflowError):
        return None, "no-interpretable", ""


def workbook_tables(book):
    for sheet in book.worksheets:
        # Do not trust cached worksheet dimensions supplied by the document.
        sheet.reset_dimensions()
        yield sheet.title, (((cell.value, cell.data_type == "f") for cell in row)
                            for row in sheet.iter_rows())


def read_workbook(data: bytes, filename: str, offset: int | None = None):
    if not filename.lower().endswith((".xlsx", ".csv")):
        raise ValueError("Selecciona un archivo .xlsx o .csv.")
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError("El archivo debe contener datos y ocupar como máximo 10 MB.")
    if offset is not None and not -720 <= offset <= 840:
        raise ValueError("El desfase horario debe estar entre UTC−12 y UTC+14.")
    book = None
    if filename.lower().endswith(".csv"):
        encoding = "utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
        try:
            content = data.decode(encoding)
        except UnicodeDecodeError as exc:
            raise ValueError("El CSV debe estar codificado en UTF-8 o UTF-16 con BOM.") from exc
        if "\x00" in content:
            raise ValueError("El CSV contiene caracteres nulos; comprueba su codificación.")
        try:
            dialect = csv.Sniffer().sniff(content.partition("\n")[0], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = csv.reader(StringIO(content, newline=""), delimiter=dialect.delimiter, strict=True)
        tables = [(filename, (((value, False) for value in row) for row in rows))]
    else:
        try:
            with ZipFile(BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(i.file_size for i in entries) > 60 * 1024 * 1024:
                    raise ValueError("Libro demasiado grande al descomprimir (máximo 60 MB / 2000 entradas).")
                if any(i.flag_bits & 1 for i in entries):
                    raise ValueError("No se admiten libros cifrados.")
            book = load_workbook(BytesIO(data), read_only=True, data_only=False, keep_links=False)
        except (BadZipFile, KeyError, OSError) as exc:
            raise ValueError("No se pudo abrir el XLSX. Comprueba que sea un libro válido sin contraseña.") from exc
        tables = workbook_tables(book)

    events, sheets, warnings = [], [], []
    seen, duplicate_ids = {}, Counter()
    missing = Counter()
    try:
        for sheet_index, (sheet_title, rows) in enumerate(tables, start=1):
            first = next(rows, ())
            headers = [text(value).strip() for value, _ in first]
            if not headers:
                continue
            if len(headers) > MAX_COLUMNS or any(len(h) > 200 for h in headers):
                raise ValueError(f"Hoja {sheet_title}: máximo 60 columnas y cabeceras de 200 caracteres.")
            if len(set(headers)) != len(headers) or any(not h for h in headers):
                raise ValueError(f"Hoja {sheet_title}: las cabeceras deben ser únicas y no estar vacías.")
            mapping = {}
            for canonical, aliases in FIELDS.items():
                matches = [i for i, h in enumerate(headers) if key(h) in {key(a) for a in aliases}]
                if len(matches) > 1:
                    raise ValueError(f"Hoja {sheet_title}: varias columnas representan {canonical}. Conserva una sola.")
                if matches:
                    mapping[canonical] = matches[0]
            required = {"timestamp", "host", "event_id", "provider"}
            if not required <= mapping.keys():
                warnings.append(f"Hoja omitida: {sheet_title}. Faltan columnas: {', '.join(sorted(required - mapping.keys()))}.")
                sheets.append({"name": sheet_title, "rows": 0, "skipped": True, "mapping": {}})
                continue
            count = 0
            for row_number, cells in enumerate(rows, start=2):
                cells = list(cells)
                if row_number > MAX_ROWS + 2:
                    raise ValueError("Una hoja supera el límite de 30 000 filas físicas.")
                if not any(value is not None and value != "" for value, _ in cells):
                    continue
                if len(events) >= MAX_ROWS:
                    raise ValueError("Máximo 30 000 eventos por archivo.")
                if len(cells) > len(headers):
                    raise ValueError(f"{sheet_title}, fila {row_number}: hay datos sin cabecera.")
                if any(formula for _, formula in cells):
                    raise ValueError(f"{sheet_title}, fila {row_number}: contiene fórmulas. Exporta valores para conservar evidencia inequívoca.")
                values = [value for value, _ in cells] + [None] * (len(headers) - len(cells))
                if any(len(text(v)) > MAX_CELL for v in values):
                    raise ValueError(f"{sheet_title}, fila {row_number}: una celda supera 8000 caracteres.")
                raw = dict(zip(headers, map(text, values)))
                normalized = {f: text(values[mapping[f]]).strip() if f in mapping else "" for f in FIELDS}
                for f in ("host", "user", "source_ip", "destination"):
                    if normalized[f] in ("-", "N/A", "null"):
                        normalized[f] = ""
                seconds, clock, utc = parse_time(values[mapping["timestamp"]], offset, sheet_title)
                fingerprint = sha256(json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
                ref = f"S{sheet_index}-R{row_number}"
                event = {
                    **normalized, "ref": ref, "sheet": sheet_title, "row": row_number,
                    "raw": raw, "seconds": seconds, "clock": clock, "utc": utc,
                    "duplicate_of": seen.get(fingerprint), "fingerprint": fingerprint,
                }
                seen.setdefault(fingerprint, ref)
                if normalized["log_id"]:
                    duplicate_ids[normalized["log_id"]] += 1
                for f in FIELDS:
                    if not normalized[f]:
                        missing[f] += 1
                events.append(event)
                count += 1
            sheets.append({"name": sheet_title, "rows": count, "skipped": False,
                           "mapping": {f: headers[i] for f, i in mapping.items()}})
    except csv.Error as exc:
        raise ValueError("No se pudo leer el CSV: comprueba los separadores, las comillas y el tamaño de las celdas.") from exc
    finally:
        if book is not None:
            book.close()
    if not events:
        raise ValueError("No hay eventos interpretables. Se necesitan Timestamp, Hostname, Event_ID y Log_Source en la primera fila. " + " ".join(warnings))
    invalid = sum(e["seconds"] is None for e in events)
    naive = sum(e["clock"].startswith("sin-zona") for e in events)
    if naive:
        warnings.append(f"{naive} eventos sin zona horaria: se conserva la hora del archivo; correlación sólo dentro de cada hoja, asumiendo relojes comparables. No se convierte a UTC.")
    if invalid:
        warnings.append(f"{invalid} fechas no interpretables: se conservan las filas pero se excluyen de reglas temporales.")
    duplicates = sum(bool(e["duplicate_of"]) for e in events)
    if duplicates:
        warnings.append(f"{duplicates} duplicados exactos conservados como evidencia y excluidos de recuentos de detección.")
    repeated_ids = sum(v > 1 for v in duplicate_ids.values())
    if repeated_ids:
        warnings.append(f"{repeated_ids} Log_ID repetidos: la referencia única es hoja + fila.")
    warnings.append("La ausencia de una detección no descarta actividad fuera de las reglas o de la cobertura del archivo.")
    return events, {
        "filename": filename, "sha256": sha256(data).hexdigest(), "bytes": len(data),
        "rows": len(events), "unique_rows": len(events) - duplicates,
        "duplicates": duplicates, "invalid_dates": invalid, "timezone_offset_minutes": offset,
        "sheets": sheets, "missing_fields": dict(missing), "warnings": warnings,
    }

import csv
from hashlib import sha256
from io import StringIO

from fastapi.testclient import TestClient
import pytest

from app.ingest import read_workbook
from app.main import app


HEADERS = ["Timestamp", "Hostname", "Event_ID", "Log_Source", "Process_CommandLine", "Message"]
ROW = ["2026-01-01 12:00:00", "HOST-01", "4688", "Security", "=literal", '  Descripción, con; "comillas" y separadores\ny salto']


def payload(rows=None, headers=None, delimiter=",", encoding="utf-8"):
    out = StringIO(newline="")
    writer = csv.writer(out, delimiter=delimiter)
    writer.writerow(HEADERS if headers is None else headers)
    writer.writerows([ROW] if rows is None else rows)
    return out.getvalue().encode(encoding)


@pytest.mark.parametrize("delimiter", [",", ";", "\t", "|"])
@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16"])
def test_csv_formats_preserve_evidence(delimiter, encoding):
    data = payload(delimiter=delimiter, encoding=encoding)
    events, meta = read_workbook(data, "logs.CSV", -180)
    event, = events
    assert event["command"] == "=literal"
    assert event["description"] == ROW[-1].strip()
    assert event["raw"]["Message"] == ROW[-1]
    assert event["ref"] == "S1-R2"
    assert event["sheet"] == "logs.CSV"
    assert event["utc"] == "2026-01-01T15:00:00+00:00"
    assert meta["sha256"] == sha256(data).hexdigest()
    assert meta["filename"] == "logs.CSV"


@pytest.mark.parametrize("data", [
    b"", b"\xffnot utf8", b"Timestamp,Hostname,Event_ID,Log_Source\n\x00",
    payload(headers=["Timestamp", "Hostname", "Event_ID", "Log_Source", "Message", "Message"]),
    payload(headers=["Timestamp", "Hostname"]),
    payload(rows=[ROW + ["extra"]]),
    payload(rows=[ROW[:4] + ["x" * 8001, ""]]),
    b'Timestamp,Hostname,Event_ID,Log_Source\n"unterminated',
])
def test_csv_rejects_invalid_input(data):
    with pytest.raises(ValueError):
        read_workbook(data, "bad.csv")


def test_csv_duplicates_and_short_rows():
    events, meta = read_workbook(payload(rows=[ROW, ROW, ROW[:4]]), "logs.csv")
    assert meta["duplicates"] == 1
    assert events[1]["duplicate_of"] == "S1-R2"
    assert events[2]["command"] == ""


def test_csv_limits(monkeypatch):
    monkeypatch.setattr("app.ingest.MAX_ROWS", 1)
    with pytest.raises(ValueError, match="eventos"):
        read_workbook(payload(rows=[ROW, ROW]), "logs.csv")
    monkeypatch.setattr("app.ingest.MAX_UPLOAD", 10)
    with pytest.raises(ValueError, match="10 MB"):
        read_workbook(payload(), "logs.csv")


def test_csv_upload_api_and_export():
    with TestClient(app) as client:
        response = client.post("/api/analyze", files={"file": ("logs.csv", payload(), "text/csv")})
        assert response.status_code == 200, response.text
        case = response.json()
        assert case["metadata"]["filename"] == "logs.csv"
        exported = client.get(f"/api/cases/{case['id']}/evidence.json")
        assert exported.status_code == 200
        assert exported.json()["events"][0]["command"] == "=literal"
        client.delete(f"/api/cases/{case['id']}")

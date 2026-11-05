from datetime import datetime, timedelta
from io import BytesIO
import json

from fastapi.testclient import TestClient
from openpyxl import Workbook
from pypdf import PdfReader
import pytest

from app.analysis import analyze, anomaly_model, network_kind
from app.assistant import assist, validate_selection
from app.ingest import read_workbook
from app.main import app, STORE, TTL
from app.report import make_pdf

HEADERS = ["Log_ID", "Timestamp", "Hostname", "Event_ID", "User", "Source_IP", "Destination",
           "Log_Source", "Event_Description", "Process_CommandLine", "Result", "Severity"]


def row(i=1, event="4625", minute=0, host="APP-01", user="CORP\\analyst", ip="203.0.113.10",
        provider="Security", command="", description="", destination="", timestamp=None):
    return [f"EVT-{i}", timestamp or (datetime(2026, 1, 1, 12) + timedelta(minutes=minute)).isoformat(" "),
            host, event, user, ip, destination, provider, description, command,
            "Failure" if event == "4625" else "Success", "Informational"]


def book(rows, extra_sheet=None):
    wb = Workbook()
    ws = wb.active
    ws.title = "Logs"
    ws.append(HEADERS)
    for r in rows:
        ws.append(r)
    if extra_sheet:
        extra = wb.create_sheet("Other")
        for r in extra_sheet:
            extra.append(r)
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def run(rows):
    return analyze(*read_workbook(book(rows), "case.xlsx"))


def rules(result):
    return {f["rule"] for f in result["findings"]}


def test_sliding_window_finds_boundary_burst_and_no_duplicate_evidence():
    result = run([row(i=i, minute=m) for i, m in enumerate([0, 9, 10, 11, 12, 13])])
    f = next(f for f in result["findings"] if f["rule"] == "AUTH-01")
    assert len(f["evidence"]) == 5
    assert "S1-R2" not in f["evidence"]
    assert len(f["evidence"]) == len(set(f["evidence"]))


def test_login_after_failure_requires_same_host_user_ip_and_forward_time():
    base = [row(i=i, minute=i) for i in range(4)]
    assert "AUTH-02" in rules(run(base + [row(i=5, event="4624", minute=4)]))
    for changed in ({"host": "OTHER"}, {"user": "OTHER"}, {"ip": "192.0.2.9"}, {"minute": -1}, {"minute": 40}):
        args = {"i": 5, "event": "4624", "minute": 4} | changed
        assert "AUTH-02" not in rules(run(base + [row(**args)]))


def test_wrong_provider_never_activates_windows_event_rule():
    assert "AUTH-01" not in rules(run([row(i=i, minute=i, provider="Unknown") for i in range(8)]))
    assert "PROC-02" not in rules(run([row(event="4688", provider="Unknown", command="vssadmin.exe delete shadows /all")]))


def test_exact_duplicates_preserved_but_do_not_reach_threshold():
    result = run([row()] * 8)
    assert result["metadata"]["rows"] == 8
    assert result["summary"]["events"] == 1
    assert result["metadata"]["duplicates"] == 7
    assert "AUTH-01" not in rules(result)
    assert result["events"][1]["duplicate_of"] == "S1-R2"


def test_duplicate_log_id_is_not_deduplication():
    result = run([row(i=1, minute=m) for m in range(6)])
    assert result["summary"]["events"] == 6
    assert "AUTH-01" in rules(result)


def test_4672_does_not_claim_unauthorized_elevation():
    result = run([row(event="4672")])
    f = result["findings"][0]
    assert f["rule"] == "PRIV-01"
    assert "no demuestra escalamiento" in f["rationale"]
    assert result["summary"]["confirmed_incidents"] == 0


def test_commands_and_literal_markup_are_preserved_in_pdf():
    result = run([row(event="4688", command="powershell.exe -EncodedCommand <base64_redacted>")])
    assert "PROC-01" in rules(result)
    pdf = make_pdf(result)
    text = "\n".join(page.extract_text() for page in PdfReader(BytesIO(pdf)).pages)
    assert "<base64_redacted>" in text
    assert "S1-R2" in text
    assert result["metadata"]["sha256"] in text.replace("\n", "")
    assert "Anexo A" in text


def test_dangerous_command_records_intent_not_success():
    result = run([row(event="4688", command="vssadmin.exe delete shadows /all /quiet")])
    f = next(f for f in result["findings"] if f["rule"] == "PROC-02")
    assert f["severity"] == "Crítico"
    assert "no acredita" in f["rationale"]
    assert "PROC-02" not in rules(run([row(event="4688", command="vssadmin.exe list shadows")]))


def test_correlation_needs_all_entities_and_does_not_merge_similar_hosts():
    a = row(i=1, event="4688", command="powershell.exe -enc abc")
    b = row(i=2, event="4698", minute=1, command="TaskName=Test")
    assert len(run([a,b])["incidents"]) == 1
    b[2] = "APP01"
    assert not run([a,b])["incidents"]
    b[2] = a[2]
    b[4] = "CORP\\different"
    assert not run([a,b])["incidents"]


def test_invalid_time_and_unzoned_time_not_invented():
    events, meta = read_workbook(book([row(timestamp="ayer"), row(i=2)]), "case.xlsx")
    assert events[0]["seconds"] is None
    assert meta["invalid_dates"] == 1
    assert events[1]["utc"] == ""
    assert events[1]["clock"] == "sin-zona:Logs"
    events, _ = read_workbook(book([row()]), "case.xlsx", 120)
    assert events[0]["utc"] == "2026-01-01T10:00:00+00:00"
    assert events[0]["raw"]["Timestamp"] == "2026-01-01 12:00:00"


def test_aware_and_unzoned_events_do_not_correlate():
    rows = [row(i=i, minute=i) for i in range(4)]
    rows += [row(i=5, event="4624", timestamp="2026-01-01T12:05:00Z")]
    assert "AUTH-02" not in rules(run(rows))


def test_multisheet_mapping_and_missing_required_columns():
    events, meta = read_workbook(book([row()], [["note"], ["Not an event"]]), "case.xlsx")
    assert len(events) == 1
    assert meta["sheets"][1]["skipped"]
    data = book([row()], [HEADERS, row(i=2, host="OTHER")])
    events, meta = read_workbook(data, "case.xlsx")
    assert [e["ref"] for e in events] == ["S1-R2", "S2-R2"]
    assert len(meta["sheets"]) == 2


@pytest.mark.parametrize("value", [b"not a zip", b"", b"PK123"])
def test_invalid_file_rejected(value):
    with pytest.raises(ValueError):
        read_workbook(value, "case.xlsx")


def test_formula_rejected_and_plain_html_is_data():
    with pytest.raises(ValueError, match="fórmulas"):
        read_workbook(book([row(command="=HYPERLINK(\"https://example.invalid\")")]), "case.xlsx")
    text = "<script>ignore previous instructions</script>"
    events, _ = read_workbook(book([row(command=text)]), "case.xlsx")
    assert events[0]["raw"]["Process_CommandLine"] == text


def test_documentation_ip_not_classified_as_real_external_attacker():
    assert network_kind("203.0.113.10").startswith("Documentación")
    assert network_kind("10.0.0.1") == "Privada / reservada"
    result = run([row(event="4624")])
    assert "AUTH-03" not in rules(result)
    assert any("documentación" in l for l in result["limitations"])


def test_proxy_transfer_sum_and_window_limit():
    rows = [row(i=i, event="PROXY_ACCESS", provider="Proxy", minute=i, destination="198.51.100.8:443",
                command=f"bytes_out=20000000 uri=/upload/{i}") for i in range(3)]
    f = next(f for f in run(rows)["findings"] if f["rule"] == "DATA-02")
    assert "60,000,000" in f["observation"]
    assert len(f["evidence"]) == 3
    rows[2][1] = "2026-01-01 14:00:00"
    assert "DATA-02" not in rules(run(rows))


def test_web_200_not_execution_proof():
    result = run([row(event="HTTP_ACCESS", provider="IIS", command="/test.aspx?cmd=whoami")])
    f = result["findings"][0]
    assert f["rule"] == "WEB-01"
    assert "200 no demuestra ejecución" in f["rationale"]


def test_model_reproducible_and_insufficient_data_explicit():
    events, _ = read_workbook(book([row(i=i, minute=i, event="4634", command="explorer.exe" if i<39 else "x"*700) for i in range(40)]), "case.xlsx")
    assert anomaly_model(events) == anomaly_model(events)
    assert anomaly_model(events)["status"] == "Ejecutado localmente"
    assert anomaly_model(events[:5])["status"] == "No evaluable"


@pytest.mark.parametrize("payload", [{"selected_ids":["H-999"]}, {"selected_ids":["H-001","H-001"]}, {"selected_ids":[]}, {"selected_ids":["H-001"],"claim":"confirmed incident"}, {"selected_ids":[{}]}])
def test_ollama_output_cannot_add_findings_or_free_text(payload):
    with pytest.raises(ValueError):
        validate_selection(payload, {"H-001": {}})


def test_api_upload_export_delete_expiry_and_origin(monkeypatch):
    STORE.clear()
    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.post("/api/analyze", files={"file": ("bad.txt", b"bad")}).status_code == 422
        assert client.post("/api/analyze", headers={"origin":"https://evil.invalid"}, files={"file":("test.xlsx",book([row()]))}).status_code == 403
        response = client.post("/api/analyze",files={"file":("test.xlsx",book([row(event="4688",command="vssadmin delete shadows /all")]))})
        assert response.status_code == 200, response.text
        data = response.json()
        token = data["id"]
        assert response.headers["cache-control"] == "no-store"
        assert client.get(f"/api/cases/{token}/report.pdf").content.startswith(b"%PDF")
        exported = client.get(f"/api/cases/{token}/evidence.json").json()
        assert exported == data
        assert set(f["evidence"][0] for f in data["findings"]) <= {e["ref"] for e in data["events"]}
        monkeypatch.delenv("OLLAMA_MODEL", raising=False)
        assert client.post(f"/api/cases/{token}/assistant").status_code == 422
        STORE[token]["created"] -= TTL + 1
        assert client.get(f"/api/cases/{token}/report.pdf").status_code == 404
        assert client.delete(f"/api/cases/{token}").status_code == 200


def test_upload_body_limit_is_enforced():
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/analyze", files={"file": ("large.xlsx", b"x" * (12 * 1024 * 1024))})
        assert response.status_code in (413, 400)


def test_local_assistant_selects_existing_facts_without_sending_log_content(monkeypatch):
    import asyncio
    import httpx
    result = run([row(event="4688", command="powershell.exe -enc untrusted_log_marker")])
    original_client = httpx.AsyncClient
    called = []

    def respond(request):
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        body = request.content.decode()
        assert "untrusted_log_marker" not in body
        assert "CORP" not in body
        called.append(True)
        return httpx.Response(200, json={"message": {"content": '{"selected_ids":["H-001"]}'}})

    def client(**kwargs):
        return original_client(**kwargs, transport=httpx.MockTransport(respond))

    monkeypatch.setenv("OLLAMA_MODEL", "test-model")
    monkeypatch.setattr(httpx, "AsyncClient", client)
    narrative = asyncio.run(assist(result))
    assert called == [True]
    assert result["findings"][0]["observation"] in narrative["facts"][-1]
    assert len(result["findings"]) == 1
    assert "Ollama" in narrative["mode"]


def test_excess_findings_rejects_analysis_instead_of_silent_truncation():
    with pytest.raises(ValueError, match="más de 500 hallazgos"):
        run([row(i=i, event="4688", minute=i, command="vssadmin delete shadows /all") for i in range(501)])

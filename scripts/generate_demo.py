"""Crea un archivo de demostración sintético; no contiene logs del cliente."""
from datetime import datetime, timedelta
from pathlib import Path
import random

from openpyxl import Workbook


def main():
    random.seed(42)
    wb = Workbook()
    ws = wb.active
    ws.title = "DEMO SINTETICA"
    ws.append(["Log_ID", "Timestamp", "Hostname", "Event_ID", "User", "Source_IP", "Destination",
               "Log_Source", "Event_Description", "Process_CommandLine", "Result", "Severity"])
    base = datetime(2026, 10, 23, 8)
    rows = []
    for i in range(160):
        rows.append([(base+timedelta(seconds=i*90)).isoformat(" "), f"DEMO-WS-{i%4+1:02}", "4634",
                     f"DEMO\\usuario{i%5}", f"10.20.0.{i%4+1}", "", "Security",
                     "Synthetic account logoff", "", "Success", "Informational"])
    for i in range(8):
        rows.append([(base+timedelta(minutes=10, seconds=i*20)).isoformat(" "), "DEMO-APP", "4625",
                     "DEMO\\admin", "203.0.113.10", "DEMO-APP", "Security",
                     "Synthetic failed logon", "", "Failure", "Warning"])
    for minute, event, command, desc in [
        (14, "4624", "", "Synthetic successful logon"),
        (15, "4672", "", "Synthetic special privileges assigned"),
        (17, "4688", "powershell.exe -EncodedCommand [SYNTHETIC_REDACTED]", "Synthetic process creation"),
        (19, "4688", "vssadmin.exe delete shadows /all /quiet", "Synthetic process creation; execution not performed"),
        (21, "4698", r"TaskName=DEMO; Action=C:\ProgramData\demo.exe", "Synthetic scheduled task"),
    ]:
        rows.append([(base+timedelta(minutes=minute)).isoformat(" "), "DEMO-APP", event,
                     "DEMO\\admin", "203.0.113.10", "", "Security", desc, command, "Success", "Warning"])
    for i,row in enumerate(sorted(rows),start=1):
        ws.append([f"DEMO-{i:04}",*row])
    for column in ws.columns:
        ws.column_dimensions[column[0].column_letter].width=22
    destination = Path(__file__).resolve().parent.parent / "artifacts" / "demo-sintetica.xlsx"
    destination.parent.mkdir(exist_ok=True)
    wb.save(destination)
    print(destination)


if __name__ == "__main__":
    main()

import argparse
import csv
from pathlib import Path
from typing import Dict, Iterable
import sys

try:
    from openpyxl import load_workbook
except Exception as exc:  # pragma: no cover - optional dependency
    raise SystemExit("openpyxl is required to read Excel files. Install it via pip.") from exc


def read_shortlist(path: Path) -> list[dict]:
    """Return rows from the bot shortlist CSV."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        sample = f.read(1024)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
        reader = csv.DictReader(f, dialect=dialect)
        rows = [dict(row) for row in reader]
    return rows


def read_usage(path: Path, scope: str) -> Dict[str, float]:
    """Return mapping of AppId to Active Users filtered by scope."""
    wb = load_workbook(filename=path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    col_idx = {h: i for i, h in enumerate(header)}

    required = {"AppId", "Active Users", "App Scope"}
    if not required <= set(col_idx):
        missing = required - set(col_idx)
        raise ValueError(f"Missing columns in usage data: {', '.join(missing)}")

    usage: Dict[str, float] = {}
    for row in rows[1:]:
        if row[col_idx["App Scope"]] != scope:
            continue
        app_id = row[col_idx["AppId"]]
        active_users = row[col_idx["Active Users"]]
        if app_id is None or active_users is None:
            continue
        try:
            val = float(active_users)
        except (TypeError, ValueError):
            continue
        if app_id not in usage or usage[app_id] < val:
            usage[app_id] = val
    return usage


def merge_data(shortlist: Iterable[dict], usage: Dict[str, float]) -> list[dict]:
    """Return merged rows with Active Users column sorted by usage."""
    merged = []
    for row in shortlist:
        app_id = row.get("App ID") or row.get("AppId")
        row = dict(row)
        row["Active Users"] = usage.get(app_id, 0)
        merged.append(row)
    merged.sort(key=lambda r: r.get("Active Users", 0) or 0, reverse=True)
    return merged


def write_csv(rows: Iterable[dict], path: Path | None) -> None:
    """Write rows as CSV to the given path or stdout."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    out_file = open(path, "w", newline="", encoding="utf-8") if path else None
    writer = csv.DictWriter(out_file or sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    if out_file:
        out_file.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge bot shortlist with usage data")
    parser.add_argument("botshortlist", type=Path, help="Path to shortlist CSV")
    parser.add_argument("usagedata", type=Path, help="Path to usage XLSX file")
    parser.add_argument("--rankby", choices=["Teams", "Group", "Meetings", "Personal"], default="Teams", help="Scope to rank by")
    parser.add_argument("-o", "--output", type=Path, help="Output CSV path")
    args = parser.parse_args()

    shortlist = read_shortlist(args.botshortlist)
    usage = read_usage(args.usagedata, args.rankby)
    merged = merge_data(shortlist, usage)
    write_csv(merged, args.output)


if __name__ == "__main__":
    main()

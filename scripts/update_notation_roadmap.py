"""Advance notation M1-M3 only from a complete, passing T3 evidence bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)


def update(workbook: Path, results_file: Path) -> list[str]:
    results = json.loads(results_file.read_text())
    statuses = {r["id"]: r["result"] for r in results}
    if len(results) != 53 or len(statuses) != 53:
        raise ValueError("expected all 53 notation assertions")
    if any(r["result"] != "PASS" for r in results if r["due"] <= 3):
        raise ValueError("M3 cannot advance: a required assertion is not PASS")
    completed = []
    evidence = str(results_file.parent.relative_to(ROOT)) if results_file.is_relative_to(ROOT) else str(results_file.parent)
    with ZipFile(workbook) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared = ["".join(e.itertext()) for e in ET.fromstring(archive.read("xl/sharedStrings.xml"))]
        content = {name: archive.read(name) for name in archive.namelist()}
        infos = archive.infolist()

    def value(cell):
        text, raw = cell.find(f"{{{NS}}}is"), cell.find(f"{{{NS}}}v")
        if cell.get("t") == "s" and raw is not None:
            return shared[int(raw.text)]
        return "".join(text.itertext()) if text is not None else raw.text if raw is not None else ""

    def put(cell, text):
        for child in list(cell):
            cell.remove(child)
        cell.set("t", "inlineStr")
        ET.SubElement(ET.SubElement(cell, f"{{{NS}}}is"), f"{{{NS}}}t").text = str(text)

    for name, data in list(content.items()):
        if not name.startswith("xl/worksheets/") or not name.endswith(".xml"):
            continue
        root = ET.fromstring(data)
        for row in root.findall(f"{{{NS}}}sheetData/{{{NS}}}row"):
            cells = {re.sub(r"\d", "", c.get("r")): c for c in row}
            vals = {k: value(c) for k, c in cells.items()}
            if name.endswith("sheet3.xml") and vals.get("A", "").startswith("RN-"):
                target = vals.get("D", "")
                if target in {"M1", "M2", "M3"} or vals["A"] in {"RN-O-003", "RN-A-003"}:
                    identifiers = re.findall(r"HARNESS-N[A-Z]+-\d{3}", vals["X"])
                    if not identifiers or any(statuses.get(i) != "PASS" for i in identifiers):
                        raise ValueError(f"missing passing evidence for {vals['A']}")
                    put(cells["Z"], "complete")
                    put(cells["AA"], "100")
                    put(cells["AB"], evidence + "/results.json; " + ", ".join(identifiers))
                    completed.append(vals["A"])
            if name.endswith(("sheet2.xml", "sheet5.xml")) and vals.get("A") in {"M1", "M2", "M3"}:
                put(cells["I" if name.endswith("sheet2.xml") else "H"], "complete (T3 evidence)")
            for cell in cells.values():
                original = value(cell)
                corrected = original.replace("ADR-0009", "ADR-0011").replace("docs/adr/0009-*.md", "docs/adr/0011-*.md")
                corrected = corrected.replace("all 51 IDs", "all 53 IDs").replace("51 assertions executed", "53 assertions executed")
                if corrected != original:
                    put(cell, corrected)
        content[name] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    temporary = workbook.with_suffix(".xlsx.tmp")
    with ZipFile(temporary, "w") as archive:
        for info in infos:
            archive.writestr(info, content[info.filename])
    temporary.replace(workbook)
    return completed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=ROOT / "docs/evolution/evidence-notation/T3/results.json")
    args = parser.parse_args(argv)
    completed = update(ROOT / "docs/evolution/roadmap-notation.xlsx", args.results.resolve())
    print(f"Advanced {len(completed)} roadmap items: {', '.join(completed)}")


if __name__ == "__main__":
    main()

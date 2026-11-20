#!/usr/bin/env python3
"""Turn the text of an FAA ACS PDF into structured JSON.

Usage:
    pdftotext -layout private_airplane_acs_6.pdf acs.txt
    python3 scripts/parse_acs.py acs.txt data/acs/private-airplane-6c.json \
        --prefix PA --doc FAA-S-ACS-6C --name "Private Pilot - Airplane"

Output shape:
    {certificate, areas: [{numeral, name, tasks: [{letter, code, name, classes,
      references, objective, notes, elements: [{code, type, text, parent}]}]}]}

Designed to work for other ACS documents (Instrument, Commercial...) by
changing --prefix, since they share the same layout.
"""
import argparse
import json
import re
import sys

AREA_RE = re.compile(r"^Area of Operation ([IVXL]+)\. (.+?)\s*$")
TASK_RE = re.compile(r"^Task ([A-Z])\. (.+?)\s*$")
FOOTER_RE = re.compile(r"ACS \(FAA-S-ACS-[\w-]+\)\s+[\divxlc]+\s*$")
CLASS_RE = re.compile(r"\(((?:ASEL|AMEL|ASES|AMES)(?:,\s*(?:ASEL|AMEL|ASES|AMES))*)\)")
TYPE_NAMES = {"K": "knowledge", "R": "risk_management", "S": "skill"}


def parse(lines, prefix):
    elem_re = re.compile(
        r"^\s+(" + prefix + r"\.([IVXL]+)\.([A-Z])\.([KRS])(\d+)([a-z]?))\s+(.*?)\s*$"
    )
    areas, area, task, last_elem, field = [], None, None, None, None

    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or FOOTER_RE.search(line):
            continue

        m = AREA_RE.match(stripped)
        if m:
            numeral, name = m.group(1), m.group(2)
            # Page headers repeat the area name; only a new numeral starts a new area.
            if area is None or area["numeral"] != numeral:
                area = {"numeral": numeral, "name": name, "tasks": []}
                areas.append(area)
            field = None
            continue

        m = TASK_RE.match(stripped)
        if m and area is not None:
            letter, name = m.group(1), m.group(2)
            classes = []
            cm = CLASS_RE.search(name)
            if cm:
                classes = [c.strip() for c in cm.group(1).split(",")]
            task = {
                "letter": letter,
                "code": f"{prefix}.{area['numeral']}.{letter}",
                "name": name,
                "classes": classes,
                "references": "",
                "objective": "",
                "notes": [],
                "elements": [],
            }
            area["tasks"].append(task)
            last_elem, field = None, "task_name"
            continue

        if task is None:
            continue

        m = elem_re.match(line)
        if m:
            code, num, ttype, sub, text = m.group(1), m.group(5), m.group(4), m.group(6), m.group(7)
            parent = None
            if sub:
                parent = code[:-1]
                text = re.sub(r"^[a-z]\.\s+", "", text)
            last_elem = {"code": code, "type": TYPE_NAMES[ttype], "text": text, "parent": parent}
            task["elements"].append(last_elem)
            field = "element"
            continue

        if stripped.startswith("References:"):
            task["references"] = stripped[len("References:"):].strip()
            field = "references"
        elif stripped.startswith("Objective:"):
            task["objective"] = stripped[len("Objective:"):].strip()
            field = "objective"
        elif stripped.startswith("Note:"):
            task["notes"].append(stripped[len("Note:"):].strip())
            field = "note"
        elif stripped.startswith(("Knowledge:", "Risk", "Management:", "Skills:")):
            field = None
        elif field == "task_name":
            # Long task titles wrap onto a second line.
            task["name"] = join(task["name"], stripped)
        elif field == "element" and last_elem is not None:
            last_elem["text"] = join(last_elem["text"], stripped)
        elif field == "objective":
            task["objective"] = join(task["objective"], stripped)
        elif field == "references":
            task["references"] = join(task["references"], stripped)
        elif field == "note" and task["notes"]:
            task["notes"][-1] = join(task["notes"][-1], stripped)

    return areas


def join(a, b):
    """Join a wrapped line, keeping hyphenated words together ("Straight-" + "and-Level")."""
    return a + b if a.endswith("-") else a + " " + b


def tidy(text):
    return re.sub(r"\s+", " ", text).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text_file")
    ap.add_argument("out_file")
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--doc", required=True)
    ap.add_argument("--name", required=True)
    args = ap.parse_args()

    with open(args.text_file, encoding="utf-8") as f:
        lines = f.readlines()
    # The body starts at the Area heading just before the first "References:" line
    # (everything earlier is the cover, foreword and table of contents) and ends
    # at the first appendix.
    first_ref = next(i for i, l in enumerate(lines) if l.strip().startswith("References:"))
    start = max(i for i in range(first_ref) if AREA_RE.match(lines[i].strip()))
    end = next((i for i in range(start, len(lines)) if lines[i].lstrip("\f").startswith("Appendix 1")), len(lines))
    areas = parse(lines[start:end], args.prefix)

    for a in areas:
        for t in a["tasks"]:
            t["name"] = tidy(t["name"])
            cm = CLASS_RE.search(t["name"])
            t["classes"] = [c.strip() for c in cm.group(1).split(",")] if cm else []
            t["objective"] = tidy(t["objective"])
            t["references"] = tidy(t["references"])
            t["notes"] = [tidy(n) for n in t["notes"]]
            for e in t["elements"]:
                e["text"] = tidy(e["text"])

    out = {
        "certificate": {"code": args.prefix, "name": args.name, "acs_document": args.doc},
        "areas": areas,
    }
    with open(args.out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    n_tasks = sum(len(a["tasks"]) for a in areas)
    n_elems = sum(len(t["elements"]) for a in areas for t in a["tasks"])
    print(f"{len(areas)} areas, {n_tasks} tasks, {n_elems} elements", file=sys.stderr)


if __name__ == "__main__":
    main()

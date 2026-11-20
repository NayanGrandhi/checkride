#!/usr/bin/env python3
"""Build the FAA reference library: split official FAA documents into short,
citable passages.

Usage:
    python3 scripts/build_library.py <source_dir> data/library

<source_dir> must contain (names as downloaded, renamed):
    phak.pdf  afh.pdf  avwx.pdf  aim.pdf  cug.pdf  cfr61.xml  cfr91.xml

Output:
    data/library/documents.json        one entry per source document
    data/library/passages.jsonl.gz     one JSON object per passage:
        {id, document_id, locator, page_label, section, content}

Every passage keeps the document's own wording (only whitespace and dash
characters are normalised), so a quote taken from a passage can be checked
word for word against it. That check is what stops invented citations.
"""
import gzip
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

import pypdf

DOCUMENTS = [
    {"id": "phak", "short_name": "PHAK", "title": "Pilot's Handbook of Aeronautical Knowledge",
     "doc_number": "FAA-H-8083-25C", "file": "phak.pdf", "kind": "chapters",
     "url": "https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/phak"},
    {"id": "afh", "short_name": "AFH", "title": "Airplane Flying Handbook",
     "doc_number": "FAA-H-8083-3C", "file": "afh.pdf", "kind": "chapters",
     "url": "https://www.faa.gov/regulations_policies/handbooks_manuals/aviation/airplane_handbook"},
    {"id": "avwx", "short_name": "Aviation Weather Handbook", "title": "Aviation Weather Handbook",
     "doc_number": "FAA-H-8083-28B", "file": "avwx.pdf", "kind": "outline",
     "url": "https://www.faa.gov/regulationspolicies/handbooksmanuals/aviation/faa-h-8083-28-aviation-weather-handbook"},
    {"id": "aim", "short_name": "AIM", "title": "Aeronautical Information Manual",
     "doc_number": "AIM Basic with Change 3 (July 9, 2026)", "file": "aim.pdf", "kind": "aim",
     "url": "https://www.faa.gov/air_traffic/publications/atpubs/aim_html/"},
    {"id": "cug", "short_name": "Chart Users' Guide", "title": "Aeronautical Chart Users' Guide",
     "doc_number": "Edition dated July 9, 2026", "file": "cug.pdf", "kind": "outline",
     "url": "https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/aero_guide"},
    {"id": "cfr61", "short_name": "14 CFR Part 61", "title": "14 CFR Part 61: Certification: Pilots, Flight Instructors, and Ground Instructors",
     "doc_number": "eCFR, current as of 2026-11-18", "file": "cfr61.xml", "kind": "cfr",
     "url": "https://www.ecfr.gov/current/title-14/part-61"},
    {"id": "cfr91", "short_name": "14 CFR Part 91", "title": "14 CFR Part 91: General Operating and Flight Rules",
     "doc_number": "eCFR, current as of 2026-11-18", "file": "cfr91.xml", "kind": "cfr",
     "url": "https://www.ecfr.gov/current/title-14/part-91"},
]

TARGET = 1100   # aim for passages of about this many characters
MAX = 1800      # never exceed this (long paragraphs are split at sentences)
MIN = 250       # merge anything shorter into its neighbour

PAGE_LABEL_RE = re.compile(r"^(?:[A-Z]-\d{1,3}|\d{1,2}-\d{1,2}-\d{1,3}|\d{1,2}-\d{1,3}|\d{1,3})$")
CHAPTER_LABEL_RE = re.compile(r"^(?:\d{1,2}|[A-Z])-\d{1,3}$")
AIM_HEAD_LINE_RE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{1,2})\.\s+(\S.*)$")
AIM_PARA_RE = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{1,2})\.\s+(\S.{2,120})$")


def norm(s):
    """Normalise characters that differ between PDF text and what people type."""
    return (s.replace("−", "-").replace("‐", "-").replace("‑", "-")
             .replace("­", "").replace("ﬁ", "fi").replace("ﬂ", "fl"))


def join_lines(lines):
    """Join wrapped lines into one paragraph, keeping hyphenated words whole."""
    out = ""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not out:
            out = line
        elif out.endswith("-") and not out.endswith(" -"):
            out += line
        else:
            out += " " + line
    return re.sub(r"\s+", " ", out).strip()


def paragraphs(page_text):
    """Split one page into paragraphs (blank-line separated, then joined)."""
    blocks, cur = [], []
    for line in page_text.splitlines():
        if line.strip():
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    return blocks


def split_long(text):
    if len(text) <= MAX:
        return [text]
    sentences = re.split(r"(?<=[.;:?!])\s+(?=[A-Z(\[\"])", text)
    parts, cur = [], ""
    for s in sentences:
        if cur and len(cur) + 1 + len(s) > TARGET:
            parts.append(cur)
            cur = s
        else:
            cur = (cur + " " + s).strip()
    if cur:
        parts.append(cur)
    # a single enormous "sentence" (tables): hard split on words
    final = []
    for p in parts:
        while len(p) > MAX:
            cut = p.rfind(" ", 0, TARGET)
            cut = cut if cut > 0 else TARGET
            final.append(p[:cut].strip())
            p = p[cut:].strip()
        final.append(p)
    return final


def pack(paras):
    """Group paragraphs into passages of roughly TARGET characters."""
    pieces = [p for para in paras for p in split_long(para)]
    out, cur = [], ""
    for p in pieces:
        if cur and len(cur) + 1 + len(p) > TARGET:
            out.append(cur)
            cur = p
        else:
            cur = (cur + "\n" + p).strip()
    if cur:
        out.append(cur)
    if len(out) > 1 and len(out[-1]) < MIN:
        last = out.pop()
        out[-1] = out[-1] + "\n" + last
    return out


def pdf_pages(path):
    raw = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True, check=True).stdout
    return [norm(p) for p in raw.split("\f")]


def page_label(lines):
    for line in reversed(lines[-4:]):
        s = line.strip()
        if PAGE_LABEL_RE.match(s):
            return s
    return None


def outline_entries(path):
    r = pypdf.PdfReader(path)
    out = []

    def walk(items):
        for it in items:
            if isinstance(it, list):
                walk(it)
            else:
                try:
                    out.append((r.get_destination_page_number(it), norm(it.title.strip())))
                except Exception:
                    pass

    walk(r.outline)
    return sorted(out)


def toc_chapter_titles(pages):
    """Chapter titles as listed in the front-matter table of contents."""
    front = "\n".join(pages[:30])
    titles = {}
    for m in re.finditer(r"Chapter (\d+)[:\s]+([A-Z][^\n]*?)\s*\.{3,}", front):
        titles.setdefault(int(m.group(1)), re.sub(r"\s+", " ", m.group(2)).strip())
    for page in pages:  # running headers like "Chapter 1: Introduction to Flight Training"
        for m in re.finditer(r"^Chapter (\d+): (.{3,80})$", page, re.M):
            titles.setdefault(int(m.group(1)), m.group(2).strip())
    return titles


def chapter_page_labels(pages):
    """Printed page labels (e.g. '7-41') for chaptered books.

    pdftotext sometimes puts the page number mid-page, so look anywhere, prefer
    a label in the last lines, and fill gaps from the neighbouring pages.
    """
    def parse(l):
        a, b = l.split("-")
        return a, int(b)

    labels = []
    for text in pages:
        nonblank = [l.strip() for l in text.splitlines() if l.strip()]
        tail = [l for l in nonblank[-4:] if CHAPTER_LABEL_RE.match(l)]
        anywhere = [l for l in nonblank if CHAPTER_LABEL_RE.match(l)]
        labels.append(tail[-1] if tail else (anywhere[0] if len(anywhere) == 1 else None))
    # fill a single missing page between two labels of the same chapter
    for i in range(1, len(labels) - 1):
        if labels[i] is None and labels[i - 1] and labels[i + 1]:
            (c1, n1), (c2, n2) = parse(labels[i - 1]), parse(labels[i + 1])
            if c1 == c2 and n2 - n1 == 2:
                labels[i] = f"{c1}-{n1 + 1}"
    # sanity: a label must be one more than the previous page in the same chapter
    for i in range(1, len(labels)):
        if labels[i] and labels[i - 1]:
            (c1, n1), (c2, n2) = parse(labels[i - 1]), parse(labels[i])
            if c1 == c2 and n2 != n1 + 1 and i + 1 < len(labels) and labels[i + 1]:
                c3, n3 = parse(labels[i + 1])
                if c3 == c1 and n3 == n1 + 2:
                    labels[i] = f"{c1}-{n1 + 1}"
    return labels


def clean_lines(lines, header_patterns):
    out = []
    for line in lines:
        s = line.strip()
        if PAGE_LABEL_RE.match(s):
            continue
        if any(p.match(s) for p in header_patterns):
            continue
        out.append(line)
    return out


def build_pdf(doc, src):
    pages = pdf_pages(os.path.join(src, doc["file"]))
    kind = doc["kind"]
    passages = []
    outline = outline_entries(os.path.join(src, doc["file"])) if kind == "outline" else []
    chapter_titles = toc_chapter_titles(pages) if kind == "chapters" else {}
    chapter_labels = chapter_page_labels(pages) if kind == "chapters" else None
    aim_para = None
    aim_started = False

    headers = [
        re.compile(r"^Chapter \d+[,:] .{3,90}$"),          # running headers / footers
        re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$"),            # AIM page dates
        re.compile(r"^AIM$"),
        re.compile(r"^Airplane Flying Handbook \(FAA-H-8083-3C\)$"),
        re.compile(r"^(Figure|Table|FIG|TBL) [\dA-Z]+-[\d-]+\.?.{0,120}$"),
    ]

    def emit(paras, label, section, aim_heading=None):
        for content in pack(paras):
            if len(content) < 80:
                continue
            if kind == "aim":
                num, _, title = aim_heading.partition(". ")
                if label and num.split("-")[0] != label.split("-")[0]:
                    continue  # chapter title pages and the index at the back

                locator = f"AIM {num}, {title}" + (f" (p. {label})" if label else "")
                sec = aim_heading
            elif kind == "chapters":
                short = section.split(",")[0] if section.startswith("Ch.") else section
                locator = f"{doc['short_name']} {short}, p. {label}"
                sec = section
            else:
                locator = f"{doc['short_name']}, {section}, p. {label}" if section else f"{doc['short_name']}, p. {label}"
                sec = section
            passages.append({"document_id": doc["id"], "locator": locator, "page_label": label,
                             "section": sec, "content": content})

    for i, text in enumerate(pages):
        lines = text.splitlines()
        nonblank = [l for l in lines if l.strip()]
        if len(nonblank) < 4:
            continue
        label = chapter_labels[i] if kind == "chapters" else page_label(nonblank)

        # skip table-of-contents style pages (dotted leaders)
        leaders = sum(1 for l in nonblank if re.search(r"(\. ){4,}|\.{5,}", l))
        if leaders >= max(3, len(nonblank) // 5):
            continue
        if kind == "aim" and not aim_started:
            if label != "1-1-1":
                continue  # change notices and front matter before Chapter 1
            aim_started = True

        if kind in ("chapters", "outline") and not label:
            continue  # cover, table of contents, blank pages
        if label and label.startswith("I-"):
            continue  # index pages: nothing worth citing

        if kind == "aim" and label:
            # drop the page label and the running section title printed after it
            for k in range(len(lines) - 1, -1, -1):
                if lines[k].strip() == label:
                    lines = lines[:k]
                    break

        if kind == "chapters":
            head = label.split("-")[0]
            if head.isdigit():
                ch = int(head)
                section = f"Ch. {ch}" + (f", {chapter_titles[ch]}" if ch in chapter_titles else "")
            else:
                section = {"G": "Glossary", "A": "Appendix"}.get(head, "Front matter")
        elif kind == "outline":
            prior = [t for p, t in outline if p <= i]
            section = prior[-1] if prior else ""
        else:
            section = ""

        body = clean_lines(lines, headers)

        if kind == "aim":
            # split at paragraph headings like "2-3-5. Holding Position Markings"
            groups, cur_head, cur = [], aim_para, []
            for block in paragraphs("\n".join(body)):
                buf = []
                for line in block:
                    m = AIM_HEAD_LINE_RE.match(line.strip())
                    if m and len(line.strip()) < 130:
                        if buf:
                            cur.append(join_lines(buf))
                            buf = []
                        if cur and cur_head:
                            groups.append((cur_head, cur))
                        cur_head = f"{m.group(1)}-{m.group(2)}-{m.group(3)}. {m.group(4).strip()}"
                        cur = []
                    else:
                        buf.append(line)
                if buf:
                    cur.append(join_lines(buf))
            if cur and cur_head:
                groups.append((cur_head, cur))
            aim_para = cur_head
            for heading, paras in groups:
                emit([p for p in paras if len(p) >= 3], label, "", heading)
            continue

        paras = [j for j in (join_lines(b) for b in paragraphs("\n".join(body))) if len(j) >= 3]
        emit(paras, label, section)
    return passages


def build_cfr(doc, src):
    tree = ET.parse(os.path.join(src, doc["file"]))
    passages = []
    for sec in tree.iter("DIV8"):
        if sec.get("TYPE") != "SECTION":
            continue
        head_el = sec.find("HEAD")
        head = norm(" ".join(head_el.itertext()).strip()) if head_el is not None else ""
        num = sec.get("N", "").strip()
        paras = []
        for el in sec:
            if el.tag in ("P", "FP"):
                t = norm(re.sub(r"\s+", " ", "".join(el.itertext())).strip())
                if t:
                    paras.append(t)
        if not paras or "[Reserved]" in head:
            continue
        title = re.sub(r"^§\s*[\d.]+\s*", "", head).strip()
        for content in pack(paras):
            passages.append({"document_id": doc["id"], "locator": f"14 CFR § {num}", "page_label": None,
                             "section": f"§ {num} {title}", "content": content})
    return passages


def main():
    src, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    all_passages, docs_out = [], []
    for doc in DOCUMENTS:
        ps = build_cfr(doc, src) if doc["kind"] == "cfr" else build_pdf(doc, src)
        for n, p in enumerate(ps, 1):
            p["id"] = f"{doc['id']}-{n:05d}"
        all_passages.extend(ps)
        docs_out.append({k: doc[k] for k in ("id", "short_name", "title", "doc_number", "url")})
        print(f"{doc['id']:6s} {len(ps):5d} passages, {sum(len(p['content']) for p in ps):,} chars", file=sys.stderr)

    with open(os.path.join(out_dir, "documents.json"), "w", encoding="utf-8") as f:
        json.dump(docs_out, f, indent=2, ensure_ascii=False)
    with gzip.open(os.path.join(out_dir, "passages.jsonl.gz"), "wt", encoding="utf-8") as f:
        for p in all_passages:
            f.write(json.dumps({k: p[k] for k in ("id", "document_id", "locator", "page_label", "section", "content")},
                               ensure_ascii=False) + "\n")
    print(f"total  {len(all_passages):5d} passages", file=sys.stderr)


if __name__ == "__main__":
    main()

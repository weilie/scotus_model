from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
try:
    from slugify import slugify
except Exception:
    def slugify(value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        return value.strip("-")
from tqdm import tqdm

BASE = "https://www.supremecourt.gov"
UA = "scotus-jackson-court-corpus-builder/0.1 (+research; contact: local-user)"


@dataclass
class DocumentRef:
    doc_type: str
    label: str
    url: str
    source_page: str
    local_path: Optional[str] = None
    sha256: Optional[str] = None
    status: str = "pending"
    error: Optional[str] = None


@dataclass
class CaseRecord:
    term: int
    docket: str
    name: str
    slug: str
    docket_url: str
    opinion_url: Optional[str] = None
    decision_date: Optional[str] = None
    argument_date: Optional[str] = None
    transcript_page_url: Optional[str] = None
    lower_court: Optional[str] = None
    questions_presented: Optional[str] = None
    questions_presented_url: Optional[str] = None
    documents: list[DocumentRef] = field(default_factory=list)


def get(url: str, *, timeout: int = 45) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_name(url: str, default: str) -> str:
    name = Path(urlparse(url).path).name
    if not name or "." not in name:
        name = default
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:180]


def download(url: str, dest: Path, *, force: bool = False, sleep: float = 0.15) -> tuple[str, str, Optional[str]]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force and dest.stat().st_size > 0:
        return "skipped", sha256_file(dest), None
    try:
        time.sleep(sleep)
        r = get(url, timeout=90)
        dest.write_bytes(r.content)
        return "downloaded", sha256_file(dest), None
    except Exception as e:
        return "error", "", str(e)


def parse_opinion_term(term: int) -> list[dict]:
    """Return docket/name/opinion href/date records from the term slip-opinion page."""
    url = f"{BASE}/opinions/slipopinion/{term % 100:02d}"
    soup = BeautifulSoup(get(url).text, "lxml")
    text = soup.get_text("\n")
    rows: list[dict] = []
    # Most links are the opinion PDFs; nearby table text has date/docket/name.
    for a in soup.find_all("a", href=True):
        href = a["href"]
        label = a.get_text(" ", strip=True)
        if "/opinions/" not in href or not href.lower().endswith(".pdf"):
            continue
        # Use parent row if present; otherwise preceding text around link.
        row_text = a.find_parent("tr").get_text(" ", strip=True) if a.find_parent("tr") else a.parent.get_text(" ", strip=True)
        if not row_text or label not in row_text:
            row_text = label
        docket_match = re.search(r"\b(\d{1,3}-\d{1,5}|\d+-Orig\.?|\d+O\d*)\b", row_text)
        date_match = re.search(r"\b\d{1,2}/\d{1,2}/\d{2}\b", row_text)
        if docket_match:
            rows.append({
                "term": term,
                "docket": docket_match.group(1).replace(".", ""),
                "name": label,
                "decision_date": date_match.group(0) if date_match else None,
                "opinion_url": urljoin(BASE, href),
                "source_page": url,
            })
    # Fallback for pages rendered as text/table with link labels only.
    if not rows:
        for m in re.finditer(r"(\d{1,2}/\d{1,2}/\d{2})\s+(\d{1,3}-\d{1,5})\s+(.+?)\s+[A-Z]{1,3}\s+\d+", text):
            rows.append({"term": term, "docket": m.group(2), "name": m.group(3), "decision_date": m.group(1), "opinion_url": None, "source_page": url})
    return dedupe_dicts(rows, key=lambda r: (r["term"], r["docket"], r["name"]))


def parse_transcript_term(term: int) -> list[dict]:
    url = f"{BASE}/oral_arguments/argument_transcript/{term}"
    soup = BeautifulSoup(get(url).text, "lxml")
    rows: list[dict] = []
    for a in soup.find_all("a", href=True):
        docket = a.get_text(" ", strip=True)
        if not re.fullmatch(r"\d{1,3}-\d{1,5}|\d+-Orig\.?", docket):
            continue
        parent = a.find_parent("tr") or a.parent
        row_text = parent.get_text(" ", strip=True)
        # Usually: docket case name date
        date_match = re.search(r"\b\d{1,2}/\d{1,2}/\d{2}\b", row_text)
        name = row_text.replace(docket, "", 1)
        if date_match:
            name = name.replace(date_match.group(0), "")
        name = re.sub(r"\s+", " ", name).strip(" -–|")
        rows.append({
            "term": term,
            "docket": docket.replace(".", ""),
            "name": name,
            "argument_date": date_match.group(0) if date_match else None,
            "transcript_pdf_url": urljoin(BASE, a["href"]),
            "source_page": url,
        })
    return dedupe_dicts(rows, key=lambda r: (r["term"], r["docket"]))


def docket_url(docket: str) -> str:
    return f"{BASE}/search.aspx?filename=/docket/docketfiles/html/public/{docket}.html"


def is_case_document_link(href: str) -> bool:
    parsed_path = urlparse(href).path.lower()
    if not parsed_path.endswith(".pdf"):
        return False
    return "/docketpdf/" in parsed_path or "/qp/" in parsed_path


def parse_docket_page(html: str, url: str) -> tuple[dict, list[DocumentRef]]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    meta: dict = {}
    m = re.search(r"Title:\s*(.+?)\s+Docketed:", text, re.S)
    if m:
        meta["title"] = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r"Lower Ct:\s*(.+?)\s+Case Numbers:", text, re.S)
    if m:
        meta["lower_court"] = re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r"Questions Presented\s*(.+?)\s+Proceedings and Orders", text, re.S)
    if m:
        q = re.sub(r"\s+", " ", m.group(1)).strip()
        meta["questions_presented"] = q if q else None

    docs: list[DocumentRef] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not is_case_document_link(href):
            continue
        abs_url = urljoin(BASE, href)
        label = a.get_text(" ", strip=True) or "document"
        if "/qp/" in urlparse(href).path.lower():
            meta["questions_presented_url"] = abs_url
        # Context: current row/list item is the filing event.
        parent = a.find_parent("tr") or a.find_parent("p") or a.parent
        context = parent.get_text(" ", strip=True) if parent else label
        doc_type = classify_document(label, context)
        docs.append(DocumentRef(doc_type=doc_type, label=context[:500], url=abs_url, source_page=url))
    return meta, dedupe_docs(docs)


def classify_document(label: str, context: str) -> str:
    label_s = label.lower()
    s = f"{label} {context}".lower()
    if "/qp/" in s or label_s == "questions presented":
        return "questions_presented"
    if "certificate" in label_s or "word count" in label_s:
        return "certificate"
    if "proof of service" in label_s:
        return "proof_of_service"
    if "joint appendix" in s:
        return "joint_appendix"
    if "petition for a writ" in s or label_s == "petition":
        return "cert_petition"
    if "brief of petitioners" in s or "brief for petitioner" in s:
        return "merits_brief_petitioner"
    if "brief of respondents" in s or "brief for respondent" in s:
        return "merits_brief_respondent"
    if "reply" in s:
        return "reply_brief"
    if "amic" in s:
        return "amicus_brief"
    if "certificate" in s:
        return "certificate"
    if "proof of service" in s:
        return "proof_of_service"
    if "motion" in s:
        return "motion"
    if "transcript" in s:
        return "oral_argument_transcript"
    return "filing"


def dedupe_docs(docs: list[DocumentRef]) -> list[DocumentRef]:
    seen = set(); out=[]
    for d in docs:
        if d.url in seen: continue
        seen.add(d.url); out.append(d)
    return out


def dedupe_dicts(rows: list[dict], key) -> list[dict]:
    seen=set(); out=[]
    for r in rows:
        k=key(r)
        if k in seen: continue
        seen.add(k); out.append(r)
    return out


def build_case_index(terms: Iterable[int]) -> list[CaseRecord]:
    by_key: dict[tuple[int,str], CaseRecord] = {}
    for term in terms:
        for r in parse_opinion_term(term):
            name = r["name"]
            d = r["docket"]
            slug = f"{d}_{slugify(name)[:80]}"
            by_key[(term,d)] = CaseRecord(term=term, docket=d, name=name, slug=slug, docket_url=docket_url(d), opinion_url=r.get("opinion_url"), decision_date=r.get("decision_date"))
        for r in parse_transcript_term(term):
            d = r["docket"]
            rec = by_key.get((term,d))
            if not rec:
                name = r["name"] or d
                rec = CaseRecord(term=term, docket=d, name=name, slug=f"{d}_{slugify(name)[:80]}", docket_url=docket_url(d))
                by_key[(term,d)] = rec
            rec.argument_date = r.get("argument_date") or rec.argument_date
            if r.get("transcript_pdf_url"):
                rec.documents.append(DocumentRef("oral_argument_transcript", "Official oral argument transcript", r["transcript_pdf_url"], r["source_page"]))
    return list(by_key.values())


def case_dir(root: Path, rec: CaseRecord) -> Path:
    return root / "cases" / str(rec.term) / rec.slug


def relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root))


def add_audio_links(rec: CaseRecord) -> None:
    # The audio detail page is stable for modern terms and dockets.
    audio_page = f"{BASE}/oral_arguments/audio/{rec.term}/{rec.docket}"
    try:
        soup = BeautifulSoup(get(audio_page).text, "lxml")
    except Exception:
        return
    for a in soup.find_all("a", href=True):
        label = a.get_text(" ", strip=True).lower()
        href = a["href"]
        abs_url = urljoin(BASE, href)
        if "download" in label or href.lower().endswith(".mp3"):
            rec.documents.append(DocumentRef("oral_argument_audio", "Official oral argument audio", abs_url, audio_page))
        elif "view" in label and href.lower().endswith(".pdf"):
            rec.documents.append(DocumentRef("oral_argument_transcript", "Official oral argument transcript", abs_url, audio_page))
    rec.documents = dedupe_docs(rec.documents)


def extract_pdf_text(pdf_path: Path, txt_path: Path) -> bool:
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        text = []
        for i, page in enumerate(reader.pages):
            text.append(f"\n\n--- page {i+1} ---\n")
            text.append(page.extract_text() or "")
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text("".join(text), encoding="utf-8")
        return True
    except Exception:
        return False


def write_case(root: Path, rec: CaseRecord, *, metadata_only=False, extract_text=False, force=False) -> list[dict]:
    cdir = case_dir(root, rec)
    cdir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    # Docket html + links
    try:
        r = get(rec.docket_url)
        (cdir / "docket.html").write_text(r.text, encoding="utf-8")
        docket_meta, docket_docs = parse_docket_page(r.text, rec.docket_url)
        rec.lower_court = docket_meta.get("lower_court") or rec.lower_court
        rec.questions_presented = docket_meta.get("questions_presented") or rec.questions_presented
        rec.questions_presented_url = docket_meta.get("questions_presented_url") or rec.questions_presented_url
        rec.documents.extend(docket_docs)
        rec.documents = dedupe_docs(rec.documents)
    except Exception as e:
        manifest.append({"case": rec.docket, "doc_type": "docket_html", "url": rec.docket_url, "status": "error", "error": str(e)})

    if rec.opinion_url:
        rec.documents.append(DocumentRef("slip_opinion", "Slip opinion", rec.opinion_url, f"{BASE}/opinions/slipopinion/{rec.term % 100:02d}"))
    add_audio_links(rec)
    rec.documents = dedupe_docs(rec.documents)

    for d in rec.documents:
        sub = folder_for_doc_type(d.doc_type)
        ext = Path(urlparse(d.url).path).suffix.lower() or ".bin"
        filename = safe_name(d.url, f"{slugify(d.doc_type)}{ext}")
        dest = cdir / sub / filename
        d.local_path = relative(dest, root)
        if metadata_only:
            d.status = "metadata_only"
        else:
            status, digest, err = download(d.url, dest, force=force)
            d.status = status; d.sha256 = digest or None; d.error = err
            if extract_text and status in {"downloaded", "skipped"} and dest.suffix.lower() == ".pdf":
                txt_dest = cdir / "extracted_text" / f"{sub.replace('/', '_')}__{dest.stem}.txt"
                extract_pdf_text(dest, txt_dest)
        manifest.append({"term": rec.term, "docket": rec.docket, **asdict(d)})

    # Store metadata after docs have local paths/hashes.
    (cdir / "metadata.json").write_text(json.dumps(asdict(rec), indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def folder_for_doc_type(t: str) -> str:
    if t.startswith("oral_argument"):
        return "oral_argument"
    if t in {"slip_opinion", "syllabus", "opinion"}:
        return "opinions"
    if t == "questions_presented":
        return "case_metadata"
    if "brief" in t or t in {"cert_petition", "joint_appendix"}:
        return "briefs_and_filings"
    if t in {"certificate", "proof_of_service"}:
        return "service_and_certificates"
    return "briefs_and_filings"


def write_cases_csv(root: Path, cases: list[CaseRecord]) -> None:
    fields = [
        "term",
        "docket",
        "name",
        "slug",
        "decision_date",
        "argument_date",
        "docket_url",
        "opinion_url",
        "lower_court",
        "questions_presented_url",
    ]
    with (root / "cases.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for c in cases:
            w.writerow({k: getattr(c, k) for k in fields})


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--terms", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    p.add_argument("--out", type=Path, default=Path("data/scotus-jackson-court"))
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--metadata-only", action="store_true")
    p.add_argument("--extract-text", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    cases = build_case_index(args.terms)
    if args.limit:
        cases = cases[: args.limit]
    all_manifest=[]
    for rec in tqdm(cases, desc="cases"):
        all_manifest.extend(write_case(args.out, rec, metadata_only=args.metadata_only, extract_text=args.extract_text, force=args.force))
    write_cases_csv(args.out, cases)
    with (args.out / "manifest.jsonl").open("w", encoding="utf-8") as f:
        for row in all_manifest:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(cases)} cases and {len(all_manifest)} document records to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

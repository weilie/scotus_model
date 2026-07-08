from scotus_corpus_builder.build_corpus import (
    CaseRecord,
    DocumentRef,
    classify_document,
    extract_pdf_text,
    folder_for_doc_type,
    is_case_document_link,
    parse_opinion_term,
    parse_transcript_term,
    parse_docket_page,
    write_case,
)


def test_classify_core_docs():
    assert classify_document("Main Document", "May 26 2022 Brief of petitioners 303 Creative LLC, et al. filed.") == "merits_brief_petitioner"
    assert classify_document("Main Document", "Aug 12 2022 Brief of respondents Aubrey Elenis, et al. filed.") == "merits_brief_respondent"
    assert classify_document("Main Document", "Sep 12 2022 Reply of petitioners 303 Creative LLC, et al. filed.") == "reply_brief"
    assert classify_document("Main Document", "Jun 02 2022 Brief amici curiae of Ethics and Public Policy Center, et al. filed.") == "amicus_brief"
    assert classify_document("Certificate of Word Count", "Sep 24 2021 Petition for a writ of certiorari filed.") == "certificate"
    assert classify_document("Proof of Service", "Sep 24 2021 Petition for a writ of certiorari filed.") == "proof_of_service"
    assert classify_document("Questions Presented", "Questions Presented") == "questions_presented"


def test_parse_actual_303_creative_docket_snippet():
    # Representative snippet from the real Supreme Court docket page for No. 21-476.
    html = '''
    <html><body>
    Docket for 21-476
    No. 21-476
    Title: 303 Creative LLC, et al., Petitioners v. Aubrey Elenis, et al.
    Docketed: September 28, 2021
    Lower Ct: United States Court of Appeals for the Tenth Circuit Case Numbers: (19-1413)
    Questions Presented Whether applying a public-accommodation law to compel an artist to speak or stay silent violates the Free Speech Clause of the First Amendment.
    Proceedings and Orders
    <p>May 26 2022 Brief of petitioners 303 Creative LLC, et al. filed.
      <a href="/DocketPDF/21/21-476/226928/petitioners.pdf">Main Document</a></p>
    <p>Aug 12 2022 Brief of respondents Aubrey Elenis, et al. filed.
      <a href="/DocketPDF/21/21-476/234020/respondents.pdf">Main Document</a></p>
    <p>Sep 12 2022 Reply of petitioners 303 Creative LLC, et al. filed.
      <a href="/DocketPDF/21/21-476/237000/reply.pdf">Main Document</a></p>
    <p><a href="/publicinfo/PIOServices.pdf">Services for News Media</a></p>
    <p><a href="/qp/21-00476qp.pdf">Questions Presented</a></p>
    </body></html>
    '''
    meta, docs = parse_docket_page(html, "https://www.supremecourt.gov/search.aspx?filename=/docket/docketfiles/html/public/21-476.html")
    assert "Tenth Circuit" in meta["lower_court"]
    assert "Free Speech Clause" in meta["questions_presented"]
    assert meta["questions_presented_url"] == "https://www.supremecourt.gov/qp/21-00476qp.pdf"
    types = {d.doc_type for d in docs}
    urls = {d.url for d in docs}
    assert {"merits_brief_petitioner", "merits_brief_respondent", "reply_brief", "questions_presented"}.issubset(types)
    assert "https://www.supremecourt.gov/publicinfo/PIOServices.pdf" not in urls


def test_docket_link_filter_only_accepts_case_pdfs():
    assert is_case_document_link("/DocketPDF/21/21-476/226928/petitioners.pdf")
    assert is_case_document_link("/qp/21-00476qp.pdf")
    assert not is_case_document_link("/publicinfo/PIOServices.pdf")
    assert not is_case_document_link("/DocketPDF/21/21-476/226928/readme.txt")


def test_attachment_labels_override_row_context():
    html = '''
    <html><body>
    <p>Sep 24 2021 Petition for a writ of certiorari filed.
      <a href="/DocketPDF/21/21-476/193619/petition.pdf">Petition</a>
      <a href="/DocketPDF/21/21-476/193619/certificate.pdf">Certificate of Word Count</a>
      <a href="/DocketPDF/21/21-476/193619/service.pdf">Proof of Service</a>
    </p>
    </body></html>
    '''
    _, docs = parse_docket_page(html, "https://www.supremecourt.gov/search.aspx?filename=/docket/docketfiles/html/public/21-476.html")
    by_url = {d.url.rsplit("/", 1)[-1]: d.doc_type for d in docs}
    assert by_url == {
        "petition.pdf": "cert_petition",
        "certificate.pdf": "certificate",
        "service.pdf": "proof_of_service",
    }


def test_questions_presented_folder():
    assert folder_for_doc_type("questions_presented") == "case_metadata"


def test_parse_opinion_term_skips_revision_diff_links(monkeypatch):
    html = '''
    <html><body>
    <table>
      <tr>
        <td>66</td><td>6/30/26</td><td>25-365</td>
        <td><a href="/opinions/25pdf/25-365_new_5if6.pdf">Trump v. Barbara</a></td>
      </tr>
      <tr>
        <td>Revisions:</td>
        <td><a href="/opinions/25pdf/25-365_diff_ed9g.pdf">7/01/26</a></td>
      </tr>
    </table>
    </body></html>
    '''

    class Response:
        text = html

    monkeypatch.setattr("scotus_corpus_builder.build_corpus.get", lambda url: Response())

    rows = parse_opinion_term(2025)
    assert rows == [
        {
            "term": 2025,
            "docket": "25-365",
            "name": "Trump v. Barbara",
            "decision_date": "6/30/26",
            "opinion_url": "https://www.supremecourt.gov/opinions/25pdf/25-365_new_5if6.pdf",
            "source_page": "https://www.supremecourt.gov/opinions/slipopinion/25",
        }
    ]


def test_parse_transcript_term_resolves_parent_relative_urls(monkeypatch):
    html = '''
    <html><body>
    <table>
      <tr>
        <td><a href="../argument_transcripts/2022/21-476_k43e.pdf">21-476</a></td>
        <td>303 Creative LLC v. Elenis</td>
        <td>12/05/22</td>
      </tr>
    </table>
    </body></html>
    '''

    class Response:
        text = html

    monkeypatch.setattr("scotus_corpus_builder.build_corpus.get", lambda url: Response())

    rows = parse_transcript_term(2022)
    assert rows[0]["transcript_pdf_url"] == "https://www.supremecourt.gov/oral_arguments/argument_transcripts/2022/21-476_k43e.pdf"


def test_extract_pdf_text_reports_failure(tmp_path):
    ok, err = extract_pdf_text(tmp_path / "missing.pdf", tmp_path / "out.txt")
    assert ok is False
    assert err


def test_write_case_skip_audio_keeps_transcript(monkeypatch, tmp_path):
    rec = CaseRecord(
        term=2022,
        docket="21-476",
        name="303 Creative LLC v. Elenis",
        slug="21-476_303-creative-llc-v-elenis",
        docket_url="https://www.supremecourt.gov/search.aspx?filename=/docket/docketfiles/html/public/21-476.html",
        documents=[
            DocumentRef(
                "oral_argument_transcript",
                "Official oral argument transcript",
                "https://www.supremecourt.gov/oral_arguments/argument_transcripts/2022/21-476_k43e.pdf",
                "https://www.supremecourt.gov/oral_arguments/argument_transcript/2022",
            ),
            DocumentRef(
                "oral_argument_audio",
                "Official oral argument audio",
                "https://www.supremecourt.gov/media/audio/mp3files/21-476.mp3",
                "https://www.supremecourt.gov/oral_arguments/audio/2022/21-476",
            ),
        ],
    )

    class Response:
        text = "<html><body></body></html>"

    monkeypatch.setattr("scotus_corpus_builder.build_corpus.get", lambda url: Response())
    monkeypatch.setattr("scotus_corpus_builder.build_corpus.add_audio_links", lambda rec: None)

    manifest = write_case(tmp_path, rec, metadata_only=True, skip_audio=True)
    assert [row["doc_type"] for row in manifest] == ["oral_argument_transcript"]


def test_write_case_text_only_discards_extracted_pdf(monkeypatch, tmp_path):
    rec = CaseRecord(
        term=2022,
        docket="21-476",
        name="303 Creative LLC v. Elenis",
        slug="21-476_303-creative-llc-v-elenis",
        docket_url="https://www.supremecourt.gov/search.aspx?filename=/docket/docketfiles/html/public/21-476.html",
        documents=[
            DocumentRef(
                "slip_opinion",
                "Slip opinion",
                "https://www.supremecourt.gov/opinions/22pdf/600us1r58_7khn.pdf",
                "https://www.supremecourt.gov/opinions/slipopinion/22",
            ),
        ],
    )

    class Response:
        text = "<html><body></body></html>"

    def fake_download(url, dest, *, force=False):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"%PDF test")
        return "downloaded", "abc123", None

    def fake_extract(pdf_path, txt_path):
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text("extracted", encoding="utf-8")
        return True, None

    monkeypatch.setattr("scotus_corpus_builder.build_corpus.get", lambda url: Response())
    monkeypatch.setattr("scotus_corpus_builder.build_corpus.add_audio_links", lambda rec: None)
    monkeypatch.setattr("scotus_corpus_builder.build_corpus.download", fake_download)
    monkeypatch.setattr("scotus_corpus_builder.build_corpus.extract_pdf_text", fake_extract)

    manifest = write_case(tmp_path, rec, extract_text=True, text_only=True)
    row = manifest[0]

    assert row["sha256"] == "abc123"
    assert row["local_path"] is None
    assert row["local_file_retained"] is False
    assert row["extraction_status"] == "extracted"
    assert row["extracted_text_path"]
    assert (tmp_path / row["extracted_text_path"]).read_text(encoding="utf-8") == "extracted"
    assert not list(tmp_path.rglob("*.pdf"))

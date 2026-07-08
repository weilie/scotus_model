from scotus_corpus_builder.build_corpus import (
    classify_document,
    folder_for_doc_type,
    is_case_document_link,
    parse_docket_page,
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

"""ATS readability audit. Confirmed = measurable document facts; heuristic = common-practice warnings.
No claim is made about how any specific employer ATS parses a document."""

def audit(p):
    out = []
    add = lambda kind, sev, title, detail, rec: out.append(dict(kind=kind, severity=sev, title=title, detail=detail, recommendation=rec))
    words = len(p["text"].split())
    if p["ocr_used"]:
        add("confirmed", "warning", "Text came from OCR", "The file had no embedded text, so OCR was used.", "Export the resume as a text-based PDF or DOCX from your editor.")
    if not p["email"]:
        add("confirmed", "warning", "No email address detected", "No email pattern was found in the text.", "Put a plain-text email near the top of the document.")
    if not p["phone"]:
        add("confirmed", "info", "No phone number detected", "No phone number pattern was found.", "Add a phone number as plain text if you want to be contacted by phone.")
    for key, label in (("experience", "Experience"), ("education", "Education"), ("skills", "Skills")):
        if key not in p["sections"]:
            add("heuristic", "warning", f"No '{label}' heading recognised", f"No standard heading for {label.lower()} was found; it may be missing or named unusually.", f"Use a conventional heading such as '{label}'. Other layouts can still be valid.")
    if p["unknown_headings"]:
        add("heuristic", "info", "Non-standard headings", "Unrecognised headings: " + ", ".join(p["unknown_headings"][:5]), "Consider common names (Experience, Education, Skills, Projects).")
    if not p["date_ranges"]:
        add("heuristic", "warning", "No date ranges detected", "No ranges like 'Jan 2021 - Present' were found.", "Show dates for roles and education in a consistent format.")
    if words < 150:
        add("confirmed", "warning", "Very little text", f"Only {words} words were extracted.", "Check that the file is not mostly images or graphics.")
    elif words > 1500:
        add("heuristic", "info", "Very long document", f"{words} words extracted.", "Consider trimming older or less relevant content.")
    if p["tables"]:
        add("heuristic", "info", "Tables detected", f"{p['tables']} table(s) found in the DOCX.", "Some parsers read tables out of order; verify the extracted text.")
    if p["pages"] and p["pages"] > config_pages():
        add("confirmed", "info", "Page limit for analysis", f"Only the first {config_pages()} pages were analysed.", "Shorten the document.")
    if not out:
        add("confirmed", "ok", "No readability problems detected", "Text extracted cleanly with standard sections.", "No action needed.")
    return out

def config_pages():
    from . import config
    return config.MAX_PAGES

import pytest
from samples import SAMPLE_TEXT, make_docx, make_pdf

from jobpilot.services.resume_parser import (
    ResumeParseError,
    detect_file_type,
    parse_resume,
    split_sections,
)


def test_split_sections_recognises_common_headings():
    sections = split_sections(SAMPLE_TEXT)
    assert [s.key for s in sections] == ["header", "summary", "experience", "education", "skills"]
    experience = sections[2]
    assert experience.heading == "Work Experience"
    assert "Built a billing service in Python." in experience.content
    assert sections[0].content == "Alex Example\nalex@example.com"


def test_heading_words_inside_sentences_are_not_headings():
    sections = split_sections("Summary\nI gained experience in education and skills training.")
    assert [s.key for s in sections] == ["summary"]


def test_text_without_headings_is_one_header_section():
    assert [s.key for s in split_sections("Just a name\nand a line")] == ["header"]


@pytest.mark.parametrize(
    ("filename", "data"),
    [
        ("resume.txt", SAMPLE_TEXT.encode()),
        ("resume.docx", make_docx(SAMPLE_TEXT.splitlines())),
        ("resume.pdf", make_pdf(SAMPLE_TEXT.splitlines())),
    ],
)
def test_parse_supported_formats(filename, data):
    file_type, text, sections = parse_resume(filename, data)
    assert file_type == filename.rsplit(".", 1)[1]
    assert "Example Corp, Software Engineer, 2021-2024" in text
    assert [s["key"] for s in sections] == [
        "header", "summary", "experience", "education", "skills",
    ]


def test_txt_falls_back_to_cp1252():
    _, text, _ = parse_resume("resume.txt", "Café Owner".encode("cp1252"))
    assert text == "Café Owner"


@pytest.mark.parametrize(
    ("filename", "data", "message"),
    [
        ("resume.exe", b"MZ", "Unsupported file type"),
        ("resume", b"text", "Unsupported file type"),
        ("resume.pdf", b"not a pdf", "not a valid PDF"),
        ("resume.docx", b"not a zip", "not a valid DOCX"),
        ("resume.docx", b"PK\x03\x04broken", "could not be read"),
        ("resume.pdf", b"%PDF-1.4 broken", "could not be read"),
        ("resume.txt", b"   \n\n  ", "No text found"),
        ("resume.pdf", make_pdf([]), "No text found"),
    ],
)
def test_invalid_files_raise_user_safe_errors(filename, data, message):
    with pytest.raises(ResumeParseError, match=message):
        parse_resume(filename, data)


def test_extension_is_case_insensitive():
    assert detect_file_type("CV.PDF", b"%PDF-1.7") == "pdf"

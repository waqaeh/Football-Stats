"""Splits the Laws of the Game PDF into chunks that each know where they came from (Law, section, page)."""
import re
from dataclasses import dataclass

from pypdf import PdfReader

MIN_WORDS = 40  # don't start a new chunk at a heading if the current one is shorter than this
TARGET_WORDS = 220  # small enough to be on one topic, big enough to keep a rule and its exceptions together
MAX_WORDS = 330  # split here even mid-sentence, e.g. in long bullet lists

LAW_TITLES = {
    1: "The Field of Play", 2: "The Ball", 3: "The Players", 4: "The Players’ Equipment", 5: "The Referee",
    6: "The Other Match Officials", 7: "The Duration of the Match", 8: "The Start and Restart of Play",
    9: "The Ball in and out of Play", 10: "Determining the Outcome of a Match", 11: "Offside",
    12: "Fouls and Misconduct", 13: "Free Kicks", 14: "The Penalty Kick", 15: "The Throw-in",
    16: "The Goal Kick", 17: "The Corner Kick",
}

# Running header near the top of most pages, e.g. "Laws of the Game 2026/27 | Law 12 | Fouls and Misconduct".
HEADER = re.compile(r"Laws of the Game \d{4}/\d{2}\s*\|\s*(?P<part>[^|]+?)(?:\s*\|.*)?$")
# Numbered sections inside a Law, e.g. "3. Disciplinary action".
SUBSECTION = re.compile(r"^(?P<number>\d{1,2})\.\s+(?P<title>[A-Z][^.]{2,70})$")


def is_heading(line: str, previous: str | None) -> bool:
    """A short line starting a new paragraph, e.g. "Denying a goal or an obvious goal-scoring opportunity (DOGSO)"."""
    return (
        len(line) <= 70
        and line[0].isupper()
        and not line.endswith((".", ",", ";", ":"))
        and (previous is None or previous.endswith((".", ":")))
    )


@dataclass
class Chunk:
    section: str  # e.g. "Law 12 – Fouls and Misconduct"
    subsection: str | None  # e.g. "3. Disciplinary action"
    page: int
    content: str


# Sections left out of the index. "Law changes" shows amendments with the old wording struck through, and PDF
# text extraction can't tell struck-through text from current text, so it would feed the model deleted rules.
SKIPPED_SECTIONS = {"Contents", "Law changes 2026/27"}


def section_name(part: str) -> str:
    match = re.fullmatch(r"Law (\d{1,2})", part)
    if match:
        return f"Law {match[1]} – {LAW_TITLES[int(match[1])]}"
    return "VAR protocol" if "(VAR) protocol" in part else part  # the PDF uses both names for one section


def read_pages(pdf_path: str) -> list[str]:
    return [page.extract_text() or "" for page in PdfReader(pdf_path).pages]


def chunk_pages(pages: list[str]) -> list[Chunk]:
    chunks: list[Chunk] = []
    section, subsection, subsection_number = "About the Laws", None, 0
    words: list[str] = []
    start_page = 1

    def flush():
        nonlocal words
        if len(words) >= 15 and section not in SKIPPED_SECTIONS:  # skip fragments like a lone heading
            chunks.append(Chunk(section, subsection, start_page, " ".join(words)))
        words = []

    def start_section(name: str, page_number: int):
        nonlocal section, subsection, subsection_number
        if name != section:
            flush()
            section, subsection, subsection_number = name, None, 0

    for page_number, text in enumerate(pages, start=1):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title_words = text.split()
        if title_words and title_words[0].isdigit():  # a leading page number
            title_words = title_words[1:]
        if 0 < len(title_words) <= 8:  # a title page, e.g. "Law 2" or "Law changes 2026/27"
            start_section(section_name(" ".join(title_words)), page_number)
            continue

        body = []
        for i, line in enumerate(lines):
            header = HEADER.search(re.sub(r"^\d+", "", line)) if i < 2 else None
            if header:  # the running header is glued to the page number, on the first or second line
                start_section(section_name(header["part"].strip()), page_number)
            elif not re.fullmatch(r"\d{1,3}", line):  # drop page numbers
                body.append(line)
        if section in SKIPPED_SECTIONS:
            continue

        previous = None
        for line in body:
            heading = SUBSECTION.match(line)
            # Only accept the next number in order, so a numbered list item isn't mistaken for a heading.
            if heading and re.fullmatch(r"Law \d+ – .+", section) and int(heading["number"]) == subsection_number + 1:
                flush()
                subsection_number = int(heading["number"])
                subsection = f"{subsection_number}. {heading['title'].strip()}"
            elif len(words) >= MIN_WORDS and is_heading(line, previous):
                flush()  # keep a heading with the text it introduces, not at the end of the previous chunk
            previous = line
            if not words:
                start_page = page_number
            words += line.split()
            if len(words) >= MAX_WORDS or (len(words) >= TARGET_WORDS and line.endswith((".", ":"))):
                flush()
    flush()
    return chunks

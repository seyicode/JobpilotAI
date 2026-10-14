"""Local, rule-based requirement extraction. Free, offline, and deterministic, but less accurate
than an AI model on unusual postings. Anything it cannot find is left unknown."""

import re

from jobpilot.services.extraction.schema import JobRequirements, Salary
from jobpilot.services.skills import skill_key

KNOWN_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "Rust", "C++", "C#", "Ruby", "PHP", "Kotlin",
    "Swift", "Scala", "Elixir", "SQL", "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis",
    "Elasticsearch", "Kafka", "RabbitMQ", "Docker", "Kubernetes", "Terraform", "Ansible", "AWS",
    "Azure", "GCP", "Linux", "Git", "CI/CD", "GraphQL", "REST", "gRPC", "React", "Next.js", "Vue",
    "Angular", "Svelte", "Node.js", "Django", "Flask", "FastAPI", "Spring", "Rails", ".NET",
    "HTML", "CSS", "Tailwind", "Pandas", "NumPy", "PyTorch", "TensorFlow", "scikit-learn",
    "Machine Learning", "Data Analysis", "Statistics", "Spark", "Airflow", "dbt", "Snowflake",
    "BigQuery", "Tableau", "Power BI", "Excel", "Figma", "Jira", "Agile", "Scrum",
    "Microservices", "Distributed Systems", "System Design", "Selenium", "Playwright", "Cypress",
    "Jest", "Pytest", "Product Management", "Project Management", "Stakeholder Management",
    "Communication", "Leadership", "Mentoring", "SEO", "Salesforce", "SAP", "Go",
]
# Other spellings that report under the canonical name above (see services.skills.ALIASES).
ALIAS_SPELLINGS = ["Postgres", "Golang", "K8s", "JS", "TS", "NodeJS", "ReactJS", "sklearn"]

_PREFERRED_HEADING = re.compile(
    r"nice to have|preferred|bonus|desirable|good to have|would be great|pluses|extra credit", re.IGNORECASE
)
_REQUIRED_HEADING = re.compile(
    r"requirements|required|must[- ]haves?|qualifications|what you(?:'|’)ll need|"
    r"what we(?:'|’)re looking for|about you|you have|who you are|essential|skills", re.IGNORECASE
)
_PREFERRED_INLINE = re.compile(
    r"nice to have|preferred|is a (?:big )?plus|a bonus|desirable|ideally|good to have", re.IGNORECASE
)
_OTHER_HEADING = re.compile(
    r"responsibilit|about (?:us|the)|benefits|what you(?:'|’)ll do|perks|the role|how to apply", re.IGNORECASE
)
_BULLET = re.compile(r"^\s*(?:[•●▪◦‣∙·\-*–]|\d+[.)])\s*")

_SENIORITY = [  # Checked in order; the first match wins.
    ("executive", r"\b(?:vp|vice president|chief \w+ officer|cto|ceo|cfo|coo)\b"),
    ("director", r"\b(?:director|head of)\b"),
    ("manager", r"\b(?:engineering|team|people|delivery|development) manager\b"),
    ("lead", r"\b(?:lead|staff|principal)\b"),
    ("senior", r"\b(?:senior|sr\.?)\b"),
    ("mid", r"\b(?:mid[- ]level|intermediate|mid[- ]senior)\b"),
    ("entry", r"\b(?:junior|jr\.?|entry[- ]level|graduate|new grad)\b"),
    ("intern", r"\b(?:intern|internship|placement)\b"),
]
# In the description body (not the title), only explicit level words are trusted.
_SENIORITY_IN_BODY = [item for item in _SENIORITY if item[0] in ("senior", "mid", "entry")]
_EMPLOYMENT = [
    ("internship", r"\binternship\b"),
    ("contract", r"\b(?:contract(?:or)?|freelance|fixed[- ]term)\b"),
    ("temporary", r"\b(?:temporary|seasonal|temp)\b"),
    ("part_time", r"\bpart[- ]time\b"),
    ("full_time", r"\b(?:full[- ]time|permanent)\b"),
]
_YEARS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)(?:'|’)?\s+(?:of\s+)?(?:[\w/+#.-]+\s+){0,3}?experience",
    re.IGNORECASE,
)
_QUALIFICATION = re.compile(
    r"\b(?:degree|bachelor|master|ph\.?d|bsc|msc|b\.s\.|m\.s\.|certifi\w*|licen[cs]e\w*|clearance|"
    r"right to work|visa|years?(?:'|’)? (?:of )?(?:\w+ ){0,3}experience)\b",
    re.IGNORECASE,
)
_LOCATION = re.compile(r"^\s*(?:location|based in|office location|where)\s*[:\-–]\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_ARRANGEMENT_LOCATION = re.compile(r"\b(?:remote|hybrid|on[- ]?site)\s*\(([^)]{2,60})\)", re.IGNORECASE)
_COMPANY = re.compile(r"^\s*(?:company|employer|organi[sz]ation)\s*[:\-–]\s*(.+)$", re.IGNORECASE | re.MULTILINE)

_CURRENCY_SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR"}
_AMOUNT = r"\d{1,3}(?:[,.]\d{3})+|\d+(?:\.\d+)?"
_SALARY = re.compile(
    rf"(?P<cur>[£$€]|\b(?:USD|GBP|EUR|CAD|AUD)\s?)?(?P<a>{_AMOUNT})\s*(?P<ak>k)?\b"
    rf"(?:\s*(?:-|–|—|to)\s*(?:[£$€]|(?:USD|GBP|EUR|CAD|AUD)\s?)?(?P<b>{_AMOUNT})\s*(?P<bk>k)?\b)?"
    rf"(?:\s*(?P<code>USD|GBP|EUR|CAD|AUD)\b)?",
    re.IGNORECASE,
)
_PERIODS = [
    ("hour", r"per hour|/\s?h(?:ou)?r\b|an hour|hourly|p/?h\b"),
    ("month", r"per month|/\s?month|a month|monthly|p/?m\b"),
    ("year", r"per year|per annum|/\s?y(?:ea)?r\b|a year|annual(?:ly)?|p\.?a\.?\b|salary"),
]


def extract_with_rules(
    description: str, *, title: str | None = None, company: str | None = None,
    extra_skills: list[str] | None = None,
) -> JobRequirements:
    lines = description.splitlines()
    first_line = next((line.strip() for line in lines if line.strip()), "")
    title = title or _guess_title(first_line)
    company = company or _guess_company(description, first_line)
    required, preferred = _skills(lines, KNOWN_SKILLS + ALIAS_SPELLINGS + (extra_skills or []))
    return JobRequirements(
        title=title,
        company=company,
        required_skills=required,
        preferred_skills=preferred,
        seniority=_seniority(title or "", description),
        location=_location(description),
        work_arrangement=_work_arrangement(description),
        employment_type=_first_match(_EMPLOYMENT, description),
        salary=_salary(description),
        years_experience_min=_years(description),
        qualifications=_qualifications(lines),
    )


def _skills(lines: list[str], vocabulary: list[str]) -> tuple[list[str], list[str]]:
    """Classify each skill by where it is mentioned. Mentioned only in 'nice to have'
    contexts -> preferred; anywhere else -> required."""
    patterns: dict[str, list[re.Pattern]] = {}
    display: dict[str, str] = {}  # key -> first spelling in the vocabulary (canonical names first)
    for name in vocabulary:
        key = skill_key(name)
        if key:
            patterns.setdefault(key, []).append(_skill_pattern(name))
            display.setdefault(key, name)
    contexts: dict[str, set[str]] = {}
    section = "neutral"
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if _is_heading(line):
            if _PREFERRED_HEADING.search(line):
                section = "preferred"
            elif _REQUIRED_HEADING.search(line):
                section = "required"
            else:
                section = "neutral"
            continue
        context = "preferred" if section == "preferred" or _PREFERRED_INLINE.search(line) else "required"
        for key, key_patterns in patterns.items():
            if any(pattern.search(line) for pattern in key_patterns):
                contexts.setdefault(key, set()).add(context)
    required, preferred = [], []
    for key, found in contexts.items():
        (required if "required" in found else preferred).append(display[key])
    return required, preferred


def _skill_pattern(name: str) -> re.Pattern:
    if name == "Go":
        return re.compile(r"\bGolang\b|(?<=[,/(]\s)Go\b|(?<=[,/(])Go\b|\bGo(?=\s?[,/)])")
    flags = 0 if len(name) <= 2 else re.IGNORECASE  # "JS", "TS": exact case only
    return re.compile(rf"(?<![\w+#.]){re.escape(name)}(?![\w+#]|\.\w)", flags)


def _is_heading(line: str) -> bool:
    """A short, non-bullet line ending in a colon, in capitals, or naming a known section."""
    text = line.strip()
    if len(text) > 60 or _BULLET.match(line):
        return False
    if text.endswith(":") or (text.isupper() and any(c.isalpha() for c in text)):
        return True
    is_phrase = re.fullmatch(r"[\w’' &/-]+", text) is not None
    known = _PREFERRED_HEADING, _REQUIRED_HEADING, _OTHER_HEADING
    return is_phrase and any(pattern.search(text) for pattern in known)


def _guess_title(first_line: str) -> str | None:
    if not first_line or len(first_line) > 100 or first_line.endswith("."):
        return None
    return re.split(r"\s+(?:at|@)\s+|\s+[-–—|]\s+", first_line, maxsplit=1)[0].strip() or None


def _guess_company(description: str, first_line: str) -> str | None:
    if match := _COMPANY.search(description):
        return match[1].strip()[:200]
    parts = re.split(r"\s+(?:at|@)\s+|\s+[-–—|]\s+", first_line, maxsplit=1)
    if len(first_line) <= 100 and len(parts) == 2:
        return parts[1].strip(" .")[:200] or None
    return None


def _seniority(title: str, description: str):
    return _first_match(_SENIORITY, title) or _first_match(_SENIORITY_IN_BODY, description)


def _first_match(options, text: str):
    for value, pattern in options:
        if re.search(pattern, text, re.IGNORECASE):
            return value
    return None


def _work_arrangement(text: str):
    def mentioned(pattern: str) -> bool:
        return any(not re.search(r"\b(?:not|no|non)[- ]?\s*$", text[max(0, m.start() - 8):m.start()], re.IGNORECASE)
                   for m in re.finditer(pattern, text, re.IGNORECASE))
    if mentioned(r"\bhybrid\b"):
        return "hybrid"
    if mentioned(r"\b(?:fully |100% )?remote\b"):
        return "remote"
    if mentioned(r"\b(?:on[- ]?site|in[- ]office|office[- ]based)\b"):
        return "onsite"
    return None


# "Location: Manchester, UK. Hybrid, full-time." -> stop before the arrangement/pay details.
_LOCATION_END = re.compile(
    r"\s+[|·]\s+|[.;,]\s+(?=(?:hybrid|remote|on[- ]?site|in[- ]office|full|part|contract|"
    r"temporary|permanent|salary|pay|[£$€]|\d))",
    re.IGNORECASE,
)


def _location(text: str) -> str | None:
    match = _LOCATION.search(text) or _ARRANGEMENT_LOCATION.search(text)
    if not match:
        return None
    return _LOCATION_END.split(match[1], maxsplit=1)[0].strip(" .")[:200] or None


def _years(text: str) -> int | None:
    values = [int(m[1]) for m in _YEARS.finditer(text) if int(m[1]) <= 50]
    return max(values) if values else None


def _qualifications(lines: list[str]) -> list[str]:
    found = []
    for line in lines:
        text = _BULLET.sub("", line).strip()
        if text and not _is_heading(line) and _QUALIFICATION.search(text):
            found.append(text[:300])
    return found[:15]


def _salary(text: str) -> Salary:
    for match in _SALARY.finditer(text):
        symbol = (match["cur"] or "").strip().upper()
        code = (match["code"] or "").upper() or _CURRENCY_SYMBOLS.get(symbol) or (symbol or None)
        if not code:
            continue
        low = _amount(match["a"], match["ak"] or match["bk"])
        high = _amount(match["b"], match["bk"]) if match["b"] else None
        window = text[match.end(): match.end() + 40]
        period = _first_match(_PERIODS, window) or _default_period(high or low)
        return Salary(min=low, max=high or low, currency=code, period=period)
    return Salary()


def _amount(value: str, thousands: str | None) -> int:
    number = float(re.sub(r"[,.](?=\d{3}\b)", "", value))
    return int(number * 1000) if thousands else int(number)


def _default_period(amount: int) -> str:
    if amount < 500:
        return "hour"
    return "month" if amount < 15_000 else "year"

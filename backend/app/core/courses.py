"""Course-code normalization shared by the agent's course resolver (S21) and merge (S16).

"COMPSCI 311 SEC 01" -> ("COMPSCI", "311"); department aliases from S16 rule 1. S16 should import
this instead of writing a second copy (extend `DEPT_ALIASES` as new spellings show up).
"""

import re

DEPT_ALIASES = {
    "CS": "COMPSCI",
    "CMPSCI": "COMPSCI",
    "COMPSCI": "COMPSCI",
    "MATH": "MATH",
    "STAT": "STATS",
    "STATS": "STATS",
}

_CODE = re.compile(r"\b([A-Za-z]{2,10})\s*[-_ ]?\s*(\d{2,4}[A-Za-z]?)\b")


def normalize_course_code(raw: str) -> tuple[str, str] | None:
    match = _CODE.search(raw or "")
    if not match:
        return None
    dept = match.group(1).upper()
    return DEPT_ALIASES.get(dept, dept), match.group(2).upper()

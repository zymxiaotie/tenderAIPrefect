# parser.py
from typing import List
from models import QSCriterion
import structlog

logger = structlog.get_logger()

def parse_markdown_table(md: str) -> List[QSCriterion]:
    lines = [l.strip() for l in md.strip().split("\n") if l.strip()]
    if len(lines) < 3: raise ValueError("Invalid table")

    header = [h.strip() for h in lines[0].split("|")[1:-1]]
    expected = ["No", "Sticker Tag", "Extracted Clause", "Accepted Variations", "QS Reason"]
    if header != expected: raise ValueError(f"Header mismatch: {header}")

    criteria = []
    seen = set()

    for row in lines[2:]:
        cols = [c.strip() for c in row.split("|")[1:-1]]
        if len(cols) != 5: continue
        raw = dict(zip(expected, cols))
        try:
            crit = QSCriterion(**raw)
            key = crit.tag_name
            if key in seen:
                existing = next(c for c in criteria if c.tag_name == key)
                existing.extracted_clause = crit.extracted_clause or existing.extracted_clause
                existing.accepted_variations += f", {crit.accepted_variations}"
            else:
                criteria.append(crit)
                seen.add(key)
        except Exception as e:
            logger.warning(f"Parse error: {e} | {raw}")
    return criteria
# models.py
from pydantic import BaseModel, Field, validator
from typing import Any

class QSCriterion(BaseModel):
    no: int = Field(..., ge=1, alias="No")
    sticker_tag: str = Field(..., alias="Sticker Tag", max_length=50)
    extracted_clause: str = Field(..., alias="Extracted Clause", max_length=1000)
    accepted_variations: str = Field(..., alias="Accepted Variations", max_length=200)
    qs_reason: str = Field(..., alias="QS Reason", max_length=500)

    model_config = {"populate_by_name": True}

    @property
    def tag_name(self) -> str:
        return self.sticker_tag.strip().upper().replace(" ", "_")

    @property
    def category(self) -> str:
        tag = self.sticker_tag.lower()
        if any(x in tag for x in ["license", "bca"]): return "License"
        if any(x in tag for x in ["turnover", "financial"]): return "Financial"
        if any(x in tag for x in ["iso", "certification"]): return "Certification"
        if any(x in tag for x in ["experience", "project"]): return "Experience"
        if any(x in tag for x in ["audit", "statement"]): return "Financial"
        return "Other"

    @property
    def confidence(self) -> float:
        base = 0.85
        if len(self.extracted_clause) > 100: base += 0.05
        if "or" in self.accepted_variations.lower(): base += 0.05
        if any(x in self.extracted_clause.lower() for x in ["last", "year"]): base += 0.05
        return min(1.0, round(base, 2))

    @validator("sticker_tag")
    def validate_tag(cls, v: str) -> str:
        v = v.strip()
        words = v.split()
        if not (2 <= len(words) <= 5): raise ValueError("Sticker Tag must be 2–5 words")
        if not all(w.replace(":", "").replace("-", "").isalnum() for w in words):
            raise ValueError("Sticker Tag contains invalid characters")
        return " ".join(words).title()
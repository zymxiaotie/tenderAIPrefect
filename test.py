# Quick drop-in fixed models.py
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List
import re

class QSCriterion(BaseModel):
    """Fixed QS Criterion - ready to use!"""
    
    # This line fixes the alias issue
    model_config = ConfigDict(populate_by_name=True)
    
    no: int = Field(..., ge=1, alias="No")
    sticker_tag: str = Field(..., alias="Sticker Tag", max_length=50)
    extracted_clause: str = Field(..., alias="Extracted Clause", max_length=1000)
    accepted_variations: str = Field(..., alias="Accepted Variations", max_length=200)
    qs_reason: str = Field(..., alias="QS Reason", max_length=500)

    @property
    def tag_name(self) -> str:
        return self.sticker_tag.strip().upper().replace(" ", "_")

    @property
    def category(self) -> str:
        tag = self.sticker_tag.lower()
        if any(x in tag for x in ["license", "bca", "registration"]):
            return "License"
        if any(x in tag for x in ["turnover", "financial", "revenue"]):
            return "Financial"
        if any(x in tag for x in ["iso", "certification"]):
            return "Certification"
        if any(x in tag for x in ["experience", "project", "track"]):
            return "Experience"
        if any(x in tag for x in ["audit", "statement"]):
            return "Financial"
        return "Other"

    @property
    def confidence(self) -> float:
        base = 0.85
        if len(self.extracted_clause) > 100: base += 0.05
        if "or" in self.accepted_variations.lower(): base += 0.05
        if any(x in self.extracted_clause.lower() for x in ["last", "year", "average"]): base += 0.05
        return min(1.0, round(base, 2))

    @field_validator("sticker_tag")
    @classmethod
    def validate_tag(cls, v):
        v = v.strip()
        words = v.split()
        if not (2 <= len(words) <= 5):
            raise ValueError("Sticker Tag must be 2–5 words")
        
        # Fixed: Allow numbers and symbols for things like "ISO 9001"
        pattern = r'^[a-zA-Z0-9\s\-:/.&()]+$'
        if not re.match(pattern, v):
            raise ValueError("Sticker Tag contains invalid characters")
        
        return " ".join(words).title()

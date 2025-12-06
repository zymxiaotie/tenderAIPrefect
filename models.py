# models.py - Improved version based on assessment findings
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional
import re
from enum import Enum

class CriteriaCategory(str, Enum):
    LICENSE = "License"
    FINANCIAL = "Financial"
    CERTIFICATION = "Certification"
    EXPERIENCE = "Experience"
    SAFETY = "Safety"
    COMPLIANCE = "Compliance"
    OTHER = "Other"

class SeverityLevel(str, Enum):
    MANDATORY = "Mandatory"
    IMPORTANT = "Important"
    OPTIONAL = "Optional"

class QSCriterion(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)
    
    no: int = Field(..., ge=1, alias="No", description="Sequential number")
    sticker_tag: str = Field(..., alias="Sticker Tag", max_length=50, description="Short descriptive tag")
    extracted_clause: str = Field(..., alias="Extracted Clause", max_length=1500, description="Full extracted requirement text")
    accepted_variations: str = Field(..., alias="Accepted Variations", max_length=300, description="Alternative acceptable formats")
    qs_reason: str = Field(..., alias="QS Reason", max_length=800, description="Professional justification")
    
    # Enhanced metadata fields
    source_page: Optional[int] = Field(None, description="Source page number")
    source_section: Optional[str] = Field(None, description="Source document section")
    
    @property
    def tag_name(self) -> str:
        """Generate database-friendly tag name"""
        return self.sticker_tag.strip().upper().replace(" ", "_").replace("-", "_")
    
    @property
    def category(self) -> CriteriaCategory:
        """Enhanced categorization with more categories"""
        tag_lower = self.sticker_tag.lower()
        clause_lower = self.extracted_clause.lower()
        combined = f"{tag_lower} {clause_lower}"
        
        # License and Registration
        if any(keyword in combined for keyword in [
            "license", "bca", "registration", "permit", "authority", "workhead", "supply head"
        ]):
            return CriteriaCategory.LICENSE
        
        # Safety
        if any(keyword in combined for keyword in [
            "safety", "accident", "fatality", "demerit", "surveillance", "mom", "workplace safety"
        ]):
            return CriteriaCategory.SAFETY
        
        # Financial
        if any(keyword in combined for keyword in [
            "turnover", "financial", "revenue", "profit", "cash flow", "audit", 
            "statement", "judicial management", "winding up", "insolvency"
        ]):
            return CriteriaCategory.FINANCIAL
        
        # Compliance
        if any(keyword in combined for keyword in [
            "debarment", "restricted", "gst", "tax", "compliance", "legal", 
            "court", "prosecution", "violation"
        ]):
            return CriteriaCategory.COMPLIANCE
        
        # Certification
        if any(keyword in combined for keyword in [
            "iso", "certification", "quality", "standard", "accreditation"
        ]):
            return CriteriaCategory.CERTIFICATION
        
        # Experience
        if any(keyword in combined for keyword in [
            "experience", "project", "track", "similar", "completed", "performance"
        ]):
            return CriteriaCategory.EXPERIENCE
        
        return CriteriaCategory.OTHER
    
    @property
    def severity(self) -> SeverityLevel:
        """Determine requirement severity level"""
        clause_lower = self.extracted_clause.lower()
        tag_lower = self.sticker_tag.lower()
        combined = f"{clause_lower} {tag_lower}"
        
        # Mandatory indicators
        mandatory_keywords = [
            "must", "shall", "required", "mandatory", "compulsory", 
            "debarred", "restricted", "license", "registration"
        ]
        
        if any(keyword in combined for keyword in mandatory_keywords):
            return SeverityLevel.MANDATORY
        
        # Important indicators  
        important_keywords = [
            "should", "expected", "preferred", "minimum", "threshold", 
            "financial", "experience", "turnover"
        ]
        
        if any(keyword in combined for keyword in important_keywords):
            return SeverityLevel.IMPORTANT
        
        return SeverityLevel.OPTIONAL
    
    @property
    def confidence(self) -> float:
        """Enhanced confidence scoring algorithm"""
        base_score = 0.80
        
        # Length and detail indicators
        if len(self.extracted_clause) > 150:
            base_score += 0.10  # Detailed requirements are more reliable
        elif len(self.extracted_clause) > 80:
            base_score += 0.05
        
        # Variation indicators
        variations = self.accepted_variations.lower()
        if "or" in variations or "," in variations:
            base_score += 0.05  # Multiple variations indicate thoroughness
        
        # Specificity indicators
        specificity_keywords = ["minimum", "maximum", "at least", "not less than", "above", "below"]
        if any(keyword in self.extracted_clause.lower() for keyword in specificity_keywords):
            base_score += 0.05
        
        # Regulatory indicators (high confidence)
        regulatory_keywords = ["act", "regulation", "authority", "ministry", "government"]
        if any(keyword in self.extracted_clause.lower() for keyword in regulatory_keywords):
            base_score += 0.08
        
        # Time-based indicators
        time_keywords = ["year", "month", "period", "duration", "recent", "current"]
        if any(keyword in self.extracted_clause.lower() for keyword in time_keywords):
            base_score += 0.03
        
        return min(1.0, round(base_score, 2))
    
    @property
    def risk_level(self) -> str:
        """Assess risk level for non-compliance"""
        if self.severity == SeverityLevel.MANDATORY:
            return "High"
        elif self.severity == SeverityLevel.IMPORTANT:
            return "Medium"
        else:
            return "Low"
    
    @validator("sticker_tag")
    def validate_tag(cls, v: str) -> str:
        """Enhanced tag validation with better regex"""
        v = v.strip()
        words = v.split()
        
        if not (2 <= len(words) <= 5):
            raise ValueError("Sticker Tag must be 2–5 words")
        
        # Allow letters, numbers, and common symbols
        allowed_pattern = r'^[a-zA-Z0-9\s\-:/.&()]+$'
        if not re.match(allowed_pattern, v):
            raise ValueError("Sticker Tag contains invalid characters")
        
        return " ".join(words).title()
    
    @validator("extracted_clause")
    def validate_clause(cls, v: str) -> str:
        """Validate extracted clause content"""
        v = v.strip()
        if len(v) < 20:
            raise ValueError("Extracted clause too short (minimum 20 characters)")
        return v

class TenderDocument(BaseModel):
    """Enhanced document model for tracking"""
    tender_id: int
    title: str
    reference_number: str
    file_path: str
    processing_status: str = "pending"
    criteria_count: int = 0
    extraction_confidence: float = 0.0
    created_at: Optional[str] = None
    
class ProcessingResult(BaseModel):
    """Result container for processing pipeline"""
    success: bool
    criteria: List[QSCriterion]
    errors: List[str] = []
    warnings: List[str] = []
    processing_time: float = 0.0
    total_pages: int = 0
    extraction_summary: dict = {}
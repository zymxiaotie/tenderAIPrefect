# parser_improved.py - Enhanced parser with comprehensive error handling and validation
import re
import logging
from typing import List, Dict, Tuple, Optional
from models_improved import QSCriterion, ProcessingResult

logger = logging.getLogger(__name__)

class TenderParser:
    """Enhanced parser for processing LLM-extracted qualification criteria"""
    
    def __init__(self):
        self.expected_headers = ["No", "Sticker Tag", "Extracted Clause", "Accepted Variations", "QS Reason"]
        self.min_table_rows = 3  # Header + separator + at least 1 data row
        
    def parse_markdown_table(self, markdown_text: str, source_info: Dict = None) -> ProcessingResult:
        """
        Parse markdown table with comprehensive error handling and validation
        
        Args:
            markdown_text: Raw markdown table text from LLM
            source_info: Optional source information (page, section, etc.)
            
        Returns:
            ProcessingResult with criteria, errors, and warnings
        """
        result = ProcessingResult(
            success=False,
            criteria=[],
            errors=[],
            warnings=[]
        )
        
        try:
            # Pre-process and clean the input
            cleaned_text = self._clean_markdown_input(markdown_text)
            if not cleaned_text:
                result.errors.append("Empty or invalid markdown input")
                return result
            
            # Extract table lines
            lines = self._extract_table_lines(cleaned_text)
            if len(lines) < self.min_table_rows:
                result.errors.append(f"Insufficient table rows. Expected at least {self.min_table_rows}, got {len(lines)}")
                return result
            
            # Parse and validate header
            header_valid, header_errors = self._validate_header(lines[0])
            if not header_valid:
                result.errors.extend(header_errors)
                return result
            
            # Process data rows
            criteria, row_errors, row_warnings = self._process_data_rows(lines[2:], source_info)
            
            result.criteria = criteria
            result.errors.extend(row_errors)
            result.warnings.extend(row_warnings)
            result.success = len(criteria) > 0 and len(result.errors) == 0
            
            # Add processing summary
            result.extraction_summary = {
                "total_rows_processed": len(lines) - 2,
                "criteria_extracted": len(criteria),
                "success_rate": len(criteria) / max(1, len(lines) - 2),
                "duplicate_tags_merged": self._count_merged_duplicates(criteria)
            }
            
            logger.info(f"Parser results: {len(criteria)} criteria extracted from {len(lines)-2} rows")
            
        except Exception as e:
            error_msg = f"Critical parsing error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result.errors.append(error_msg)
            
        return result
    
    def _clean_markdown_input(self, text: str) -> str:
        """Clean and normalize markdown input"""
        if not text or not text.strip():
            return ""
        
        # Remove markdown code fences if present
        text = re.sub(r'```(?:markdown)?\s*', '', text)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        
        # Normalize whitespace and line endings
        text = re.sub(r'\r\n|\r', '\n', text)
        text = re.sub(r'\n\s*\n', '\n', text)  # Remove empty lines
        
        return text.strip()
    
    def _extract_table_lines(self, text: str) -> List[str]:
        """Extract valid table lines from text"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        # Filter lines that look like table rows (contain |)
        table_lines = []
        for line in lines:
            if '|' in line and len(line.split('|')) >= 3:  # At least start, middle, end
                table_lines.append(line)
        
        return table_lines
    
    def _validate_header(self, header_line: str) -> Tuple[bool, List[str]]:
        """Validate table header against expected format"""
        errors = []
        
        try:
            # Parse header columns
            columns = [col.strip() for col in header_line.split('|')[1:-1]]  # Remove empty start/end
            
            # Check column count
            if len(columns) != len(self.expected_headers):
                errors.append(f"Header column mismatch: expected {len(self.expected_headers)}, got {len(columns)}")
            
            # Check column names (flexible matching)
            for i, (expected, actual) in enumerate(zip(self.expected_headers, columns)):
                if not self._header_matches(expected, actual):
                    errors.append(f"Header column {i+1}: expected '{expected}', got '{actual}'")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            errors.append(f"Header parsing failed: {str(e)}")
            return False, errors
    
    def _header_matches(self, expected: str, actual: str) -> bool:
        """Check if header column matches expected (fuzzy matching)"""
        # Normalize for comparison
        expected_norm = expected.lower().replace(' ', '').replace('_', '')
        actual_norm = actual.lower().replace(' ', '').replace('_', '')
        
        # Direct match
        if expected_norm == actual_norm:
            return True
        
        # Partial matches for common variations
        if expected == "No" and actual_norm in ["no", "num", "number", "#"]:
            return True
        if expected == "Sticker Tag" and "tag" in actual_norm:
            return True
        if expected == "Extracted Clause" and ("clause" in actual_norm or "requirement" in actual_norm):
            return True
        if expected == "Accepted Variations" and ("variation" in actual_norm or "alternative" in actual_norm):
            return True
        if expected == "QS Reason" and ("reason" in actual_norm or "justification" in actual_norm):
            return True
        
        return False
    
    def _process_data_rows(self, data_lines: List[str], source_info: Dict = None) -> Tuple[List[QSCriterion], List[str], List[str]]:
        """Process data rows and create QSCriterion objects"""
        criteria = []
        errors = []
        warnings = []
        seen_tags = {}  # Track duplicates for merging
        
        for row_idx, line in enumerate(data_lines, 1):
            try:
                # Parse row columns
                columns = [col.strip() for col in line.split('|')[1:-1]]
                
                # Skip incomplete rows
                if len(columns) != 5:
                    warnings.append(f"Row {row_idx}: incomplete data ({len(columns)} columns), skipping")
                    continue
                
                # Create raw data dictionary
                raw_data = dict(zip(self.expected_headers, columns))
                
                # Skip empty rows
                if not any(raw_data.values()) or not raw_data["Sticker Tag"].strip():
                    warnings.append(f"Row {row_idx}: empty or missing sticker tag, skipping")
                    continue
                
                # Add source information if available
                if source_info:
                    raw_data.update(source_info)
                
                # Try to create QSCriterion object
                try:
                    criterion = QSCriterion(**raw_data)
                    
                    # Handle duplicates by merging
                    tag_key = criterion.tag_name
                    if tag_key in seen_tags:
                        existing_criterion = seen_tags[tag_key]
                        merged_criterion = self._merge_duplicate_criteria(existing_criterion, criterion)
                        seen_tags[tag_key] = merged_criterion
                        warnings.append(f"Row {row_idx}: merged duplicate tag '{criterion.sticker_tag}'")
                    else:
                        seen_tags[tag_key] = criterion
                    
                except ValueError as ve:
                    errors.append(f"Row {row_idx}: validation failed - {str(ve)}")
                    logger.warning(f"Validation failed for row {row_idx}: {raw_data}")
                    
            except Exception as e:
                errors.append(f"Row {row_idx}: processing failed - {str(e)}")
                logger.error(f"Row processing error at {row_idx}: {line}", exc_info=True)
        
        # Convert seen_tags to list
        criteria = list(seen_tags.values())
        
        # Re-number criteria sequentially
        for i, criterion in enumerate(criteria, 1):
            criterion.no = i
        
        logger.info(f"Processed {len(data_lines)} rows, extracted {len(criteria)} criteria with {len(errors)} errors")
        
        return criteria, errors, warnings
    
    def _merge_duplicate_criteria(self, existing: QSCriterion, new: QSCriterion) -> QSCriterion:
        """Merge duplicate criteria by combining information"""
        # Use the more detailed clause
        merged_clause = existing.extracted_clause
        if len(new.extracted_clause) > len(existing.extracted_clause):
            merged_clause = new.extracted_clause
        
        # Combine variations
        existing_vars = set(v.strip() for v in existing.accepted_variations.split(','))
        new_vars = set(v.strip() for v in new.accepted_variations.split(','))
        combined_vars = ', '.join(sorted(existing_vars | new_vars))
        
        # Use the more detailed reason
        merged_reason = existing.qs_reason
        if len(new.qs_reason) > len(existing.qs_reason):
            merged_reason = new.qs_reason
        
        # Create merged criterion
        merged_data = {
            "No": existing.no,
            "Sticker Tag": existing.sticker_tag,
            "Extracted Clause": merged_clause,
            "Accepted Variations": combined_vars,
            "QS Reason": merged_reason
        }
        
        return QSCriterion(**merged_data)
    
    def _count_merged_duplicates(self, criteria: List[QSCriterion]) -> int:
        """Count how many duplicates were merged (approximation)"""
        # This is a rough estimate based on variation count
        total_variations = sum(len(c.accepted_variations.split(',')) for c in criteria)
        return max(0, total_variations - len(criteria))
    
    def validate_extraction_quality(self, result: ProcessingResult) -> Dict[str, any]:
        """Validate the quality of extracted criteria"""
        if not result.criteria:
            return {"score": 0, "issues": ["No criteria extracted"]}
        
        quality_metrics = {
            "total_criteria": len(result.criteria),
            "avg_confidence": sum(c.confidence for c in result.criteria) / len(result.criteria),
            "category_distribution": {},
            "severity_distribution": {},
            "quality_score": 0,
            "issues": []
        }
        
        # Analyze distributions
        for criterion in result.criteria:
            # Category distribution
            cat = criterion.category.value
            quality_metrics["category_distribution"][cat] = quality_metrics["category_distribution"].get(cat, 0) + 1
            
            # Severity distribution
            sev = criterion.severity.value
            quality_metrics["severity_distribution"][sev] = quality_metrics["severity_distribution"].get(sev, 0) + 1
        
        # Calculate quality score
        base_score = 70  # Base score for successful extraction
        
        # Bonus for high confidence
        if quality_metrics["avg_confidence"] > 0.9:
            base_score += 15
        elif quality_metrics["avg_confidence"] > 0.8:
            base_score += 10
        elif quality_metrics["avg_confidence"] > 0.7:
            base_score += 5
        
        # Bonus for good category distribution
        unique_categories = len(quality_metrics["category_distribution"])
        if unique_categories >= 4:
            base_score += 10
        elif unique_categories >= 3:
            base_score += 5
        
        # Penalty for too many "Other" category
        other_count = quality_metrics["category_distribution"].get("Other", 0)
        if other_count > len(result.criteria) * 0.5:  # More than 50% "Other"
            base_score -= 10
            quality_metrics["issues"].append("High proportion of uncategorized criteria")
        
        # Bonus for good clause detail
        avg_clause_length = sum(len(c.extracted_clause) for c in result.criteria) / len(result.criteria)
        if avg_clause_length > 100:
            base_score += 5
        
        quality_metrics["quality_score"] = min(100, max(0, base_score))
        
        return quality_metrics

# Convenience function for backward compatibility
def parse_markdown_table(md: str) -> List[QSCriterion]:
    """Legacy function for backward compatibility"""
    parser = TenderParser()
    result = parser.parse_markdown_table(md)
    
    if not result.success:
        logger.warning(f"Parsing issues: {result.errors}")
    
    return result.criteria
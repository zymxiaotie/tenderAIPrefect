# context_builder.py
from datetime import datetime
from typing import Dict
from utils.db import get_db
import json

def build_context(tender_id: int) -> Dict:
    context = {
        "reference": "", "title": "", "email_to": ["qs@company.com"],
        "generated_at": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "stats": {}, "recommendation": {}, "summary_text": "",
        "issuing_authority": "Unknown", "submission_deadline": "N/A",
        "project_name": "N/A", "site_location": "N/A", "contract_type": "N/A",
        "liquidated_damages": "N/A", "performance_bond": "N/A",
        "retention": "N/A", "defects_liability_period": "N/A",
        "eligibility_items": [], "documents": [], "addenda": [],
        "action_items": [], "reasoning_text": "", "important_criteria_validation_required": False,
    }

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT tender_title, tender_reference_number FROM tenders WHERE tender_id=%s", (tender_id,))
        row = cur.fetchone()
        if row:
            context.update({"title": row[0], "reference": row[1]})

        cur.execute(
            "SELECT cr.tag_name, cr.category, tqc.raw_text, tqc.confidence_score, tqc.is_met, tqc.notes, tqc.justification, tqc.actions "
            "FROM tender_qualification_criteria tqc JOIN criteria_register cr ON tqc.tag_id=cr.tag_id "
            "WHERE tqc.tender_id=%s", (tender_id,)
        )
        rows = cur.fetchall()
        items = []
        met = 0
        actions = []
        reasoning_parts = []
        for tag, cat, raw, conf, is_met, notes, justification, action_str in rows:
            item = {
                "requirement": tag.replace("_", " ").title(),
                "full_clause": raw,
                "severity": "mandatory" if cat in ["License", "Certification"] else "important" if cat in ["Financial", "Experience"] else "optional",
                "status": "met" if is_met else "not-met",
                "notes": notes or f"Confidence: {conf:.0%}",
                "source": "original"
            }
            items.append(item)
            if is_met: met += 1
            reasoning_parts.append(justification or "")
            if action_str:
                item_actions = json.loads(action_str)
                actions.extend(item_actions)

        context["eligibility_items"] = items
        context["stats"] = {"met_criteria": met, "total_criteria": len(items)}
        context["recommendation"] = {
            "class": "rec-recommend" if met == len(items) else "rec-disqualified",
            "icon": "RECOMMENDED" if met == len(items) else "DISQUALIFIED",
            "text": "RECOMMENDED TO BID" if met == len(items) else "DO NOT BID"
        }
        context["summary_text"] = f"The bidder meets {met}/{len(items)} qualification criteria."
        context["action_items"] = actions
        context["reasoning_text"] = "\n\n".join(reasoning_parts)

    return context
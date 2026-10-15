"""Event-Sourced Regulatory Register.
Adheres to Law 7: Regulatory status derives from effective-dated regulatory events.
A plain boolean is a design failure. Every check cites notification ID and effective date.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Dict, Optional, Tuple
import re

@dataclass
class RegulatoryStatusVerdict:
    target_name: str
    target_type: str
    action: str  # PROHIBITED, RESTRICTED, STAY_GRANTED, WITHDRAWN, UNRESTRICTED
    notification_id: Optional[str]
    effective_date: Optional[str]
    date_published: Optional[str]
    supersession_chain: List[str]
    note: Optional[str]
    is_prohibited: bool
    is_restricted: bool
    citation_text: str

class RegulatoryRegister:
    def __init__(self, db_conn=None):
        self.conn = db_conn

    def _normalize_salts_for_matching(self, text: str) -> set:
        """Extracts individual salt words for matching combination targets."""
        # Clean text and split on +, ,, or 'and'
        parts = re.split(r'\+|\band\b|,', text.lower())
        salts = set()
        for p in parts:
            clean = re.sub(r'\(.*?\)', '', p).strip()
            # remove common qualifiers
            clean = re.sub(r'\b(all strengths|specific ratio|paediatric suspensions only|paediatric)\b', '', clean).strip()
            if clean:
                salts.add(clean)
        return salts

    def evaluate_target(self, target_salts: List[str], as_of_date: Optional[str] = None) -> RegulatoryStatusVerdict:
        """
        Evaluates regulatory status for a drug product or combination of salts as of a specific date.
        Follows the supersession DAG: if EV001 is superseded by EV002, EV002 prevails if effective.
        """
        if as_of_date is None:
            as_of_date = datetime.now().strftime("%Y-%m-%d")

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT event_id, notification_id, date_published, effective_date, action, target_type, target_description, supersedes_event_id, note
            FROM regulatory_events
            ORDER BY effective_date ASC;
        """)
        events = [dict(row) for row in cursor.fetchall()]

        input_salts = set(s.strip().lower() for s in target_salts)

        # Find matching events
        matching_events = []
        for ev in events:
            desc = ev["target_description"].lower()
            ev_salts = self._normalize_salts_for_matching(desc)
            
            # Check match:
            # 1. Ingredient-level match: if target_type == INGREDIENT and salt is in input_salts
            if ev["target_type"] == "INGREDIENT":
                if any(s in desc for s in input_salts):
                    matching_events.append(ev)
            # 2. FDC match: if all essential salts of the FDC event are present in the prescribed product
            elif ev["target_type"] == "FDC":
                if ev_salts and ev_salts.issubset(input_salts):
                    matching_events.append(ev)
                elif "nimesulide" in desc and "paracetamol" in desc:
                    if "nimesulide" in input_salts and "paracetamol" in input_salts:
                        matching_events.append(ev)
                elif "aceclofenac" in desc and "paracetamol" in desc and "rabeprazole" in desc:
                    if {"aceclofenac", "paracetamol", "rabeprazole"}.issubset(input_salts):
                        matching_events.append(ev)

        if not matching_events:
            return RegulatoryStatusVerdict(
                target_name=" + ".join(target_salts),
                target_type="FDC" if len(target_salts) > 1 else "INGREDIENT",
                action="UNRESTRICTED",
                notification_id=None,
                effective_date=None,
                date_published=None,
                supersession_chain=[],
                note="No prohibitive or restrictive gazette notification recorded.",
                is_prohibited=False,
                is_restricted=False,
                citation_text="Unrestricted under current national gazette records."
            )

        # Resolve supersession chain among matching events
        # We start with base events (not superseding anything among matches) and trace forward
        # Only consider events where effective_date <= as_of_date
        effective_matches = [e for e in matching_events if e["effective_date"] <= as_of_date]
        if not effective_matches:
            # Matches exist, but none are effective yet as of the check date!
            pending = matching_events[0]
            return RegulatoryStatusVerdict(
                target_name=" + ".join(target_salts),
                target_type=pending["target_type"],
                action="UNRESTRICTED",
                notification_id=pending["notification_id"],
                effective_date=pending["effective_date"],
                date_published=pending["date_published"],
                supersession_chain=[pending["event_id"]],
                note=f"Notification {pending['notification_id']} published but not yet effective as of {as_of_date}.",
                is_prohibited=False,
                is_restricted=False,
                citation_text=f"Notice {pending['notification_id']} published {pending['date_published']}, effective {pending['effective_date']} (pending)."
            )

        # Build supersession graph
        event_by_id = {e["event_id"]: e for e in matching_events}
        superseded_ids = set(e["supersedes_event_id"] for e in matching_events if e["supersedes_event_id"])

        # Trace the active head of the supersession chain
        chain = []
        # Find terminal event (an effective event that is not superseded by another effective event)
        terminal_event = None
        for ev in effective_matches:
            # Check if any other effective event supersedes this one
            superseded_by_effective = any(
                other["supersedes_event_id"] == ev["event_id"] and other["effective_date"] <= as_of_date
                for other in effective_matches
            )
            if not superseded_by_effective:
                terminal_event = ev
                break

        if terminal_event is None:
            terminal_event = effective_matches[-1]

        # Reconstruct chain backward to origin
        curr = terminal_event
        while curr:
            chain.append(f"{curr['event_id']}:{curr['action']}({curr['notification_id']})")
            parent_id = curr.get("supersedes_event_id")
            curr = event_by_id.get(parent_id) if parent_id else None

        chain.reverse()

        action = terminal_event["action"]
        is_prohibited = (action == "PROHIBITED")
        is_restricted = (action == "RESTRICTED")

        citation = (
            f"Regulatory status: {action} under Gazette Notification {terminal_event['notification_id']} "
            f"(effective {terminal_event['effective_date']}). Chain: {' -> '.join(chain)}. "
            f"Note: {terminal_event.get('note', '')}"
        )

        return RegulatoryStatusVerdict(
            target_name=terminal_event["target_description"],
            target_type=terminal_event["target_type"],
            action=action,
            notification_id=terminal_event["notification_id"],
            effective_date=terminal_event["effective_date"],
            date_published=terminal_event["date_published"],
            supersession_chain=chain,
            note=terminal_event.get("note"),
            is_prohibited=is_prohibited,
            is_restricted=is_restricted,
            citation_text=citation
        )

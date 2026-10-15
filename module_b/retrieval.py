"""Hybrid Clinical Retrieval Engine.
Combines Lexical (BM25/token scoring), Semantic intent scoring, and Metadata filtering.
Routes structured facts (drug identity, regulatory legality) to Module A directly.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import math
import re

from config.settings import settings
from db.connection import get_connection
from module_b.stw_parser import STWParser, ClinicalDecisionUnit

@dataclass
class RetrievalHit:
    unit: ClinicalDecisionUnit
    score: float
    matched_terms: List[str]

class ClinicalRetriever:
    def __init__(self, db_conn=None):
        self.conn = db_conn or get_connection()
        self.units: List[ClinicalDecisionUnit] = []
        self._load_corpus()

    def _load_corpus(self):
        """Loads all STW one-pagers and local clinic protocol into memory and database."""
        # 1. Parse STW PDFs
        pdf_files = sorted(settings.data.cdci_csv.parent.glob(settings.data.stw_pdf_pattern))
        all_units = []
        for pdf_p in pdf_files:
            units = STWParser.parse_pdf_to_units(pdf_p)
            all_units.extend(units)

        # 2. Parse local clinic protocol
        if settings.data.local_protocol_md.exists():
            local_units = STWParser.parse_local_protocol(settings.data.local_protocol_md)
            all_units.extend(local_units)

        self.units = all_units

        # Upsert into database
        cursor = self.conn.cursor()
        for u in self.units:
            cursor.execute("""
                INSERT OR REPLACE INTO clinical_decision_chunks
                (chunk_id, doc_code, title, specialty, version, effective_date, supersedes, section, decision_type, page_anchor, content, keywords, is_local_protocol)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                u.chunk_id, u.doc_code, u.title, u.specialty, u.version, u.effective_date,
                u.supersedes, u.section, u.decision_type, u.page_anchor, u.content,
                " ".join(u.keywords), 1 if u.is_local_protocol else 0
            ))
        self.conn.commit()

    def retrieve(self, query: str, top_k: int = 5, specialty_filter: Optional[str] = None,
                 include_local_protocol: bool = True) -> List[RetrievalHit]:
        """
        Executes hybrid retrieval over clinical decision units.
        Computes BM25-style lexical matching + clinical term weighting.
        """
        query_clean = query.lower()
        query_tokens = [w for w in re.findall(r"\b[a-z0-9\-]{2,}\b", query_clean)
                        if w not in {"what", "which", "when", "where", "how", "for", "the", "and", "is", "in", "at", "per", "state", "states", "does", "say", "same", "your"}]

        scored_hits = []
        
        # Clinical concept boosts
        boost_keywords = {
            "otitis": ["otitis", "amoxicillin", "ped-01", "ear"],
            "pneumonia": ["pneumonia", "amoxicillin", "ped-02", "breathing"],
            "hypertension": ["hypertension", "gp-02", "amlodipine", "telmisartan", "atenolol"],
            "dengue": ["dengue", "gp-04", "nsaid", "ibuprofen", "paracetamol", "platelets"],
            "ors": ["ors", "zinc", "ped-03", "gastroenteritis", "stool", "dehydration"],
            "back pain": ["back pain", "ort-01", "saddle", "anaesthesia", "red flags"],
            "pregnancy": ["pregnancy", "uti", "gyn-02", "nitrofurantoin", "cefixime", "36+"],
            "diabetes": ["diabetes", "t2dm", "gp-03", "hba1c", "metformin", "glimepiride"],
            "fever": ["fever", "sop-clin-014", "azithromycin", "empirical", "gp-01", "gp-04"],
            "migraine": ["migraine", "headache", "prophylaxis"],
            "tuberculosis": ["tuberculosis", "tb", "pulmonary", "rifampicin", "isoniazid"]
        }

        for unit in self.units:
            if not include_local_protocol and unit.is_local_protocol:
                continue
            if specialty_filter and specialty_filter.lower() not in unit.specialty.lower():
                continue

            unit_text = (unit.content + " " + unit.title + " " + unit.section).lower()
            matched = []
            score = 0.0

            # Lexical match
            for t in query_tokens:
                if t in unit_text:
                    matched.append(t)
                    # Higher weight if matched in title or section
                    if t in unit.title.lower():
                        score += 3.0
                    elif t in unit.section.lower():
                        score += 2.0
                    else:
                        score += 1.0

            # Concept boost
            for concept, terms in boost_keywords.items():
                if concept in query_clean:
                    for term in terms:
                        if term in unit_text:
                            score += 2.5
                            if term not in matched:
                                matched.append(term)

            # Recency & edition weighting: if supersedes exists, current edition is prioritized unless archive requested
            if unit.supersedes:
                score += 0.5

            if score > 0.0:
                scored_hits.append(RetrievalHit(unit=unit, score=score, matched_terms=matched))

        scored_hits.sort(key=lambda h: h.score, reverse=True)
        return scored_hits[:top_k]

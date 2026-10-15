"""Module C — Unified End-to-End Clinical AI Trace.
Takes {a draft prescription + one clinical question} and returns a single JSON trace:
- Normalization results (including unresolved items in review queue)
- All safety check results under the 8-state contract
- Grounded answer with citations or clean abstention
- Complete versioning manifest (datasets, rules, prompts, engine)
Adheres to Section 3 Module C integration contract.
"""
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import json
import sys
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from db.connection import get_connection
from module_a.safety_rail import DeterministicSafetyRail, PrescriptionItem, PrescriptionSafetyEvaluation
from module_b.answering import GroundedAnsweringEngine, GroundedAnswer

class EndToEndTracer:
    def __init__(self, db_conn=None):
        self.conn = db_conn or get_connection()
        self.rail = DeterministicSafetyRail(self.conn)
        self.qa_engine = GroundedAnsweringEngine()

    def generate_trace(self, rx_id: str, prescription_items: List[Dict[str, Any]], clinical_question: str) -> Dict[str, Any]:
        """
        Executes unified end-to-end trace integrating Module A safety rail and Module B grounded Q&A.
        """
        trace_id = f"TRACE-{datetime.now().strftime('%Y%m%d%H%M%S')}-{rx_id}"
        created_at = datetime.now().isoformat()

        # Parse prescription items
        parsed_items = [
            PrescriptionItem(
                item_no=it.get("item_no", idx + 1),
                written_product=it["written_product"],
                strength_as_written=it.get("strength_as_written"),
                dose_frequency=it.get("dose_frequency", "1-0-0"),
                clinical_note=it.get("clinical_note")
            )
            for idx, it in enumerate(prescription_items)
        ]

        # 1. Execute Module A Safety Rail
        safety_eval: PrescriptionSafetyEvaluation = self.rail.evaluate_prescription(rx_id, parsed_items)

        # 2. Execute Module B Grounded Q&A
        qa_eval: GroundedAnswer = self.qa_engine.answer_question(clinical_question)

        # 3. Assemble Unified JSON Trace
        trace_payload = {
            "trace_metadata": {
                "trace_id": trace_id,
                "timestamp": created_at,
                "engine_version": settings.manifest.system_version,
                "engine_name": settings.manifest.engine_name
            },
            "manifest_versions": {
                "drug_master_load_batch": settings.manifest.drug_master_load_batch,
                "regulatory_register_version": settings.manifest.regulatory_register_version,
                "interaction_seed_version": settings.manifest.interaction_seed_version,
                "safety_rule_version": settings.manifest.safety_rule_version,
                "corpus_version": settings.manifest.corpus_version
            },
            "prescription_evaluation": {
                "rx_id": safety_eval.rx_id,
                "overall_state": safety_eval.overall_state,
                "highest_severity": safety_eval.highest_severity,
                "items_verified": safety_eval.items_verified,
                "summary_evidence": safety_eval.summary_evidence,
                "normalization_results": safety_eval.normalization_results,
                "safety_checks": [
                    {
                        "check_name": c.check_name,
                        "state": c.state,
                        "severity": c.severity,
                        "evidence": c.evidence,
                        "rule_version": c.rule_version,
                        "data_version": c.data_version,
                        "provenance": c.provenance
                    }
                    for c in safety_eval.individual_checks
                ],
                "cumulative_daily_exposures": [
                    {
                        "ingredient_name": c.ingredient_name,
                        "total_daily_mg": c.total_daily_mg,
                        "max_recommended_daily_mg": c.max_recommended_daily_mg,
                        "exceeds_threshold": c.exceeds_threshold,
                        "is_prn_sos": c.is_prn_sos,
                        "contributing_products": c.contributing_products
                    }
                    for c in safety_eval.cumulative_exposures
                ]
            },
            "grounded_clinical_qa": {
                "question": qa_eval.question_text,
                "state": qa_eval.state,
                "answer": qa_eval.answer_text,
                "claim_citations": qa_eval.citations,
                "abstention_reason": qa_eval.abstention_reason,
                "conflict_detected": qa_eval.conflict_detected,
                "is_dose_question": qa_eval.is_dose_question,
                "contains_local_protocol": qa_eval.contains_local_protocol,
                "retrieved_evidence_units": qa_eval.retrieved_chunks
            }
        }

        # Save trace to audit database
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO prescription_audit_traces
            (trace_id, rx_id, overall_state, highest_severity, items_count, trace_json)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (
            trace_id,
            rx_id,
            safety_eval.overall_state,
            safety_eval.highest_severity,
            len(parsed_items),
            json.dumps(trace_payload)
        ))
        self.conn.commit()

        # Save trace JSON artifact to output directory
        trace_file = settings.output_dir / "sample_end_to_end_trace.json"
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(trace_payload, f, indent=2)

        return trace_payload

def main():
    parser = argparse.ArgumentParser(description="BRAHMO End-to-End Clinical AI Trace Runner")
    parser.add_argument("--rx", default="RX01", help="Prescription template ID to run (e.g. RX01, RX02, RX03, RX04)")
    parser.add_argument("--question", default="Which analgesic class must be avoided in suspected dengue, and why?", help="Clinical question text")
    args = parser.parse_args()

    # Sample prescription definitions from template
    sample_rx_catalog = {
        "RX01": [
            {"item_no": 1, "written_product": "Dolo 650", "strength_as_written": "650 mg", "dose_frequency": "1-0-1 x 5d", "clinical_note": "fever"},
            {"item_no": 2, "written_product": "Sinarest Tablet", "strength_as_written": "", "dose_frequency": "1-0-1 x 5d", "clinical_note": "cold"}
        ],
        "RX02": [
            {"item_no": 1, "written_product": "NimuPar-P", "strength_as_written": "", "dose_frequency": "1-0-1 x 3d", "clinical_note": "pain"}
        ],
        "RX03": [
            {"item_no": 1, "written_product": "Warf 5", "strength_as_written": "5 mg", "dose_frequency": "0-0-1", "clinical_note": "AF, ongoing"},
            {"item_no": 2, "written_product": "Azee 500", "strength_as_written": "500 mg", "dose_frequency": "1-0-0 x 3d", "clinical_note": "RTI"}
        ],
        "RX04": [
            {"item_no": 1, "written_product": "Telma", "strength_as_written": "", "dose_frequency": "1-0-0", "clinical_note": "HTN"}
        ]
    }

    rx_items = sample_rx_catalog.get(args.rx, sample_rx_catalog["RX01"])
    tracer = EndToEndTracer()
    trace = tracer.generate_trace(args.rx, rx_items, args.question)

    print("================================================================================")
    print("BRAHMO CLINICAL AI — MODULE C END-TO-END TRACE GENERATED")
    print("================================================================================")
    print(f"Trace ID:         {trace['trace_metadata']['trace_id']}")
    print(f"Rx ID:            {trace['prescription_evaluation']['rx_id']}")
    print(f"Safety State:     {trace['prescription_evaluation']['overall_state']} ({trace['prescription_evaluation']['highest_severity']})")
    print(f"Safety Evidence:  {trace['prescription_evaluation']['summary_evidence']}")
    print(f"\nClinical Q&A:     {trace['grounded_clinical_qa']['question']}")
    print(f"QA State:         {trace['grounded_clinical_qa']['state']}")
    print(f"Citations:        {trace['grounded_clinical_qa']['claim_citations']}")
    print(f"Answer:\n{trace['grounded_clinical_qa']['answer']}")
    print("================================================================================")
    print(f"[*] Trace successfully checked into: {settings.output_dir / 'sample_end_to_end_trace.json'}")

if __name__ == "__main__":
    main()

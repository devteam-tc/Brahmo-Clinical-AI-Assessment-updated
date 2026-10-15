"""Module A.7 — Seeded Safety Rail Demonstration Runner.
Runs all 10 draft prescriptions from seed_prescriptions_template.csv.
Evaluates known-bad cases, clean cases, and unknown/ambiguous cases.
Outputs completed CSV and logs full evidence notes.
"""
import csv
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from db.connection import get_connection
from module_a.safety_rail import DeterministicSafetyRail, PrescriptionItem

def run_seeded_demonstration():
    conn = get_connection()
    rail = DeterministicSafetyRail(conn)
    
    template_path = settings.data.seed_prescriptions_csv
    output_path = settings.output_dir / "seed_prescriptions_completed.csv"
    root_output_path = settings.data.seed_prescriptions_csv.parent / "seed_prescriptions_completed.csv"
    
    print("================================================================================")
    print("BRAHMO CLINICAL AI — MODULE A.7 SEEDED PRESCRIPTION DEMONSTRATION")
    print("================================================================================")
    
    # Read rows
    with open(template_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
    # Group by rx_id
    rx_groups: Dict[str, List[Dict[str, str]]] = {}
    for r in rows:
        rx_groups.setdefault(r["rx_id"].strip(), []).append(r)
        
    completed_rows = []
    
    for rx_id, rx_rows in sorted(rx_groups.items()):
        items = []
        for r in rx_rows:
            items.append(PrescriptionItem(
                item_no=int(r["item_no"]),
                written_product=r["written_product"].strip(),
                strength_as_written=r["strength_as_written"].strip() if r["strength_as_written"].strip() else None,
                dose_frequency=r["dose_frequency"].strip() if r["dose_frequency"].strip() else "1-0-0",
                clinical_note=r["clinical_note"].strip() if r["clinical_note"].strip() else None
            ))
            
        eval_result = rail.evaluate_prescription(rx_id, items)
        
        print(f"\n--------------------------------------------------------------------------------")
        print(f"Rx ID: {rx_id} | Products: {[it.written_product for it in items]}")
        print(f"Overall State:    {eval_result.overall_state}")
        print(f"Highest Severity: {eval_result.highest_severity}")
        print(f"Evidence Note:    {eval_result.summary_evidence}")
        if eval_result.cumulative_exposures:
            print("Cumulative Daily Exposures:")
            for c in eval_result.cumulative_exposures:
                limit_info = f" (Threshold: {c.max_recommended_daily_mg} mg/day)" if c.max_recommended_daily_mg else ""
                print(f"  - {c.ingredient_name}: {c.total_daily_mg:g} mg/day{limit_info} [{'EXCEEDS' if c.exceeds_threshold else 'SAFE'}]")

        for r in rx_rows:
            r_copy = dict(r)
            r_copy["candidate_rail_output_state"] = eval_result.overall_state
            r_copy["candidate_evidence_note"] = eval_result.summary_evidence
            completed_rows.append(r_copy)

    # Write completed CSV to output_dir and root
    fieldnames = list(rows[0].keys())
    if "candidate_rail_output_state" not in fieldnames:
        fieldnames.append("candidate_rail_output_state")
    if "candidate_evidence_note" not in fieldnames:
        fieldnames.append("candidate_evidence_note")
        
    for out_p in [output_path, root_output_path]:
        with open(out_p, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(completed_rows)
            
    print(f"\n[*] Completed seeded demonstration saved to:\n  - {output_path}\n  - {root_output_path}")

if __name__ == "__main__":
    run_seeded_demonstration()

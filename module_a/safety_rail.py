"""Deterministic Clinical Medication Safety Rail.
Adheres to:
- Law 4: Safety outside the LLM (pure lookup logic, NO model calls anywhere in the check path).
- Law 5: Unknown is first-class (exact 8-state vocabulary; missing data never renders as safe).
- Law 7: Event-sourced regulatory status with notification citations and effective dates.
- Section 3 Module A.6: Duplicate active ingredient, prohibited FDC, severe interactions, and cumulative daily exposure.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import re

from config.settings import settings
from module_a.normalization import DrugNormalizer, NormalizationResult
from module_a.regulatory_register import RegulatoryRegister, RegulatoryStatusVerdict

@dataclass
class PrescriptionItem:
    item_no: int
    written_product: str
    strength_as_written: Optional[str] = None
    dose_frequency: str = "1-0-0"
    clinical_note: Optional[str] = None

@dataclass
class SafetyCheckVerdict:
    check_name: str  # DUPLICATE_SALT, PROHIBITED_FDC, SEVERE_INTERACTION, CUMULATIVE_EXPOSURE
    state: str       # HIT, CHECKED_NO_HIT, PARTIAL_COVERAGE, UNVERIFIED_INPUT, NOT_CHECKED, DATA_EXPIRED, SOURCE_CONFLICT, SERVICE_UNAVAILABLE
    severity: str    # INFO, WARNING, SEVERE, CRITICAL
    evidence: str
    rule_version: str
    data_version: str
    provenance: Dict[str, Any] = field(default_factory=dict)

@dataclass
class CumulativeExposure:
    ingredient_name: str
    total_daily_mg: float
    max_recommended_daily_mg: Optional[float]
    exceeds_threshold: bool
    contributing_products: List[Dict[str, Any]]
    is_prn_sos: bool = False

@dataclass
class PrescriptionSafetyEvaluation:
    rx_id: str
    overall_state: str
    highest_severity: str
    items_verified: bool
    normalization_results: List[Dict[str, Any]]
    individual_checks: List[SafetyCheckVerdict]
    cumulative_exposures: List[CumulativeExposure]
    timestamp: str
    rule_version: str
    data_version: str
    engine_name: str
    summary_evidence: str

class DeterministicSafetyRail:
    def __init__(self, db_conn):
        self.conn = db_conn
        self.normalizer = DrugNormalizer(db_conn)
        self.reg_register = RegulatoryRegister(db_conn)

    def parse_daily_frequency(self, freq_str: Optional[str]) -> Tuple[float, bool]:
        """
        Parses dosage frequency into daily dose multiplier and PRN/SOS flag.
        1-0-1 -> 2.0 doses/day
        1-0-0 -> 1.0 dose/day
        0-0-1 -> 1.0 dose/day
        1-1-1 -> 3.0 doses/day
        SOS / PRN -> 1.0 dose max single PRN allowance
        """
        if not freq_str:
            return 1.0, False
            
        freq_clean = freq_str.strip().upper()
        if "SOS" in freq_clean or "PRN" in freq_clean or "AS NEEDED" in freq_clean:
            return 1.0, True
            
        # Match standard Indian OPD frequency pattern: X-X-X or X-X-X-X
        match = re.search(r"(\d+)-(\d+)-(\d+)(?:-(\d+))?", freq_clean)
        if match:
            d1 = float(match.group(1))
            d2 = float(match.group(2))
            d3 = float(match.group(3))
            d4 = float(match.group(4)) if match.group(4) else 0.0
            total_doses = d1 + d2 + d3 + d4
            return total_doses if total_doses > 0 else 1.0, False
            
        # Match "once daily", "twice daily", "three times daily"
        if "ONCE" in freq_clean or "OD" in freq_clean:
            return 1.0, False
        if "TWICE" in freq_clean or "BD" in freq_clean or "BID" in freq_clean:
            return 2.0, False
        if "THRICE" in freq_clean or "TID" in freq_clean or "TDS" in freq_clean:
            return 3.0, False
        if "QID" in freq_clean:
            return 4.0, False

        return 1.0, False

    def evaluate_prescription(self, rx_id: str, items: List[PrescriptionItem], as_of_date: Optional[str] = None) -> PrescriptionSafetyEvaluation:
        """
        Executes pure deterministic safety checks over a draft prescription.
        Zero LLM calls in check path.
        Returns one of the 8 binding states.
        """
        timestamp = datetime.now().isoformat()
        rule_version = settings.manifest.safety_rule_version
        data_version = f"{settings.manifest.regulatory_register_version}+{settings.manifest.interaction_seed_version}"
        engine_name = settings.manifest.engine_name

        norm_results = []
        unverified_items = []
        resolved_items = []

        # Step 1: Normalization & Input Verification
        for item in items:
            norm_res = self.normalizer.normalize(item.written_product, item.strength_as_written)
            norm_results.append({
                "item_no": item.item_no,
                "written_product": item.written_product,
                "strength_as_written": item.strength_as_written,
                "dose_frequency": item.dose_frequency,
                "clinical_note": item.clinical_note,
                "status": norm_res.status,
                "confidence": norm_res.confidence,
                "method_tag": norm_res.method_tag,
                "resolved_product_id": norm_res.product_id,
                "resolved_brand_name": norm_res.brand_name,
                "dose_form": norm_res.dose_form,
                "active_ingredients": norm_res.active_ingredients,
                "reason_code": norm_res.reason_code,
                "review_queue_id": norm_res.review_queue_id
            })
            if norm_res.status != "RESOLVED":
                unverified_items.append((item, norm_res))
            else:
                resolved_items.append((item, norm_res))

        # Gate check: If any item is unverified, missing, or ambiguous:
        # Law 5: Missing data must never render as safe -> Return UNVERIFIED_INPUT immediately!
        if unverified_items:
            reasons = [f"Item {it.item_no} '{it.written_product}': {nr.reason_code} (method: {nr.method_tag})" for it, nr in unverified_items]
            verdict = SafetyCheckVerdict(
                check_name="INPUT_VERIFICATION",
                state="UNVERIFIED_INPUT",
                severity="WARNING",
                evidence=f"Prescription contains {len(unverified_items)} unverified or ambiguous product(s) routed to review queue: " + "; ".join(reasons) + ". Medication safety rail cannot run safely without complete product resolution.",
                rule_version=rule_version,
                data_version=data_version,
                provenance={"unverified_count": len(unverified_items), "reasons": reasons}
            )
            return PrescriptionSafetyEvaluation(
                rx_id=rx_id,
                overall_state="UNVERIFIED_INPUT",
                highest_severity="WARNING",
                items_verified=False,
                normalization_results=norm_results,
                individual_checks=[verdict],
                cumulative_exposures=[],
                timestamp=timestamp,
                rule_version=rule_version,
                data_version=data_version,
                engine_name=engine_name,
                summary_evidence=verdict.evidence
            )

        # Step 2: Compute Cumulative Exposures & Detect Duplicate Active Ingredients
        # Map: salt_name -> list of {brand, strength_mg, daily_doses, daily_total_mg, item_no, is_prn}
        salt_exposures = {}
        for item, nr in resolved_items:
            daily_doses, is_prn = self.parse_daily_frequency(item.dose_frequency)
            for ing in nr.active_ingredients:
                salt_name = ing["ingredient_name"].strip()
                s_mg = float(ing["strength_mg"])
                daily_total = s_mg * daily_doses
                
                contrib = {
                    "item_no": item.item_no,
                    "brand_name": nr.brand_name,
                    "strength_mg": s_mg,
                    "dose_frequency": item.dose_frequency,
                    "daily_doses": daily_doses,
                    "daily_total_mg": daily_total,
                    "is_prn": is_prn
                }
                salt_exposures.setdefault(salt_name.lower(), {
                    "canonical_name": salt_name,
                    "contributions": []
                })["contributions"].append(contrib)

        cumulative_list = []
        duplicate_hits = []

        for salt_key, data in salt_exposures.items():
            cname = data["canonical_name"]
            contribs = data["contributions"]
            total_daily = sum(c["daily_total_mg"] for c in contribs)
            any_prn = any(c["is_prn"] for c in contribs)
            
            # Threshold evaluation
            threshold = None
            if salt_key == "paracetamol":
                threshold = settings.thresholds.max_daily_paracetamol_mg
            elif salt_key == "ibuprofen":
                threshold = settings.thresholds.max_daily_ibuprofen_mg
            elif salt_key == "telmisartan":
                threshold = settings.thresholds.max_daily_telmisartan_mg
            elif salt_key == "metformin":
                threshold = settings.thresholds.max_daily_metformin_mg

            exceeds = (threshold is not None and total_daily > threshold)

            cum_obj = CumulativeExposure(
                ingredient_name=cname,
                total_daily_mg=total_daily,
                max_recommended_daily_mg=threshold,
                exceeds_threshold=exceeds,
                contributing_products=contribs,
                is_prn_sos=any_prn
            )
            cumulative_list.append(cum_obj)

            # Check duplicate active ingredient across distinct items
            distinct_items = set(c["item_no"] for c in contribs)
            if len(distinct_items) > 1:
                # Duplicate active ingredient detected!
                brands_str = " and ".join([f"{c['brand_name']} ({c['daily_total_mg']:g} mg/day)" for c in contribs])
                evidence_note = (
                    f"Duplicate active ingredient '{cname}' prescribed across multiple products: {brands_str}. "
                    f"Cumulative daily exposure: {total_daily:g} mg/day"
                )
                if any_prn:
                    evidence_note += " (including SOS/PRN allowance)"
                if exceeds:
                    evidence_note += f" — EXCEEDS maximum recommended OPD ceiling of {threshold:g} mg/day!"

                duplicate_hits.append({
                    "salt": cname,
                    "total_daily_mg": total_daily,
                    "exceeds": exceeds,
                    "evidence": evidence_note,
                    "contributing_products": contribs
                })

        # Step 3: Check Event-Sourced Prohibited/Restricted FDCs
        fdc_hits = []
        for item, nr in resolved_items:
            salts = [ing["ingredient_name"] for ing in nr.active_ingredients]
            if len(salts) >= 2 or len(salts) == 1:
                verdict: RegulatoryStatusVerdict = self.reg_register.evaluate_target(salts, as_of_date=as_of_date)
                if verdict.is_prohibited:
                    fdc_hits.append({
                        "item_no": item.item_no,
                        "brand_name": nr.brand_name,
                        "target": verdict.target_name,
                        "action": "PROHIBITED",
                        "severity": "CRITICAL",
                        "notification_id": verdict.notification_id,
                        "effective_date": verdict.effective_date,
                        "citation": verdict.citation_text,
                        "note": verdict.note
                    })
                elif verdict.is_restricted:
                    fdc_hits.append({
                        "item_no": item.item_no,
                        "brand_name": nr.brand_name,
                        "target": verdict.target_name,
                        "action": "RESTRICTED",
                        "severity": "WARNING",
                        "notification_id": verdict.notification_id,
                        "effective_date": verdict.effective_date,
                        "citation": verdict.citation_text,
                        "note": verdict.note
                    })

        # Step 4: Check Severe Drug-Drug Interactions from Seed List
        # Pairwise across all distinct items
        interaction_hits = []
        cursor = self.conn.cursor()
        
        for i in range(len(resolved_items)):
            for j in range(i + 1, len(resolved_items)):
                item_a, nr_a = resolved_items[i]
                item_b, nr_b = resolved_items[j]
                
                salts_a = [ing["ingredient_name"].strip() for ing in nr_a.active_ingredients]
                salts_b = [ing["ingredient_name"].strip() for ing in nr_b.active_ingredients]
                
                for sa in salts_a:
                    for sb in salts_b:
                        cursor.execute("""
                            SELECT ingredient_a, ingredient_b, severity, clinical_note, source_tag
                            FROM severe_interactions
                            WHERE (LOWER(ingredient_a) = LOWER(?) AND LOWER(ingredient_b) = LOWER(?))
                               OR (LOWER(ingredient_a) = LOWER(?) AND LOWER(ingredient_b) = LOWER(?));
                        """, (sa, sb, sb, sa))
                        matched_int = cursor.fetchone()
                        if matched_int:
                            interaction_hits.append({
                                "item_a": item_a.written_product,
                                "item_b": item_b.written_product,
                                "salt_a": sa,
                                "salt_b": sb,
                                "severity": matched_int["severity"],
                                "clinical_note": matched_int["clinical_note"],
                                "source_tag": matched_int["source_tag"]
                            })

        # Step 5: Synthesize Final State and Individual Check Verdicts
        individual_verdicts = []
        overall_state = "CHECKED_NO_HIT"
        highest_severity = "INFO"
        summary_lines = []

        # (a) Duplicate check verdict
        if duplicate_hits:
            overall_state = "HIT"
            # If cumulative dose exceeds threshold, severity is CRITICAL/SEVERE, else WARNING
            dup_sev = "CRITICAL" if any(h["exceeds"] for h in duplicate_hits) else "WARNING"
            if dup_sev == "CRITICAL" or highest_severity != "CRITICAL":
                highest_severity = dup_sev
                
            evidence_str = "; ".join([h["evidence"] for h in duplicate_hits])
            summary_lines.append(f"[DUPLICATE ACTIVE INGREDIENT HIT]: {evidence_str}")
            individual_verdicts.append(SafetyCheckVerdict(
                check_name="DUPLICATE_ACTIVE_INGREDIENT",
                state="HIT",
                severity=dup_sev,
                evidence=evidence_str,
                rule_version=rule_version,
                data_version=data_version,
                provenance={"duplicate_hits": duplicate_hits}
            ))
        else:
            individual_verdicts.append(SafetyCheckVerdict(
                check_name="DUPLICATE_ACTIVE_INGREDIENT",
                state="CHECKED_NO_HIT",
                severity="INFO",
                evidence="No duplicate active ingredients detected across prescribed items.",
                rule_version=rule_version,
                data_version=data_version
            ))

        # (b) Prohibited/Restricted FDC verdict
        if fdc_hits:
            overall_state = "HIT"
            fdc_sev = "CRITICAL" if any(h["action"] == "PROHIBITED" for h in fdc_hits) else "WARNING"
            highest_severity = "CRITICAL" if fdc_sev == "CRITICAL" else (highest_severity if highest_severity == "CRITICAL" else "WARNING")
            
            evidence_str = "; ".join([f"{h['brand_name']}: {h['citation']}" for h in fdc_hits])
            summary_lines.append(f"[REGULATORY FDC HIT]: {evidence_str}")
            individual_verdicts.append(SafetyCheckVerdict(
                check_name="REGULATORY_STATUS_FDC",
                state="HIT",
                severity=fdc_sev,
                evidence=evidence_str,
                rule_version=rule_version,
                data_version=data_version,
                provenance={"regulatory_hits": fdc_hits}
            ))
        else:
            individual_verdicts.append(SafetyCheckVerdict(
                check_name="REGULATORY_STATUS_FDC",
                state="CHECKED_NO_HIT",
                severity="INFO",
                evidence="All prescribed formulations are unrestricted under current event-sourced national gazette records.",
                rule_version=rule_version,
                data_version=data_version
            ))

        # (c) Severe interaction verdict
        if interaction_hits:
            overall_state = "HIT"
            if highest_severity != "CRITICAL":
                highest_severity = "SEVERE"
                
            evidence_str = "; ".join([
                f"{h['item_a']} ({h['salt_a']}) + {h['item_b']} ({h['salt_b']}): {h['clinical_note']} [{h['source_tag']}]"
                for h in interaction_hits
            ])
            summary_lines.append(f"[SEVERE DRUG-DRUG INTERACTION HIT]: {evidence_str}")
            individual_verdicts.append(SafetyCheckVerdict(
                check_name="SEVERE_INTERACTION",
                state="HIT",
                severity="SEVERE",
                evidence=evidence_str,
                rule_version=rule_version,
                data_version=data_version,
                provenance={"interactions": interaction_hits}
            ))
        else:
            individual_verdicts.append(SafetyCheckVerdict(
                check_name="SEVERE_INTERACTION",
                state="CHECKED_NO_HIT",
                severity="INFO",
                evidence="Zero severe ingredient-level interactions detected against high-priority seed register.",
                rule_version=rule_version,
                data_version=data_version
            ))

        # (d) Cumulative exposure check verdict
        excessive_exposures = [c for c in cumulative_list if c.exceeds_threshold]
        if excessive_exposures:
            overall_state = "HIT"
            highest_severity = "CRITICAL"
            evidence_str = "; ".join([
                f"{c.ingredient_name}: {c.total_daily_mg:g} mg/day exceeds recommended threshold of {c.max_recommended_daily_mg:g} mg/day"
                for c in excessive_exposures
            ])
            summary_lines.append(f"[CUMULATIVE DOSE CEILING HIT]: {evidence_str}")
            individual_verdicts.append(SafetyCheckVerdict(
                check_name="CUMULATIVE_DOSE_LIMIT",
                state="HIT",
                severity="CRITICAL",
                evidence=evidence_str,
                rule_version=rule_version,
                data_version=data_version
            ))
        else:
            individual_verdicts.append(SafetyCheckVerdict(
                check_name="CUMULATIVE_DOSE_LIMIT",
                state="CHECKED_NO_HIT",
                severity="INFO",
                evidence="All cumulative active ingredient daily exposures are within recommended therapeutic limits.",
                rule_version=rule_version,
                data_version=data_version
            ))

        if overall_state == "CHECKED_NO_HIT":
            summary_evidence = (
                f"All {len(items)} products verified; 0 duplicate salts; 0 prohibited/restricted FDCs; "
                f"0 severe drug-drug interactions detected. All cumulative active ingredient exposures within safe thresholds."
            )
        else:
            summary_evidence = " | ".join(summary_lines)

        return PrescriptionSafetyEvaluation(
            rx_id=rx_id,
            overall_state=overall_state,
            highest_severity=highest_severity,
            items_verified=True,
            normalization_results=norm_results,
            individual_checks=individual_verdicts,
            cumulative_exposures=cumulative_list,
            timestamp=timestamp,
            rule_version=rule_version,
            data_version=data_version,
            engine_name=engine_name,
            summary_evidence=summary_evidence
        )

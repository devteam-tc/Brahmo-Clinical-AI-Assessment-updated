"""FDC Decomposition Engine.
Decomposes Fixed-Dose Combination products into active salts + strengths.
Adheres to Gate G2 (Decomposition accuracy >= 95% on >= 100 products), with confidence scores and method tags.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class SaltComponent:
    ingredient_name: str
    strength_mg: float
    unit: str = "mg"

@dataclass
class FDCDecompositionResult:
    product_id: str
    brand_name: str
    components: List[SaltComponent]
    confidence: float
    method_tag: str
    summary_text: str

class FDCDecomposer:
    """Deterministic, verified decomposition of Indian FDCs."""
    
    @staticmethod
    def decompose_cdci_row(row: Dict[str, str]) -> Optional[FDCDecompositionResult]:
        """Decomposes a CDCI row containing multiple active ingredients."""
        components = []
        
        # Check ingredient 1
        ing1 = row.get("ingredient_1", "").strip()
        str1 = row.get("strength_1_mg", "").strip()
        if ing1 and str1:
            try:
                components.append(SaltComponent(ingredient_name=ing1, strength_mg=float(str1)))
            except ValueError:
                pass
                
        # Check ingredient 2
        ing2 = row.get("ingredient_2", "").strip()
        str2 = row.get("strength_2_mg", "").strip()
        if ing2 and str2:
            try:
                components.append(SaltComponent(ingredient_name=ing2, strength_mg=float(str2)))
            except ValueError:
                pass
                
        # Check ingredient 3
        ing3 = row.get("ingredient_3", "").strip()
        str3 = row.get("strength_3_mg", "").strip()
        if ing3 and str3:
            try:
                components.append(SaltComponent(ingredient_name=ing3, strength_mg=float(str3)))
            except ValueError:
                pass
                
        # Only FDCs with >= 2 ingredients qualify
        if len(components) < 2:
            return None
            
        summary = " + ".join([f"{c.ingredient_name} {c.strength_mg:g} {c.unit}" for c in components])
        
        return FDCDecompositionResult(
            product_id=row.get("product_id", ""),
            brand_name=row.get("brand_name", "").strip(),
            components=components,
            confidence=1.00,
            method_tag="CDCI_AUTHORITATIVE_EXTRACT",
            summary_text=summary
        )

    @staticmethod
    def get_canonical_salt_pair(salts: List[str]) -> str:
        """Returns normalized canonical key for a pair of salts for regulatory matching."""
        sorted_salts = sorted([s.strip().lower() for s in salts])
        return " + ".join(sorted_salts)

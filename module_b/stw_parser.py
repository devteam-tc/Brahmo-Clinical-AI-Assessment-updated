"""STW PDF Parser and Clinical Decision Unit Chunker.
Extracts ICMR STW one-pagers and clinic protocol into clinically meaningful decision units.
Adheres to Section 3 Module B.1: Chunking into recommendations, workflow steps, contraindications, never blind token slices.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional
import zlib
import base64
import re
import glob

from config.settings import settings

@dataclass
class ClinicalDecisionUnit:
    chunk_id: str
    doc_code: str
    title: str
    specialty: str
    version: str
    effective_date: str
    supersedes: Optional[str]
    section: str
    decision_type: str
    page_anchor: str
    content: str
    keywords: List[str]
    is_local_protocol: bool

class STWParser:
    """Parses ICMR STW PDF one-pagers without external binary dependencies."""
    
    @staticmethod
    def extract_raw_pdf_text(pdf_path: Path) -> str:
        with open(pdf_path, "rb") as f:
            data = f.read()
        s_idx = data.find(b"stream")
        if s_idx == -1:
            return ""
        start = data.find(b"\n", s_idx) + 1
        end = data.find(b"~>", start) + 2
        raw_stream = data[start:end]
        try:
            a85 = base64.a85decode(raw_stream, adobe=True)
            decompressed = zlib.decompress(a85)
        except Exception:
            return ""
            
        lines = []
        for match in re.finditer(rb"\((.*?)\)\s*Tj", decompressed):
            raw_str = match.group(1).decode("latin1", errors="replace")
            cleaned = (
                raw_str.replace("\\(", "(")
                .replace("\\)", ")")
                .replace("\\227", "—")
                .replace("\\267", "·")
                .replace("\\226", "–")
                .replace("\\177", "•")
                .replace("\\263", ">=")
                .replace("\\243", "<=")
            )
            lines.append(cleaned)
        return "\n".join(lines)

    @staticmethod
    def parse_pdf_to_units(pdf_path: Path) -> List[ClinicalDecisionUnit]:
        raw_text = STWParser.extract_raw_pdf_text(pdf_path)
        lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
        
        # Extract metadata
        title = "Standard Treatment Workflow"
        doc_code = "STW-UNKNOWN"
        version = "2024.1"
        effective_date = "2024-01-01"
        supersedes = None
        specialty = "General Practice"
        
        if "PED" in pdf_path.name:
            specialty = "Pediatrics"
        elif "GYN" in pdf_path.name:
            specialty = "Gynaecology"
        elif "ORT" in pdf_path.name:
            specialty = "Orthopaedics"
        elif "GP" in pdf_path.name:
            specialty = "General Practice"
            
        # Parse header lines
        for i, line in enumerate(lines[:12]):
            if "Code:" in line:
                m = re.search(r"Code:\s*([A-Z0-9\-]+)", line)
                if m:
                    doc_code = m.group(1)
            elif "Version:" in line:
                m_ver = re.search(r"Version:\s*([0-9\.]+)", line)
                if m_ver:
                    version = m_ver.group(1)
                m_eff = re.search(r"Effective:\s*([0-9\-]+)", line)
                if m_eff:
                    effective_date = m_eff.group(1)
            elif "Supersedes:" in line:
                m_sup = re.search(r"Supersedes:\s*(.+)", line)
                if m_sup:
                    supersedes = m_sup.group(1).strip()
            elif i == 1:
                title = line.replace("—", "-").strip()

        # Sections to detect
        section_headers = [
            "ASSESS", "CONFIRM", "DIAGNOSE", "CLASSIFY", "ASSESS DEHYDRATION", "SCREEN", "SUSPECT",
            "FIRST-LINE MANAGEMENT", "FIRST-LINE MANAGEMENT (CURRENT)", "FIRST-LINE MANAGEMENT (THIS 2021 EDITION)",
            "OPD MANAGEMENT", "WARNING SIGNS — ADMIT", "RED FLAGS — IMAGE/REFER", "RED FLAGS — REFER",
            "AVOID", "DO NOT", "MONITOR", "REVIEW", "TARGETS", "COUNSEL", "REFER", "STATUS"
        ]
        
        # Segment into sections
        current_section = "GENERAL"
        section_bullets = {}
        
        for line in lines[4:]:
            # Check if line matches a known section header
            matched_header = None
            for hdr in section_headers:
                if line.upper() == hdr or line.upper().startswith(hdr + " —") or line.upper().startswith(hdr + ":"):
                    matched_header = hdr
                    break
            
            if matched_header:
                current_section = matched_header
                section_bullets.setdefault(current_section, [])
            elif line.startswith("•") or line.startswith("-") or line.startswith(">="):
                clean_bullet = line.lstrip("•- ").strip()
                if clean_bullet and not clean_bullet.startswith("SYNTHETIC ASSESSMENT DOCUMENT"):
                    section_bullets.setdefault(current_section, []).append(clean_bullet)
            elif not line.startswith("SYNTHETIC ASSESSMENT DOCUMENT"):
                # Continuation or standalone recommendation
                section_bullets.setdefault(current_section, []).append(line)

        units = []
        for sec, items in section_bullets.items():
            if not items:
                continue
            # Categorize decision type
            sec_upper = sec.upper()
            if "RED FLAGS" in sec_upper or "WARNING" in sec_upper or "REFER" in sec_upper:
                dec_type = "RED_FLAG_REFERRAL"
            elif "AVOID" in sec_upper or "DO NOT" in sec_upper:
                dec_type = "CONTRAINDICATION"
            elif "DIAGNOSE" in sec_upper or "ASSESS" in sec_upper or "CONFIRM" in sec_upper or "SCREEN" in sec_upper:
                dec_type = "DIAGNOSTIC_CRITERIA"
            elif "MONITOR" in sec_upper or "REVIEW" in sec_upper:
                dec_type = "MONITORING"
            else:
                dec_type = "RECOMMENDATION"

            # Combine items into a clinically coherent recommendation unit
            content_text = " • ".join(items)
            chunk_id = f"{doc_code}_v{version}_{sec.replace(' ', '_').replace('-', '_')}"
            
            # Keywords extraction
            kw = [w.lower() for w in re.findall(r"\b[A-Za-z0-9\-]{3,}\b", content_text + " " + title)]
            
            unit = ClinicalDecisionUnit(
                chunk_id=chunk_id,
                doc_code=doc_code,
                title=title,
                specialty=specialty,
                version=version,
                effective_date=effective_date,
                supersedes=supersedes,
                section=sec,
                decision_type=dec_type,
                page_anchor="Page 1",
                content=content_text,
                keywords=list(set(kw)),
                is_local_protocol=False
            )
            units.append(unit)

        return units

    @staticmethod
    def parse_local_protocol(md_path: Path) -> List[ClinicalDecisionUnit]:
        """Parses local clinic fever protocol as organization-level knowledge."""
        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()
            
        doc_code = "SOP-CLIN-014"
        title = "Adult Acute Undifferentiated Fever: Local Treatment Protocol"
        specialty = "Clinic SOP (Sunrise Multi-speciality Clinic)"
        version = "2.1"
        effective_date = "2026-03-10"
        
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        units = []
        
        protocol_steps = []
        for line in lines:
            if re.match(r"^\d+\.", line):
                protocol_steps.append(line)
                
        for step in protocol_steps:
            m = re.match(r"^(\d+)\.\s*(.+)", step)
            if m:
                step_no = m.group(1)
                content = m.group(2).replace("**", "")
                sec = f"STEP_{step_no}"
                dec_type = "RECOMMENDATION"
                if "Azithromycin" in content:
                    sec = "EMPIRICAL_ANTIBIOTIC_INITIATION"
                
                kw = [w.lower() for w in re.findall(r"\b[A-Za-z0-9\-]{3,}\b", content + " " + title)]
                units.append(ClinicalDecisionUnit(
                    chunk_id=f"SOP_CLIN_014_v2.1_{sec}",
                    doc_code=doc_code,
                    title=title,
                    specialty=specialty,
                    version=version,
                    effective_date=effective_date,
                    supersedes=None,
                    section=sec,
                    decision_type=dec_type,
                    page_anchor="Page 1",
                    content=content,
                    keywords=list(set(kw)),
                    is_local_protocol=True
                ))
                
        return units

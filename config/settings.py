"""Configuration settings for BRAHMO Clinical AI System.
Follows Rule 4 / Law 8: No hardcoded constants; all thresholds, paths, and versions are configurable.
"""
from dataclasses import dataclass, field
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

@dataclass(frozen=True)
class DatabaseSettings:
    db_path: Path = BASE_DIR / "brahmo_clinical.db"
    migrations_dir: Path = BASE_DIR / "db" / "migrations"
    busy_timeout_ms: int = 5000
    wal_mode: bool = True

@dataclass(frozen=True)
class DataPaths:
    cdci_csv: Path = BASE_DIR / "cdci_drug_subset.csv"
    pharmacy_stock_csv: Path = BASE_DIR / "pharmacy_stock.csv"
    nlem_csv: Path = BASE_DIR / "nlem_extract.csv"
    jan_aushadhi_csv: Path = BASE_DIR / "jan_aushadhi_extract.csv"
    regulatory_gazette_csv: Path = BASE_DIR / "regulatory_gazette_events.csv"
    severe_interaction_csv: Path = BASE_DIR / "severe_interaction_seed.csv"
    seed_prescriptions_csv: Path = BASE_DIR / "seed_prescriptions_template.csv"
    local_protocol_md: Path = BASE_DIR / "local_protocol_acute_fever.md"
    sample_questions_md: Path = BASE_DIR / "sample_questions.md"
    stw_pdf_pattern: str = "STW_*.pdf"

@dataclass(frozen=True)
class SafetyRailThresholds:
    # Cumulative daily maximum thresholds (mg/day)
    # Sourced from STW-GP-01, STW-GP-04 and clinical pharmacopeia
    max_daily_paracetamol_mg: float = 3000.0  # Max OPD limit per STW-GP-01 / STW-GP-04
    max_daily_paracetamol_ceiling_mg: float = 4000.0  # Absolute upper ceiling
    max_daily_ibuprofen_mg: float = 1200.0   # 400mg tid per STW-ORT-01
    max_daily_telmisartan_mg: float = 80.0    # STW-GP-02 max dose
    max_daily_metformin_mg: float = 2000.0   # Standard therapeutic ceiling
    
    # Confidence scoring thresholds for drug normalization
    exact_match_confidence: float = 1.00
    cleaned_token_match_confidence: float = 0.95
    heuristic_salt_match_confidence: float = 0.85
    min_auto_accept_confidence: float = 0.90  # Below this, lands in review queue

@dataclass(frozen=True)
class VersionManifest:
    system_version: str = "1.0.0-prod"
    engine_name: str = "BrahmoClinicalEngine"
    drug_master_load_batch: str = "BATCH-2026-10-15-01"
    regulatory_register_version: str = "GAZETTE-REG-2026.1"
    interaction_seed_version: str = "INT-SEED-2026.1"
    corpus_version: str = "STW-CORPUS-2026Q3"
    safety_rule_version: str = "RULE-SAFETY-2026.1"

@dataclass(frozen=True)
class Settings:
    db: DatabaseSettings = field(default_factory=DatabaseSettings)
    data: DataPaths = field(default_factory=DataPaths)
    thresholds: SafetyRailThresholds = field(default_factory=SafetyRailThresholds)
    manifest: VersionManifest = field(default_factory=VersionManifest)
    output_dir: Path = BASE_DIR / "output"

settings = Settings()

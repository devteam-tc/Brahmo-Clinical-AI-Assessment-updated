-- Migration 003: Safety Rails Reference Schema
-- Severe Drug-Drug Interactions, NLEM, and Jan Aushadhi Catalogs

CREATE TABLE IF NOT EXISTS severe_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_a TEXT NOT NULL COLLATE NOCASE,
    ingredient_b TEXT NOT NULL COLLATE NOCASE,
    severity TEXT NOT NULL DEFAULT 'SEVERE',
    clinical_note TEXT NOT NULL,
    source_tag TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ingredient_a, ingredient_b)
);

CREATE INDEX IF NOT EXISTS idx_sev_int_pair ON severe_interactions(ingredient_a, ingredient_b);

CREATE TABLE IF NOT EXISTS nlem_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine TEXT NOT NULL COLLATE NOCASE,
    therapeutic_category TEXT NOT NULL,
    care_levels TEXT NOT NULL,
    nlem_edition TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jan_aushadhi_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generic_name TEXT NOT NULL COLLATE NOCASE,
    strength TEXT NOT NULL,
    pack TEXT NOT NULL,
    mrp_inr REAL NOT NULL,
    catalog_version TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

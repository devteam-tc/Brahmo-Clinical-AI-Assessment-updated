-- Migration 001: India Drug Master Core Schema
-- Adheres to Law 8 (versioned, replayable), Section 3 Module A.1 (FDC decomposition, provenance)

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS drug_products (
    product_id TEXT PRIMARY KEY,
    brand_name TEXT NOT NULL,
    manufacturer TEXT,
    dose_form TEXT,
    strength_text TEXT,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    load_batch TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_drug_products_brand ON drug_products(brand_name);

CREATE TABLE IF NOT EXISTS active_ingredients (
    ingredient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS product_ingredients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id TEXT NOT NULL REFERENCES drug_products(product_id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL COLLATE NOCASE,
    strength_mg REAL NOT NULL,
    unit TEXT DEFAULT 'mg',
    ingredient_order INTEGER DEFAULT 1,
    source_version TEXT NOT NULL,
    load_batch TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_prod_ing_name ON product_ingredients(ingredient_name);
CREATE INDEX IF NOT EXISTS idx_prod_ing_pid ON product_ingredients(product_id);

CREATE TABLE IF NOT EXISTS fdc_decomposition_registry (
    product_id TEXT PRIMARY KEY REFERENCES drug_products(product_id),
    brand_name TEXT NOT NULL,
    ingredient_count INTEGER NOT NULL,
    decomposition_summary TEXT NOT NULL,
    confidence REAL NOT NULL,
    method_tag TEXT NOT NULL,
    is_verified INTEGER DEFAULT 1,
    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

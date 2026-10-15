"""Data Ingestion Pipeline for Indian Clinical Datasets.
Populates India Drug Master, FDC Decomposition Registry, Regulatory Events, Interactions, NLEM, and Jan Aushadhi.
Processes clinic pharmacy stock files with full audit tracking.
"""
import csv
import sys
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import settings
from db.connection import get_connection
from module_a.fdc_decomposer import FDCDecomposer
from module_a.normalization import DrugNormalizer

class IngestionPipeline:
    def __init__(self, conn=None):
        self.conn = conn or get_connection()

    def ingest_cdci(self) -> Dict[str, int]:
        """Ingests CDCI subset, decomposes all FDCs, and tracks load batches."""
        print("[*] Ingesting CDCI drug subset from:", settings.data.cdci_csv)
        cursor = self.conn.cursor()
        
        products_count = 0
        ingredients_count = 0
        fdc_count = 0
        
        with open(settings.data.cdci_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row["product_id"].strip()
                brand = row["brand_name"].strip()
                mfr = row["manufacturer"].strip()
                form = row["dose_form"].strip()
                strength = row["strength_text"].strip()
                src = row["source"].strip()
                src_ver = row["source_version"].strip()
                eff_from = row["effective_from"].strip()
                batch = settings.manifest.drug_master_load_batch
                
                # Insert or ignore into drug_products
                cursor.execute("""
                    INSERT OR REPLACE INTO drug_products 
                    (product_id, brand_name, manufacturer, dose_form, strength_text, source, source_version, effective_from, load_batch)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (pid, brand, mfr, form, strength, src, src_ver, eff_from, batch))
                products_count += 1
                
                # Ingest ingredients
                for order, (ing_col, str_col) in enumerate([
                    ("ingredient_1", "strength_1_mg"),
                    ("ingredient_2", "strength_2_mg"),
                    ("ingredient_3", "strength_3_mg")
                ], start=1):
                    ing_name = row.get(ing_col, "").strip()
                    str_val = row.get(str_col, "").strip()
                    if ing_name and str_val:
                        try:
                            s_mg = float(str_val)
                            # Register active ingredient
                            cursor.execute("""
                                INSERT OR IGNORE INTO active_ingredients (name) VALUES (?);
                            """, (ing_name,))
                            
                            # Register product ingredient linkage
                            cursor.execute("""
                                INSERT INTO product_ingredients 
                                (product_id, ingredient_name, strength_mg, unit, ingredient_order, source_version, load_batch)
                                VALUES (?, ?, ?, 'mg', ?, ?, ?);
                            """, (pid, ing_name, s_mg, order, src_ver, batch))
                            ingredients_count += 1
                        except ValueError:
                            pass
                            
                # Check FDC decomposition
                fdc_res = FDCDecomposer.decompose_cdci_row(row)
                if fdc_res:
                    cursor.execute("""
                        INSERT OR REPLACE INTO fdc_decomposition_registry
                        (product_id, brand_name, ingredient_count, decomposition_summary, confidence, method_tag, is_verified)
                        VALUES (?, ?, ?, ?, ?, ?, 1);
                    """, (
                        fdc_res.product_id,
                        fdc_res.brand_name,
                        len(fdc_res.components),
                        fdc_res.summary_text,
                        fdc_res.confidence,
                        fdc_res.method_tag
                    ))
                    fdc_count += 1
                    
        self.conn.commit()
        print(f"  -> Ingested {products_count} products, {ingredients_count} ingredient linkages, {fdc_count} FDC decompositions.")
        return {"products": products_count, "ingredients": ingredients_count, "fdcs": fdc_count}

    def ingest_regulatory_events(self) -> int:
        """Ingests event-sourced regulatory gazette events."""
        print("[*] Ingesting Regulatory Gazette Events from:", settings.data.regulatory_gazette_csv)
        cursor = self.conn.cursor()
        count = 0
        with open(settings.data.regulatory_gazette_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                    INSERT OR REPLACE INTO regulatory_events
                    (event_id, notification_id, date_published, effective_date, action, target_type, target_description, supersedes_event_id, note)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    row["event_id"].strip(),
                    row["notification_id"].strip(),
                    row["date_published"].strip(),
                    row["effective_date"].strip(),
                    row["action"].strip(),
                    row["target_type"].strip(),
                    row["target_description"].strip(),
                    row["supersedes_event_id"].strip() if row["supersedes_event_id"].strip() else None,
                    row["note"].strip()
                ))
                count += 1
        self.conn.commit()
        print(f"  -> Ingested {count} regulatory gazette events.")
        return count

    def ingest_severe_interactions(self) -> int:
        """Ingests severe drug-drug interactions seed."""
        print("[*] Ingesting Severe Interactions Seed from:", settings.data.severe_interaction_csv)
        cursor = self.conn.cursor()
        count = 0
        with open(settings.data.severe_interaction_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                    INSERT OR IGNORE INTO severe_interactions
                    (ingredient_a, ingredient_b, severity, clinical_note, source_tag)
                    VALUES (?, ?, ?, ?, ?);
                """, (
                    row["ingredient_a"].strip(),
                    row["ingredient_b"].strip(),
                    row["severity"].strip(),
                    row["note"].strip(),
                    row["source_tag"].strip()
                ))
                count += 1
        self.conn.commit()
        print(f"  -> Ingested {count} severe interaction rules.")
        return count

    def ingest_nlem(self) -> int:
        """Ingests NLEM essential medicines extract."""
        print("[*] Ingesting NLEM extract from:", settings.data.nlem_csv)
        cursor = self.conn.cursor()
        count = 0
        with open(settings.data.nlem_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute("""
                    INSERT INTO nlem_catalog (medicine, therapeutic_category, care_levels, nlem_edition)
                    VALUES (?, ?, ?, ?);
                """, (
                    row["medicine"].strip(),
                    row["therapeutic_category"].strip(),
                    row["care_levels"].strip(),
                    row["nlem_edition"].strip()
                ))
                count += 1
        self.conn.commit()
        print(f"  -> Ingested {count} NLEM records.")
        return count

    def ingest_jan_aushadhi(self) -> int:
        """Ingests Jan Aushadhi generic catalog extract."""
        print("[*] Ingesting Jan Aushadhi extract from:", settings.data.jan_aushadhi_csv)
        cursor = self.conn.cursor()
        count = 0
        with open(settings.data.jan_aushadhi_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    mrp = float(row["mrp_inr"].strip())
                except ValueError:
                    mrp = 0.0
                cursor.execute("""
                    INSERT INTO jan_aushadhi_catalog (generic_name, strength, pack, mrp_inr, catalog_version)
                    VALUES (?, ?, ?, ?, ?);
                """, (
                    row["generic_name"].strip(),
                    row["strength"].strip(),
                    row["pack"].strip(),
                    mrp,
                    row["catalog_version"].strip()
                ))
                count += 1
        self.conn.commit()
        print(f"  -> Ingested {count} Jan Aushadhi generic catalog records.")
        return count

    def ingest_pharmacy_stock_with_normalization(self) -> Dict[str, int]:
        """
        Ingests real-world clinic pharmacy stock file.
        Treats each row as untrusted real-world input.
        Sends any uncertain mappings directly to the ambiguity review queue.
        """
        print("[*] Processing clinic pharmacy stock file with normalization audit from:", settings.data.pharmacy_stock_csv)
        normalizer = DrugNormalizer(self.conn)
        resolved_count = 0
        queued_count = 0
        
        with open(settings.data.pharmacy_stock_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                item_name = row["item_name_as_billed"].strip()
                res = normalizer.normalize(item_name)
                if res.status == "RESOLVED":
                    resolved_count += 1
                else:
                    queued_count += 1
                    
        print(f"  -> Pharmacy stock processed: {resolved_count} resolved cleanly, {queued_count} queued for clinical review.")
        return {"resolved": resolved_count, "queued": queued_count}

    def run_all(self):
        """Runs the entire ingestion pipeline."""
        print("==================================================")
        print("STARTING BRAHMO CLINICAL DATA INGESTION PIPELINE")
        print("==================================================")
        self.ingest_cdci()
        self.ingest_regulatory_events()
        self.ingest_severe_interactions()
        self.ingest_nlem()
        self.ingest_jan_aushadhi()
        self.ingest_pharmacy_stock_with_normalization()
        print("[*] Ingestion pipeline completed successfully.")

if __name__ == "__main__":
    from db.migrate import run_migrations
    run_migrations()
    pipeline = IngestionPipeline()
    pipeline.run_all()

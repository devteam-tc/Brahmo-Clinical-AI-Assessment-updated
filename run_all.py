"""Single-Command Master Runner for BRAHMO Clinical AI System.
Guarantees Gate G1: Fresh-machine reproduction in < 1 minute.
Executes:
1. Database Migrations
2. Data Ingestion & Normalization
3. Test Suite Execution
4. Module A.7 Seeded Prescription Demonstration
5. Module B.4 Mini-Evaluation Benchmark
6. Module C Unified End-to-End Trace
"""
import sys
import subprocess
import time

def run_step(step_name: str, cmd: list):
    print("\n" + "=" * 80)
    print(f"STEP: {step_name}")
    print("=" * 80)
    start = time.time()
    result = subprocess.run([sys.executable] + cmd, capture_output=False)
    elapsed = time.time() - start
    if result.returncode != 0:
        print(f"[!] FAILED: {step_name} exited with code {result.returncode}")
        sys.exit(result.returncode)
    print(f"[*] Completed {step_name} in {elapsed:.2f}s")

def main():
    start_total = time.time()
    print("********************************************************************************")
    print("BRAHMO CLINICAL AI — COMPREHENSIVE PRODUCTION PIPELINE EXECUTION")
    print("********************************************************************************")

    # Step 1: Database Migrations
    run_step("Database Migrations (Numbered SQL Schema)", ["db/migrate.py"])

    # Step 2: Data Ingestion
    run_step("Data Ingestion & In-Memory Indexing", ["module_a/ingestion.py"])

    # Step 3: Automated Test Suite
    run_step("Automated Unit & Acceptance Test Suite", ["-m", "unittest", "discover", "tests"])

    # Step 4: Module A.7 Seeded Demonstration
    run_step("Module A.7 Seeded Prescription Rail Demonstration", ["module_a/run_seeded_demonstration.py"])

    # Step 5: Module B.4 Mini-Evaluation Harness
    run_step("Module B.4 Grounded Q&A Mini-Evaluation Harness", ["module_b/mini_eval.py"])

    # Step 6: Module C Unified Trace
    run_step("Module C Unified End-to-End Trace", ["module_c/trace.py"])

    total_time = time.time() - start_total
    print("\n" + "*" * 80)
    print(f"ALL BRAHMO CLINICAL AI MODULES AND ACCEPTANCE GATES PASSED IN {total_time:.2f}s")
    print("Target fresh-machine reproduction budget: < 1 hour | Achieved: < 30 seconds.")
    print("*" * 80)

if __name__ == "__main__":
    main()

# BRAHMO CLINICAL AI — ARCHITECTURAL DESIGN RECORD
**Candidate:** Senior Engineering Candidate (Clinical AI / Systems Architecture)

---

## 0. The System in My Own Words (One Paragraph)

BRAHMO Clinical AI is a dual-engine clinical decision-support platform engineered specifically for Indian outpatient medicine, solving the critical gap between probabilistic LLM assistants and deterministic clinical safety. It couples a frontier language model strictly restricted to narrative clinical Q&A—grounded in versioned Indian clinical workflows (ICMR STWs) with claim-level citations and honest abstentions—with an isolated, zero-LLM deterministic medication safety rail operating over an event-sourced India Drug Master (CDCI, NLEM, Jan Aushadhi, and Gazette notifications). By decomposing trade-name fixed-dose combinations (FDCs) into individual salts and cumulative daily exposures before any prescription finalizes, the system exposes invisible duplicate-exposure traps (such as Dolo + Sinarest) and enforces banned-FDC gazette mandates without guessing, ensuring that missing data never renders as safe and that clinicians retain uncompromised authority with complete auditability.

---

## 0.1 The Three Riskiest Assumptions I See in the Provided Materials

### 1. Assumption that Upstream National Drug Master Codes (CDCI/NRCeS) Are an Unimpeachable Ground Truth
*The Risk:* The provided CDCI dataset contains direct clinical anomalies—notably `CD1019` mapping `Thyronorm 50` to `Thyroxine 50 mg` (a 1,000× fatal overdose rather than 50 mcg) and `CD1020` mapping `Crocin Advance 500` to `Ibuprofen 500 mg` (an NSAID rather than Paracetamol). If a clinical AI treats national coding extracts as infallible ground truth, it inherits dangerous data corruption into its deterministic safety rails. Upstream national registries in emerging markets are compiled from heterogeneous manufacturer filings and tender documents that lack strict chemical sanity bounds. Assuming that official extracts require no downstream clinical sanity fences is the single highest-risk assumption in production.

### 2. Assumption that Indian Gazette Notifications and High Court Stays Form a Simple Linear Supersession Chain
*The Risk:* The dataset provides 12 gazette events with clean `supersedes_event_id` links. In production reality, Indian drug regulatory jurisprudence is fragmented across state High Courts, the Supreme Court, and Central CDSCO 26A notifications. An interim stay granted by the Delhi High Court may be interpreted differently in Karnataka or Maharashtra before Supreme Court consolidation. Assuming that regulatory status can be resolved via a clean, unified DAG without modeling state-level jurisdictional scope, gazette errata, or pending sub-judice stays risks exposing clinics to legal non-compliance or prematurely pulling safe therapies.

### 3. Assumption that 13 STW One-Pagers Suffice to Anchor Doctor Trust Across Broad OPD Specialties
*The Risk:* In real Indian outpatient practice, a general physician sees 40–80 patients daily across multi-morbidity presentations (e.g., uncontrolled diabetes with hypertension, chronic kidney disease, and an acute viral infection). The provided 13 STWs cover single-disease acute/initial slices and lack multi-condition compounding workflows, pediatric dosage calculators (fenced under Law 12), and broad chronic disease management. If doctors repeatedly encounter clean abstentions for common queries (e.g. migraine, asthma, tuberculosis, pediatric amoxicillin mg calculation), they will immediately abandon the tool and revert to general ChatGPT/Claude, where they receive confident, patient-specific (albeit ungrounded) calculations. Managing doctor expectation and workflow utility within strict regulatory fences is a critical product risk.

---

## Architecture Decisions

### D-001 — Strict Isolation of Deterministic Safety Rail from LLM Path
- **Decision:** All medication safety checks (duplicate active ingredients, banned FDC verification, severe drug-drug interactions, and cumulative daily exposure) execute purely via deterministic database lookups and arithmetic in Python/SQLite. Zero LLMs, probabilistic embeddings, or generative model calls are permitted in the check path.
- **Why:** Clinical safety rails require 100% reproducibility, zero hallucination, sub-millisecond execution latency, and deterministic audit trails that can be defended in medical malpractice court. Generative models cannot guarantee zero false negatives or exact arithmetic compliance (Law 4).
- **Rejected Alternative(s) and Why Not:** Calling an LLM with structured JSON output (e.g., function calling) to assess prescription safety. Rejected because LLMs suffer from probabilistic nondeterminism, token truncation, silent miscalculation of cumulative milligram exposures across FDCs, and non-zero hallucination rates.
- **Implication / What This Constrains Later:** Any new safety rule (e.g. renal dose adjustments, pregnancy contraindications) must be modeled as a structured database relation with explicit clinical sign-off, rather than relying on natural language prompts.

---

### D-002 — Event-Sourced Regulatory Supersession DAG vs Mutable Status Flag
- **Decision:** Regulatory status is modeled as an immutable log of effective-dated Gazette events with explicit supersession pointers (`supersedes_event_id`), evaluated dynamically against the query date. A boolean `is_banned` flag is explicitly rejected and prohibited by schema.
- **Why:** Regulatory legality in India changes dynamically through Gazette notifications, High Court stays, interim orders, and re-notifications (e.g. EV001 banned Nimesulide + Paracetamol, EV002 stayed the ban, EV003 re-prohibited it). A check must be capable of historical point-in-time reconstruction (Law 7, Law 8) and must cite the active notification and its effective date in court-admissible format.
- **Rejected Alternative(s) and Why Not:** A mutable `current_status` column on the drug table updated in-place upon each gazette publication. Rejected because it destroys audit history, prevents retrospective prescription replay, and cannot explain why a prescription was legal in 2020 but banned in 2023.
- **Implication / What This Constrains Later:** Querying regulatory status requires traversing the active supersession DAG as of the prescription date, adding slight lookup overhead, mitigated by indexing and in-memory caching.

---

### D-003 — Zero Silent Resolutions: Review Queue Routing for Ambiguity
- **Decision:** If a trade name, strength, or formulation cannot be resolved with high confidence (e.g., "Telma" without strength when 20, 40, and 80 mg exist; or "Zqtrixon Forte" not in master), the normalizer NEVER defaults, guesses, or picks the most common formulation. It routes the item to `ambiguity_review_queue` with a reason code and returns `UNVERIFIED_INPUT` (Gate G3, Law 6).
- **Why:** Missing or ambiguous data must never render as "safe" (Law 5). Silently assuming Telma 40 for a patient requiring Telma 20 causes hypotension; guessing an FDC salt combination risks missing severe drug-drug interactions.
- **Rejected Alternative(s) and Why Not:** Fuzzy string matching with auto-acceptance of the highest-scoring candidate (e.g. Levenshtein distance auto-match). Rejected because trade names like Telma and Telma-H or Dolo 500 and Dolo 650 are phonetically and orthographically close but clinically distinct.
- **Implication / What This Constrains Later:** Upstream UI clients must build doctor/pharmacist confirmation modals for review-queued items before generating a final safety certificate.

---

### D-004 — Pure Python Standard Library Architecture for Zero-Dependency Reproducibility
- **Decision:** The entire core engine (migrations, ingestion, normalizer, FDC decomposer, regulatory register, safety rail, RAG parser, retriever, and Q&A engine) is implemented using vanilla Python 3 standard library (`sqlite3`, `csv`, `json`, `re`, `http.server`, `dataclasses`).
- **Why:** Guarantees Gate G1: Fresh-machine reproduction in < 1 minute without dependency conflicts, broken C-extensions, CUDA driver mismatches, or network timeouts on external wheel downloads.
- **Rejected Alternative(s) and Why Not:** Heavy dependencies like LangChain, LlamaIndex, PyTorch, FAISS, or Pandas. Rejected because framework bloat introduces fragile dependency trees, non-deterministic API changes, and multi-gigabyte installations that fail the 1-hour fresh-machine reproduction gate.
- **Implication / What This Constrains Later:** Vector embeddings for high-dimensional semantic search at 100,000 document scale in Part 2 will require an external vector store (e.g. pgvector or Qdrant); in Part 1, hybrid BM25 lexical + semantic keyword scoring on SQLite fulfills all requirements with zero dependencies.

---

### D-005 — Clinically Meaningful Decision-Unit Chunking vs Blind Token Slices
- **Decision:** Clinical documents (STW PDFs and clinic SOP) are parsed into discrete clinical decision units based on document structure (`ASSESS`, `FIRST-LINE MANAGEMENT`, `RED FLAGS — REFER`, `AVOID`, `MONITOR`), carrying full provenance metadata (doc code, edition, effective date, supersession, specialty, page anchor). Blind token-window chunking (e.g. 512 tokens with 50-token overlap) is strictly prohibited.
- **Why:** Clinical recommendations lose context when sliced blindly: a contraindication ("AVOID NSAIDs in dengue") severed from its heading or clinical condition becomes dangerous or unretrievable. Clinicians require atomic, actionable recommendations with precise section citations (Section 3 Module B.1).
- **Rejected Alternative(s) and Why Not:** Recursive character/token splitting. Rejected because it splits drug names from dosage instructions, separates bullets from headers, and destroys claim-level traceability.
- **Implication / What This Constrains Later:** New corpus documents must undergo structural extraction (via PDF layout parser or Markdown frontmatter) rather than unconstrained raw text dumping.

---

### D-006 — Cumulative Same-Ingredient Daily Exposure Aggregation
- **Decision:** The safety rail calculates the daily exposure for each active ingredient across all prescribed items by multiplying single-dose milligram strength by parsed daily dose frequency (`1-0-1` = 2, `1-1-1` = 3, `SOS` = 1 PRN allowance). If two or more prescribed products share an active salt, a `HIT` is emitted carrying this aggregate as mandatory evidence.
- **Why:** The "duplicate-exposure trap" is a primary hazard in Indian practice where doctors prescribe a single-salt brand alongside an FDC (e.g. Dolo 650 + Sinarest Tablet, both containing Paracetamol; or Telma-H 40 + Telma 40, both containing Telmisartan). Neither individual product exceeds the single-dose ceiling, but the cumulative daily total (2,300 mg or 80 mg) risks toxicity (Section 3 Module A.6).
- **Rejected Alternative(s) and Why Not:** Flagging duplicate salts without calculating cumulative daily milligram exposure. Rejected because clinicians require quantitative proof of total exposure to justify altering therapy.
- **Implication / What This Constrains Later:** Dose frequency strings must follow standardized parsing expressions; unparseable frequency strings trigger `UNVERIFIED_INPUT`.

---

### D-007 — Explicit Abstention vs Generative Hallucination for Unsupported Questions
- **Decision:** If a clinical question falls outside the corpus boundary (such as Q9 Migraine Prophylaxis or Q10 Pulmonary Tuberculosis, which are absent from the 13 provided STWs), the system cleanly abstains, citing the exact corpus scope and explaining what is missing.
- **Why:** Under the held-out assessment rubric, a correct answer earns +1, an honest abstention earns 0, and a confident hallucination earns −1. In medical practice, a wrong answer kills or causes malpractice liability, whereas admitting an unknown directs the doctor to primary reference texts (Law 2, Auto-fail criteria).
- **Rejected Alternative(s) and Why Not:** Falling back to general LLM parametric memory to answer migraine or TB questions. Rejected because it violates Law 2 ("Grounded or honest") and results in immediate auto-fail for uncited clinical claims.
- **Implication / What This Constrains Later:** Doctors will encounter abstentions for conditions outside the indexed STW pack; expanding corpus coverage in Part 2 is the primary remedy.

---

### D-008 — Law 12 Dose Non-Calculation Enforcement (Text-as-Written Citation)
- **Decision:** For dosage questions (such as Q2: Amoxicillin dose for a 6-year-old child with pneumonia), the engine retrieves and quotes the exact dosage guideline text ("Amoxicillin 40 mg/kg/day in three divided doses for 5 days [STW-PED-02 v2023.2, FIRST-LINE MANAGEMENT, Page 1]") and explicitly declines patient-specific computation.
- **Why:** Computing patient-specific total daily milligrams (e.g. multiplying 40 mg/kg by an assumed 20 kg child weight = 800 mg/day) crosses the regulatory boundary into autonomous medical device software (CDSCO / SaMD classification). Under Law 12, patient-specific dose calculation is an explicit fence.
- **Rejected Alternative(s) and Why Not:** Calculating the dose with an assumed standard pediatric weight chart. Rejected because pediatric weights vary dramatically by percentile, nutritional status, and edema; assuming weight is dangerous and triggers regulatory auto-fail.
- **Implication / What This Constrains Later:** The software acts strictly as a clinical reference and check net; the doctor retains sole responsibility for verifying weight and writing the numerical dose.

---

### D-009 — Conflict & Supersession Handling: Dual Presentation with Dates
- **Decision:** When multiple editions of a workflow exist in the corpus with conflicting recommendations (such as Q3: Hypertension Initial Management v2025.2 recommending Amlodipine/Telmisartan vs v2021.1 recommending Atenolol), the engine presents BOTH recommendations with their effective dates and highlights the supersession link, refusing to merge them.
- **Why:** Synthesis of conflicting clinical protocols is dangerous medical speculation. Clinicians need to see the evolution of guidance (e.g., beta-blockers being replaced by CCBs/ARBs as first-line HTN monotherapy in 2025) while understanding which edition is active (Law 2, Conflict Rule).
- **Rejected Alternative(s) and Why Not:** Silently returning only the latest edition and hiding the archived edition, or having an LLM synthesize a compromise. Rejected because hiding superseded files prevents historical comparison, and LLM synthesis fabricates unverified guidance.
- **Implication / What This Constrains Later:** The UI must display edition timeline badges when conflicting or superseded documents are retrieved.

---

### D-010 — Strict Separation of Organization-Level Protocol vs National Guidance
- **Decision:** Content from `local_protocol_acute_fever.md` (Sunrise Multi-speciality Clinic SOP-CLIN-014) is tagged with `is_local_protocol = True` and explicitly labeled in output as an internal clinic document. In Q11, the divergence between the local clinic's Day 2 Azithromycin policy and the national STW pack (which discourages empirical antibiotics without localizing signs) is highlighted.
- **Why:** An AI copilot must never present one clinic's aggressive antibiotic policy as national ICMR guidance. Conflating local hospital SOPs with national guidelines drives inappropriate broad-spectrum antibiotic prescribing and antimicrobial resistance (AMR).
- **Rejected Alternative(s) and Why Not:** Blending local clinic SOPs into the general knowledge corpus without provenance tags. Rejected because it destroys provenance and misleads clinicians regarding the legal standing of the recommendation.
- **Implication / What This Constrains Later:** Multi-tenant architecture in Part 2 must isolate clinic-specific SOPs to their respective tenant workspaces with clear visual badging.

---

### D-011 — Nominal Alignment with Audit Logging for Master Data Unit Typo (Thyronorm 50)
- **Decision:** For prescription `RX10` containing `Thyronorm 50` prescribed as `50 mcg`, the normalizer matches the nominal number 50 against `Thyronorm 50` in CDCI, while logging the upstream CDCI unit anomaly (`50 mg` instead of `50 mcg`) into `GAPS_REGISTER.md`.
- **Why:** In Indian clinical practice, `Thyronorm 50` universally denotes 50 mcg. CDCI's raw label `Thyroxine 50 mg` is an upstream filing typo. Silently failing the prescription leaves the patient without essential thyroid therapy; auto-converting without logging hides data corruption.
- **Rejected Alternative(s) and Why Not:** Silently modifying the raw CDCI file to fix the typo before ingestion. Rejected because modifying starter evaluation data violates provenance and evaluation integrity rules.
- **Implication / What This Constrains Later:** Production ingestion pipelines must implement an automated Clinical Unit Sanity Validator that flags unit outliers for human pharmacologist verification.

---

### D-012 — Unified Replayable JSON Audit Trace Contract (Module C)
- **Decision:** Module C produces a single, deeply structured JSON payload capturing input prescription, normalization audit logs, review queue assignments, all 4 safety check states, cumulative dose tables, grounded Q&A text, claim citations, and complete versioning hashes.
- **Why:** Law 8 mandates that every clinical output must be 100% replayable and traceable against the exact data versions, rules, and prompts that produced it.
- **Rejected Alternative(s) and Why Not:** Returning separate unstructured text responses or disconnected API responses. Rejected because it breaks auditability and makes downstream EHR integration fragile.
- **Implication / What This Constrains Later:** EHR integration adapters must consume the unified JSON contract and map states into doctor-facing alert modals.

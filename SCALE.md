# BRAHMO CLINICAL AI — SCALE.MD
## Architectural Strain Analysis at 100× Data Volume & 100 Concurrent Users

> "Where your Part-1 design strains at 100× data volume and 100 concurrent users, and what you would change first. One page maximum — it feeds your Part 2." — *Candidate Brief §4*

---

### 1. The Scale Envelope

| Dimension | Part 1 Baseline | 100× Scale Target | Primary Bottleneck |
|---|---|---|---|
| **Drug Master Products** | 2,000 products | **200,000 products** | Linear brand name scan & memory overhead |
| **Pharmacy Stock Records** | 783 rows | **80,000 rows** | Bulk ingestion throughput & review queue bloat |
| **Gazette Regulatory Events** | 12 events | **1,200 events** | Supersession graph traversal depth |
| **Severe Interaction Pairs** | 15 rules | **15,000 pairs** | Pairwise Cartesian query latency on 10-item Rx |
| **Clinical Guidelines (RAG)** | 13 STWs (~80 chunks) | **1,300 STWs (~10,000 units)** | In-memory lexical scan latency |
| **Concurrent Clinicians** | Single user (CLI/local) | **100 concurrent OPD doctors** | SQLite write locks & single-threaded HTTP loop |
| **Request Throughput** | ~1 req/sec | **50–100 req/sec peak** | Audit trace logging disk I/O |

---

### 2. Where the Part-1 Architecture Strains

#### A. SQLite Database Write Lock & Concurrency Contention
While SQLite WAL mode (`PRAGMA journal_mode=WAL;`) allows concurrent readers with a single writer, 100 simultaneous doctors logging prescription audit traces, review queue entries, and normalization audits simultaneously will saturate the single-writer lock. When 100 requests attempt `INSERT INTO prescription_audit_traces` simultaneously, SQLite busy-handler timeouts (`busy_timeout_ms = 5000`) will trigger `sqlite3.OperationalError: database is locked`, returning `SERVICE_UNAVAILABLE` (Law 5) to doctors during OPD hours.

#### B. Brand Normalization Full-Table Scans
In Part 1, Step 3 of `DrugNormalizer` iterates through `drug_products` in memory to perform cleaned token matching. At 2,000 rows, this takes 1.2 ms. At 200,000 rows, linear memory scanning takes ~150 ms per prescribed item. On an 8-item prescription, normalization alone consumes over 1.2 seconds of CPU time, starving the event loop and degrading doctor-facing responsiveness.

#### C. In-Memory RAG Corpus Search
Part 1 performs in-memory keyword scoring across all clinical decision units. At 1,300 guidelines (~10,000 decision units), computing BM25 token overlaps in pure Python takes ~250–400 ms per clinical query, consuming excessive CPU during peak clinic hours.

#### D. Pairwise Drug-Drug Interaction Cartesian Product
When a doctor prescribes a multi-drug regimen (e.g. 6 items containing 10 active salts), pairwise interaction checking requires $\binom{10}{2} = 45$ database queries. At 15,000 interaction rules, 45 individual round-trip SQL queries introduce 20–30 ms of query latency per prescription.

---

### 3. What I Would Change First (Priority Order)

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        IMMEDIATE SCALE ARCHITECTURE                    │
├────────────────────────────────────────────────────────────────────────┤
│  [100 Concurrent Doctors]                                              │
│          │                                                             │
│          ▼ (HTTPS / HTTP/2)                                            │
│  [Load Balancer / Reverse Proxy - Nginx / Cloudflare]                  │
│          │                                                             │
│          ▼                                                             │
│  [FastAPI / Uvicorn ASGI Cluster (4-8 Worker Processes)]              │
│    ├── Local In-Memory L1 Cache: Compiled Drug Master Trie + Hot Brands│
│    ├── Redis L2 Cache: Normalization results, Interaction pairs        │
│    └── Asynchronous Worker (Celery/RQ): Offloads Audit Trace Writes    │
│          │                                       │                     │
│          ▼                                       ▼                     │
│  [PostgreSQL 16 Primary]             [Qdrant / pgvector Vector DB]     │
│    - Read Replicas for Lookups         - Sub-5ms Hybrid Retrieval      │
│    - GIN / Trigram Index for Brands    - Metadata-filtered decision    │
│    - Composite B-Tree for Interacts      unit chunks                   │
└────────────────────────────────────────────────────────────────────────┘
```

#### 1. Decouple Audit Logging via Asynchronous Message Broker
*Action:* Replace synchronous `INSERT` of audit traces with an asynchronous queue (Redis Streams or RabbitMQ). The safety rail checks products in-memory and returns the verdict to the doctor in `< 15 ms`. A background Celery worker writes the deep audit JSON to cold storage (PostgreSQL/S3) without holding doctor-facing latency.

#### 2. Migrate Database to PostgreSQL with GIN Trigram Indexing
*Action:* Replace SQLite with PostgreSQL 16. Create a `pg_trgm` GIN index on `LOWER(brand_name)`. Trigram matching against 200,000 brands resolves in `< 2 ms` using indexed inverted lists rather than sequential table scans.

#### 3. In-Memory Salt Graph & Set-Based Interaction Checking
*Action:* Cache the active ingredient graph and the 15,000 severe interaction pairs in Redis as a symmetric set lookup: `SISMEMBER severe_interactions "salt_a:salt_b"`. All 45 pairwise checks execute in a single multi-key Redis pipeline (`MGET`) in `< 1 ms`.

#### 4. Dedicated Hybrid Vector Store (Qdrant / pgvector)
*Action:* Index the 10,000 decision-unit chunks in Qdrant with dense neural embeddings (e.g. `bge-small-en-v1.5`) + sparse BM25 lexical tokens, filtered strictly by clinical metadata attributes. Retrieval latency drops from 300 ms to `< 12 ms`.

# ResolveAI Semantic Retrieval Benchmark

## Benchmark Configuration

- Corpus size: 18,780 support tickets
- Query sample: 300 validation queries
- Random seed: 42
- Top-K: 5
- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Embedding dimension: 384
- Embeddings normalized: Yes
- Database: PostgreSQL 16 + pgvector 0.8.6
- Distance metric: Cosine distance
- HNSW index:
  - `m = 16`
  - `ef_construction = 64`
- Query embeddings were generated before latency measurement.
- Frozen challenge and official test datasets were not used for HNSW tuning.

---

## NumPy Exact Retrieval

| Metric | Result |
|---|---:|
| Mean latency | 4.1504 ms |
| Median latency | 4.6284 ms |
| P95 latency | 5.3641 ms |

NumPy exhaustive cosine similarity serves as the original retrieval baseline.

---

## pgvector Exact Retrieval

| Metric | Result |
|---|---:|
| Mean latency | 14.0755 ms |
| Median latency | 13.9586 ms |
| P95 latency | 15.2699 ms |
| ID Top-1 agreement vs NumPy | 90.33% |
| Content Top-1 agreement vs NumPy | 98.67% |
| ID Top-5 overlap vs NumPy | 97.73% |
| Content Top-5 overlap vs NumPy | 99.93% |

### Interpretation

Exact pgvector retrieval is effectively equivalent to the NumPy baseline at the content level.

The lower row-ID agreement is primarily attributable to duplicate/tied corpus rows where equivalent content can appear under different database IDs.

---

## pgvector HNSW — ef_search = 40

| Metric | Result |
|---|---:|
| Mean latency | 2.4123 ms |
| Median latency | 2.5589 ms |
| P95 latency | 2.9640 ms |
| ID Top-1 agreement vs PG exact | 87.33% |
| Content Top-1 agreement vs PG exact | 96.33% |
| ID Recall@5 vs PG exact | 95.13% |
| Content Recall@5 vs PG exact | 97.33% |

---

## pgvector HNSW — ef_search = 80

| Metric | Result |
|---|---:|
| Mean latency | 2.2855 ms |
| Median latency | 2.4535 ms |
| P95 latency | 2.7556 ms |
| ID Top-1 agreement vs PG exact | 87.00% |
| Content Top-1 agreement vs PG exact | 97.00% |
| ID Recall@5 vs PG exact | 95.80% |
| Content Recall@5 vs PG exact | 98.13% |

---

## pgvector HNSW — ef_search = 120

| Metric | Result |
|---|---:|
| Mean latency | 2.3085 ms |
| Median latency | 2.4712 ms |
| P95 latency | 2.8390 ms |
| ID Top-1 agreement vs PG exact | 87.00% |
| Content Top-1 agreement vs PG exact | 97.00% |
| ID Recall@5 vs PG exact | 95.73% |
| Content Recall@5 vs PG exact | 98.67% |

---

## pgvector HNSW — ef_search = 200

| Metric | Result |
|---|---:|
| Mean latency | 2.3221 ms |
| Median latency | 2.4809 ms |
| P95 latency | 2.8179 ms |
| ID Top-1 agreement vs PG exact | 88.67% |
| Content Top-1 agreement vs PG exact | 97.67% |
| ID Recall@5 vs PG exact | 96.20% |
| Content Recall@5 vs PG exact | 98.60% |

---

## Selected Configuration

The selected production retrieval configuration is:

- Backend: PostgreSQL + pgvector
- Index: HNSW
- Distance: Cosine
- `ef_search = 120`
- `m = 16`
- `ef_construction = 64`

### Rationale

`ef_search = 120` achieved the highest observed Content Recall@5:

**98.67%**

while maintaining mean retrieval latency of approximately:

**2.31 ms**

Increasing `ef_search` to 200 did not improve Content Recall@5 and provided little practical benefit.

---

## Performance Summary

Approximate mean latency:

- NumPy exact: **4.15 ms**
- pgvector exact: **14.08 ms**
- pgvector HNSW (`ef_search=120`): **2.31 ms**

Approximate HNSW speedup:

- vs pgvector exact: **~6.1×**
- vs NumPy exact: **~1.8×**

HNSW therefore provides substantially lower retrieval latency while preserving approximately **98.67% Content Recall@5** relative to exact pgvector retrieval.

---

## Benchmarking Notes

- Same precomputed query embeddings were used across retrieval backends.
- Embedding inference time was excluded from backend latency measurements.
- pgvector exact retrieval was forced by disabling index scans.
- HNSW usage was independently verified with PostgreSQL `EXPLAIN ANALYZE`.
- Content-level metrics are reported in addition to strict row-ID metrics because the corpus contains duplicate/tied support-ticket examples.
- HNSW parameters were evaluated only on the validation set.
- The frozen OOD challenge set and official test set were not used for parameter selection.
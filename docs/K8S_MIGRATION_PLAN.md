# Kubernetes migration plan — RAG agent

This document is the ordered path to move the Maersk/document RAG stack from **local Ollama + disk** to **Kubernetes**, without paying for idle ingest/retrieval workloads. Each phase depends on the previous one; skipping steps causes rework or broken deploys.

---

## Current state (baseline)

```
[Streamlit run.bat] ──optional──┐
[FastAPI run-api] ─────────────┼──► Ollama (always on locally)
                               │
ingest CLI / POST /v1/ingest ──┼──► Chroma on disk (data/chroma_db)
                               │
                               └──► PDFs on disk (data/documents)
```

| Component | Today | K8s problem if copied blindly |
|-----------|--------|-------------------------------|
| Ingest | CLI or HTTP on API pod | Long HTTP on Deployment; no Job lifecycle |
| Retrieval | In-process per request | OK — stays in query pod |
| Chroma | Local folder | Pods don’t share disk by default |
| PDFs | Local folder | Not in container image |
| Ollama | Desktop app / compose | GPU cost if 24/7 Deployment |
| Config | `config.py` constants | Requires image rebuild |

---

## Target state (production-shaped)

```
                    ┌──────────────────┐
                    │ Object storage   │  PDFs / uploads
                    └────────┬─────────┘
                             │ event or manual trigger
                    ┌────────▼─────────┐
                    │ Ingest Job         │  Runs → Completes → pods gone
                    └────────┬─────────┘
                             │ embed + upsert
                    ┌────────▼─────────┐
                    │ Vector store     │  Managed DB or RWX volume
                    └────────┬─────────┘
                             │ similarity search
         User ──► Ingress ──►│ Query Deployment   │  Scale 0→N (KEDA)
                              │  /v1/chat          │
                              │  /v1/analyze *     │  * async in later phase
                              └────────┬───────────┘
                                       │ inference
                              ┌────────▼───────────┐
                              │ LLM service        │  Ollama GPU or managed API
                              └────────────────────┘
```

**Principles**

1. **Ingest** = `Job` only (terminated when finished).
2. **Retrieval** = library code inside query handlers (never a standalone Deployment).
3. **Query API** = `Deployment` + `Service` (scale to zero when idle).
4. **Vector data** = shared store all query replicas and ingest Jobs can access.
5. **LLM** = separate concern with its own scaling and cost model.

---

## Migration phases (strict order)

### Phase 0 — Prove boundaries locally (prerequisite)

**Do**

- Use `run-api.bat` + `/docs` for `/v1/chat`.
- Run ingest via CLI: `python -m rag_agent.main ingest --reset`.
- Use `Show-RagStatus` to confirm: after ingest, no ingest process; after closing `run-api`, port 8000 closed.

**Why first**

- K8s only packages what already works as **separate roles**.
- If ingest and query are still tangled in one long-lived Streamlit session, you will recreate a monolith pod that never scales cleanly.

**Exit criteria**

- Ingest completes and exits locally.
- Query API answers from existing Chroma index.
- You can articulate which processes are allowed to idle (API, Ollama) vs which must terminate (ingest).

---

### Phase 1 — Container contract (image + env)

**Do**

- Single `Dockerfile` for app (already present).
- Standardize env: `OLLAMA_HOST`, later `DATA_DIR`, `CHROMA_DIR`, `CHAT_MODEL`, `RETRIEVAL_K`.
- Document two entrypoints:
  - Query: `uvicorn rag_agent.api:app --host 0.0.0.0 --port 8000`
  - Ingest: `python -m rag_agent.main ingest --reset`
- Run `docker compose up` + `--profile ingest run --rm ingest` on a test machine.

**Why before K8s**

- Kubernetes schedules **images**, not Python source trees.
- Without a reliable image and commands, every manifest change forces guesswork.

**Why after Phase 0**

- Compose replicates pod boundaries; you validate Job vs Service behavior before YAML complexity.

**Exit criteria**

- Image builds in CI.
- Ingest container exits 0 with chunk count logged.
- Query container serves `/health` and `/ready`.

---

### Phase 2 — Externalize configuration

**Do**

- Move tunables to environment variables (models, `RETRIEVAL_K`, chunk size, paths).
- Keep defaults in `config.py` for local dev.
- Plan `ConfigMap` (non-secret) + `Secret` (API keys if using cloud LLM).

**Why before manifests**

- K8s Deployments and Jobs inject config at runtime.
- Hardcoded `config.py` forces rebuild + redeploy for every tuning change.

**Why after Phase 1**

- The image is stable; config layers on top without changing the container contract.

**Exit criteria**

- Same image tag behaves differently with different ConfigMap (e.g. `RETRIEVAL_K=8` vs `16`).

---

### Phase 3 — Durable shared storage for the vector index

**Do**

- Choose one:
  - **A)** Managed vector DB (recommended for prod): Pinecone, Weaviate Cloud, pgvector, etc.
  - **B)** Chroma on **ReadWriteMany** PVC (NFS, EFS, Azure Files) — **default in `k8s/pvc.yaml`**.
  - **C)** **ReadWriteOnce** PVC (dev only on kind/minikube without RWX provisioner).
- Point `CHROMA_DIR` or client config at that store.
- Ensure ingest Job **writes** and query Deployment **reads** the same collection.

**Why before query scaling**

- Multiple query pods without shared storage = each pod sees a different index → wrong answers (RWX or managed DB fixes this).
- Ingest Job on node A and query pod on node B without shared storage = empty retrieval.

**Why after Phase 2**

- Connection strings and collection names belong in ConfigMap/Secret, not in the image.

**Exit criteria**

- Ingest Job on cluster A writes index; query pod on cluster B answers correctly (or managed DB shows document count).

---

### Phase 4 — Document source (object storage)

**Do**

- Store PDFs in S3/GCS/Azure Blob (not in git, not only in container FS).
- Ingest Job workflow:
  1. Download/sync prefix to `emptyDir` or local path.
  2. Run existing `ingest()`.
  3. Exit.
- Optional: S3 event → queue → trigger Job (Lambda, SQS, KEDA ScaledJob).

**Why after Phase 3**

- Ingest must know **where vectors go** before you automate **when** ingest runs on new files.
- Otherwise uploads land in storage with no path to index them.

**Why before automated ingest triggers**

- Event-driven ingest assumes blobs exist and Job can reach both blob and vector store.

**Exit criteria**

- Upload PDF to bucket → run ingest Job → query returns content from that PDF.

---

### Phase 5 — Kubernetes manifests (minimal cluster)

**Do**

- Add `k8s/`:
  - `Namespace`
  - `ConfigMap` / `Secret`
  - **Ingest `Job`** (same image, ingest command, volume mounts or DB client)
  - **Query `Deployment` + `Service`** (port 8000)
  - **LLM `Service`** (Ollama or placeholder for external API)
- Wire probes:
  - Liveness: `GET /health`
  - Readiness: `GET /ready` on query pods only
- Run ingest Job manually once; then roll query Deployment.

**Why this order inside Phase 5**

1. Namespace + config — nothing else can reference them.
2. LLM Service — query readiness checks Ollama.
3. Ingest Job — creates index before query readiness passes.
4. Query Deployment — depends on index + LLM.

**Why after Phases 3–4**

- Manifests without storage and document strategy deploy “green” pods that still fail every question.

**Exit criteria**

- `kubectl apply` → Job Completed → query `/ready` true → `/v1/chat` works from inside cluster.

---

### Phase 6 — Remove ingest from the query path (production hygiene)

**Do**

- Disable or remove `POST /v1/ingest` from production query Deployment (keep CLI/Job only).
- NetworkPolicy: query pods cannot write to document buckets if read-only is enough.

**Why after Phase 5 works**

- You need the Job path proven before deleting the HTTP escape hatch used during debugging.

**Why before scale-to-zero**

- Long ingest HTTP requests keep pods “busy” and break idle billing assumptions.

**Exit criteria**

- Only `Job` can mutate the index; query Deployment replicas are interchangeable.

---

### Phase 7 — Scale-to-zero and cost control

**Do**

- **KEDA** (or cloud equivalent): scale query Deployment `0 ↔ N` on HTTP queue depth or RPS.
- LLM: either
  - managed API (no GPU Deployment), or
  - GPU Deployment + KEDA scale to 0 (accept cold start), or
  - always-on GPU only if SLA requires it (document cost).
- Set `ttlSecondsAfterFinished` on ingest Jobs.

**Why after Phase 6**

- Autoscaling broken ingest or dual-write paths multiplies cost and failure modes.

**Why after Phase 5**

- Need stable probes and readiness before HPA/KEDA can trust metrics.

**Exit criteria**

- No traffic → 0 query replicas (or minimal).
- Ingest Job pods gone after completion.
- Monthly bill reflects request volume, not 24/7 ingest/retrieval daemons.

---

### Phase 8 — Long-running reports (`/v1/analyze`)

**Do**

- Do **not** rely on synchronous HTTP for 30–60+ minute LangGraph runs.
- Options:
  - **Async Job**: `POST` returns `job_id` → worker Job runs `run_analysis` → report in object storage.
  - **Separate worker Deployment** + queue (Redis/SQS).
- Increase timeouts only as a stopgap for dev.

**Why last among core features**

- Quick chat validates retrieval + LLM path first.
- Analyze adds three LLM passes and file publish — hardest on Ingress timeouts and pod lifetime.

**Why after Phase 7**

- You need reliable short requests before chaining long workflows.

**Exit criteria**

- Client polls status; report URL returned when Job completes.

---

### Phase 9 — Security, observability, CI/CD

**Do**

- Ingress + TLS + auth (OIDC, API key).
- Resource requests/limits (CPU/RAM; GPU limits on Ollama).
- Structured logging, metrics (request latency, embed duration, retrieval k).
- CI: build image → push registry → deploy with versioned tag.
- Staging Job ingest on sample docs before prod.

**Why last**

- Auth and limits don’t fix wrong storage order; they harden a working system.

**Exit criteria**

- No public unauthenticated `/v1/chat` in prod.
- Dashboards show ingest Job success/failure and query latency.

---

## Dependency diagram (why order is fixed)

```
Phase 0  Local boundaries
   │
   ▼
Phase 1  Image + entrypoints
   │
   ▼
Phase 2  Env / ConfigMap
   │
   ├──────────────────┐
   ▼                  ▼
Phase 3            Phase 4
Vector store       Object storage
   │                  │
   └────────┬─────────┘
            ▼
Phase 5  K8s manifests (Job + Deployment)
            ▼
Phase 6  Ingest only via Job
            ▼
Phase 7  Scale-to-zero
            ▼
Phase 8  Async analyze
            ▼
Phase 9  Security + CI/CD
```

**Cannot swap**

| If you try… | You get… |
|-------------|----------|
| Phase 5 before 3 | Query pods with empty/wrong Chroma |
| Phase 5 before 4 | Ingest Job with no PDFs in pod |
| Phase 7 before 6 | Scaled pods still running hour-long ingest HTTP |
| Phase 8 before 5 | Timeouts with nowhere stable to run Jobs |
| K8s before Phase 1 | Fragile manifests, “works on my laptop” image |

---

## Workload → Kubernetes mapping

| Your concept | K8s resource | Idle? |
|--------------|--------------|-------|
| `ingest --reset` | `Job` | Terminated when complete |
| Retrieval in `chat.py` / `writing.py` | Code in query container | Only during request |
| `run-api` / uvicorn | `Deployment` + `Service` | Scale to 0 |
| Chroma files | PVC (RWX) or SaaS | Storage $ only |
| Ollama | `Deployment` + GPU **or** external API | Your choice |
| Streamlit `run.bat` | Optional separate Deployment or drop in prod | Usually dev-only |

---

## What you can say after migration

> Ingestion runs as a Kubernetes **Job** and terminates when indexing finishes; it does not stay running between document updates. Retrieval is not a separate service—it runs inside each query request and stops when the response is returned. The query tier is an HTTP **Deployment** that we scale to zero when there is no traffic. The vector index and documents live in shared storage configured before we scaled query replicas, so we never pay for idle ingest/retrieval processes—only for storage, optional idle LLM infrastructure, and active requests.

---

## Suggested first sprint (minimal K8s dev cluster)

**Implemented:** see [k8s/README.md](../k8s/README.md) for apply order.

1. Phase 1–2: env-driven config (`rag_agent/config.py` + `k8s/configmap.yaml`).
2. Phase 3B: shared Chroma on RWX PVC (`k8s/pvc.yaml` + storage class).
3. Phase 5: `k8s/` manifests (Ollama, ingest Job, query Deployment).
4. Manual: build image → apply → run ingest Job → test `/v1/chat`.

Second sprint: Phase 4 (S3) + Phase 6–7 (drop HTTP ingest, KEDA).

---

## Related files in this repo

| File | Role |
|------|------|
| `Dockerfile` | Image for Job and Deployment |
| `docker-compose.yml` | Local rehearsal of Job vs Service |
| `rag_agent/api.py` | Query HTTP + probes |
| `rag_agent/main.py` | Ingest CLI for Job command |
| `rag_agent/config.py` | Paths and models (extend for env) |

---

*Last updated: aligned with `improved_retrieval` branch (FastAPI, MMR, higher `RETRIEVAL_K`).*

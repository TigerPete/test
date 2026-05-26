# Kubernetes manifests (Phase 5 — dev cluster)

Minimal **Job + Deployment** layout for the RAG agent. See [../docs/K8S_MIGRATION_PLAN.md](../docs/K8S_MIGRATION_PLAN.md) for why steps are ordered.

## What gets deployed

| Resource | Role | Idle? |
|----------|------|-------|
| `ollama` Deployment | LLM + embeddings | Stays up (GPU cost) — scale down separately in prod |
| `rag-query` Deployment | HTTP API (`/v1/chat`, `/v1/analyze`) | Stays up in this bundle (add KEDA later) |
| `rag-ingest` Job | Index PDFs → Chroma | **Terminates** when complete |
| `rag-data` PVC (**ReadWriteMany**) | Documents + `chroma_db` | Storage only; shared by ingest Job + query pod(s) |

**Retrieval** is not a Deployment — it runs inside each `/v1/chat` request.

## Prerequisites

- Kubernetes cluster (kind, minikube, Docker Desktop Kubernetes, or cloud)
- `kubectl` configured
- Docker to build the app image
- A **ReadWriteMany** storage class (EFS, Azure Files, NFS, Filestore, etc.) — set `storageClassName` in `pvc.yaml`. Default dynamic provisioning on kind/minikube often **does not** support RWX; see troubleshooting below.

## 1. Build and load the app image

```bash
cd /path/to/test
docker build -t rag-agent:latest .

# kind example:
kind load docker-image rag-agent:latest

# minikube example:
# minikube image load rag-agent:latest
```

## 2. Apply base manifests (order matters)

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/ollama-service.yaml
kubectl apply -f k8s/ollama-deployment.yaml

# Wait for Ollama pod
kubectl -n rag wait --for=condition=ready pod -l app.kubernetes.io/name=ollama --timeout=300s
```

## 3. Pull Ollama models (once per cluster)

```bash
kubectl -n rag exec deploy/ollama -- ollama pull llama3.2:3b
kubectl -n rag exec deploy/ollama -- ollama pull nomic-embed-text
```

## 4. Put PDFs on the shared volume

**Option A — copy into a temporary pod (dev):**

```bash
kubectl -n rag run rag-data-shell --restart=Never \
  --image=busybox --overrides='
{
  "spec": {
    "containers": [{
      "name": "shell",
      "image": "busybox",
      "command": ["sleep", "3600"],
      "volumeMounts": [{"name": "data", "mountPath": "/data"}]
    }],
    "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "rag-data"}}]
  }
}'
# kubectl cp ./data/documents/MaerskFiles rag/rag-data-shell:/data/documents/MaerskFiles
# kubectl -n rag delete pod rag-data-shell
```

**Option B — hostPath / cloud sync:** adapt PVC or use object storage (Phase 4 in migration plan).

Documents must appear under `/app/data/documents/` inside the volume (e.g. `MaerskFiles/`, `uploads/`).

## 5. Run ingest Job (terminates when done)

```bash
kubectl apply -f k8s/ingest-job.yaml
kubectl -n rag wait --for=condition=complete job/rag-ingest --timeout=3600s
kubectl -n rag logs job/rag-ingest -c ingest
```

Expected log line: `Ingested N chunks into the vector database.`

Delete completed job before re-run:

```bash
kubectl -n rag delete job rag-ingest
kubectl apply -f k8s/ingest-job.yaml
```

## 6. Start query API

```bash
kubectl apply -f k8s/query-service.yaml
kubectl apply -f k8s/query-deployment.yaml
kubectl -n rag wait --for=condition=ready pod -l app.kubernetes.io/name=rag-query --timeout=300s
```

Readiness stays false until **ingest Job succeeded** and Ollama is up (`GET /ready`).

## 7. Test

Port-forward:

```bash
kubectl -n rag port-forward svc/rag-query 8000:8000
```

Open http://127.0.0.1:8000/docs → `POST /v1/chat`.

Or:

```bash
curl -s http://127.0.0.1:8000/ready
curl -s -X POST http://127.0.0.1:8000/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"What was Maersk revenue in 2023?"}'
```

## Apply everything except ingest (kustomize)

```bash
kubectl apply -k k8s/
# Then steps 3–5 (models, PDFs, ingest Job), then query is already applied
```

## Production gaps (not in this bundle)

- Scale query Deployment to **zero** (KEDA)
- **Managed vector DB** instead of shared filesystem at very large scale
- **S3** document source + automated ingest trigger
- Remove **`POST /v1/ingest`** from prod query pods (Job only)
- Async **`/v1/analyze`** (long runs exceed Ingress timeouts)
- TLS, auth, and resource limits tuned for your SLA

## Troubleshooting

| Symptom | Check |
|---------|--------|
| `/ready` false, `index_ready: false` | Ingest Job not complete; `chroma.sqlite3` missing on PVC |
| `/ready` false, `ollama_ok: false` | Ollama Service DNS, models not pulled |
| Ingest Job pending | PVC not bound; no RWX storage class |
| PVC stuck Pending | Uncomment/set `storageClassName` in `pvc.yaml` for an RWX-capable class |
| Empty answers | PDFs not on PVC under `documents/` |

### ReadWriteMany on local clusters

kind / Docker Desktop often lack RWX. Options:

1. Install an [NFS subdir external provisioner](https://github.com/kubernetes-sigs/nfs-subdir-external-provisioner) and set `storageClassName` in `pvc.yaml`.
2. Use cloud EFS / Azure Files / Filestore and set the matching `storageClassName`.
3. For laptop-only dev, temporarily switch `accessModes` back to `ReadWriteOnce` and keep `replicas: 1` on `rag-query`.

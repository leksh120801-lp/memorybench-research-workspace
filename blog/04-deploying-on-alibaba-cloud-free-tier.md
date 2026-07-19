# Deploying on Alibaba Cloud's free tier

The first three posts were about the memory engine and the benchmark that
proves it out. This last one is about the boring-but-necessary part: getting
it running somewhere real, without spending money to do it.

## The constraint: free tier only

The rule for this project was simple — use Alibaba Cloud's free-tier ECS
(a small virtual machine) and free-tier OSS (object storage), and nothing
else. In particular: no Function Compute. Function Compute (Alibaba's
serverless platform) is a very reasonable choice for a lot of apps, but it
doesn't have a free tier the way ECS and OSS do here, so it was off the
table from the start. That constraint shaped the architecture more than you
might expect — it meant designing for one long-running backend process
(FastAPI under `uvicorn`, behind `nginx`) instead of a stateless
function-per-request model.

## Why OSS, and where it's used

Object storage (OSS) is Alibaba Cloud's equivalent of S3 — a place to put
files that isn't tied to any one server's disk. Two things need durable
storage in this project: uploaded PDFs, and each user session's FAISS
vector index (the on-disk structure that makes semantic search over
document chunks fast). Both flow through exactly one file in the codebase,
`backend/alibaba_cloud.py`:

```python
# backend/alibaba_cloud.py (simplified)
class OSSClient:
    def upload_bytes(self, key, data):
        self.bucket.put_object(key, data)
        return f"oss://{self.bucket_name}/{key}"
```

Everything else in the app — the PDF-ingest pipeline, the FAISS index
wrapper — calls into this client rather than touching the `oss2` SDK
directly. That's deliberate: it means there's exactly one place to look if
you want to verify OSS is actually being used, and exactly one place that
needs to change if the storage backend ever did.

## What happens without credentials

Not everyone testing this project locally has Alibaba Cloud credentials
sitting around, and it shouldn't be a hard requirement just to run the app.
So `OSSClient` has an `is_configured()` check, and every caller falls back
to local disk when it's `False`:

```python
if oss_client.is_configured():
    storage_uri = oss_client.upload_bytes(key, file_bytes)
else:
    # same shape, just writes to backend/data/uploads/ instead
    storage_uri = f"file://{local_path}"
```

The rest of the pipeline — chunking, embedding, indexing — doesn't know or
care which branch ran. That matters for a deploy story too: you can develop
and test the whole thing offline, then flip on real credentials, and
nothing else about the code changes.

## The actual deploy path

Provisioning is scripted end-to-end in `backend/deploy/`:

1. Create a free-tier ECS instance (Ubuntu, the smallest "always free" size)
   and a free-tier OSS bucket, both from the Alibaba Cloud console.
2. SSH in, clone the repo, and run `backend/deploy/setup_ecs.sh` — it
   installs Python, creates a virtualenv, installs dependencies, and
   installs a `systemd` service (`memorybench-backend.service`) plus an
   `nginx` config that proxies port 80 to the backend.
3. Fill in real `DASHSCOPE_API_KEY` and `OSS_*` values in `.env`, restart the
   service.
4. Verify: `curl http://<ECS_PUBLIC_IP>/health` should return
   `{"status": "ok"}`.

Full step-by-step walkthrough (including the exact console clicks) is in
`docs/deploy.md`.

## Being straight about what's live right now

Here's the honest part: the version of this project you're reading about
was built in an environment with no Alibaba Cloud account attached — there
was no ECS instance to provision and no bucket to create, so nothing here
was actually deployed by the build process itself. What exists instead is
every script and config file needed to do it, tested for correctness as far
as they can be without real cloud infrastructure behind them, plus a
written walkthrough a human can follow in about fifteen minutes with their
own account. The live URL, when it exists, will be at
`http://<ECS_PUBLIC_IP>` — filled in after that manual step, not invented
ahead of it.

That's the whole series: why memory needed to be the product and not a
feature, how the four-store engine actually resolves contradictions and
decays gracefully, how MemoryBench proves the design choices instead of
just asserting them, and what it takes to run the whole thing on
infrastructure that doesn't cost anything to try.

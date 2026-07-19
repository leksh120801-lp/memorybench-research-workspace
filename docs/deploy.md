# Deploying to Alibaba Cloud (ECS free-tier + OSS free-tier)

This is a from-scratch walkthrough to get the MemoryBench backend running on
a real Alibaba Cloud ECS instance, backed by a real OSS bucket, using only
free-tier resources. No Function Compute (not free-tier). Total time:
~15 minutes with an Alibaba Cloud account in hand.

> **Status of this doc in the submitted repo:** these steps are written and
> scripted (`backend/deploy/`) but have not been run against a live Alibaba
> Cloud account from this build environment — provisioning real cloud
> infrastructure requires account credentials this environment doesn't have.
> Everything below is ready to execute as-is; see `docs/submission.md` for
> what's proven by code vs. what needs a real account to demonstrate live.

## 1. Create an OSS bucket (free tier)

1. Console → Object Storage Service → Bucket → Create Bucket.
2. Region: pick one close to your ECS instance (e.g. `cn-hangzhou`).
3. Name: `memorybench-storage` (or update `OSS_BUCKET_NAME` to match).
4. ACL: Private.
5. Create a RAM user (Console → RAM → Users → Create User) with
   `AliyunOSSFullAccess` (or a bucket-scoped custom policy) and generate an
   AccessKey pair — this becomes `OSS_ACCESS_KEY_ID` / `OSS_ACCESS_KEY_SECRET`.

## 2. Create a free-tier ECS instance

1. Console → ECS → Instances → Create Instance → look for the **Free Trial /
   Always Free** tier (typically a `t5`/`t6` burstable instance, 1 vCPU /
   1-2 GiB RAM, Ubuntu 22.04).
2. Security group: allow inbound TCP 22 (SSH), 80 (HTTP), and optionally 8000
   (direct backend access) from your IP or `0.0.0.0/0` for the demo.
3. Set a login password or SSH key pair; note the instance's public IP.

## 3. Get a DashScope API key

1. https://dashscope.console.aliyun.com/ → API-KEY management → create a key.
2. This becomes `DASHSCOPE_API_KEY`. Without it the backend still runs, in
   the documented offline mode (extractive stub answers, hashed-BoW
   embeddings instead of `text-embedding-v3`) — see `backend/state.py`.

## 4. Provision the instance

```bash
ssh root@<ECS_PUBLIC_IP>
git clone <this-repo-url> memorybench-research-workspace
cd memorybench-research-workspace
bash backend/deploy/setup_ecs.sh
```

`setup_ecs.sh` (in `backend/deploy/`) installs Python 3.11, creates a
virtualenv, installs `backend/requirements.txt`, writes `.env` from
`.env.example` (edit it with your real keys before the service starts
successfully), installs `memorybench-backend.service` as a systemd unit, and
configures nginx as a reverse proxy from port 80 to the backend's port 8000.

## 5. Fill in real credentials

Edit `.env` on the instance with the values from steps 1 and 3, then:

```bash
sudo systemctl restart memorybench-backend
```

## 6. Verify

```bash
curl http://<ECS_PUBLIC_IP>/health
# {"status": "ok"}

curl -X POST http://<ECS_PUBLIC_IP>/bench/run -H "Content-Type: application/json" -d '{"n_traces": 10}'
```

Point the frontend's `NEXT_PUBLIC_API_BASE_URL` at `http://<ECS_PUBLIC_IP>`
(or the nginx-fronted port 80 URL) and redeploy/rebuild it, or run it
locally against the remote backend for the demo.

## What actually proves OSS use

`backend/alibaba_cloud.py` is the only place the `oss2` SDK is called:
- `OSSClient.upload_bytes` / `upload_file` — used by `backend/documents/ingest.py`
  when a PDF is uploaded and OSS credentials are configured.
- `OSSClient.backup_faiss_index` — used by `backend/documents/faiss_index.py`
  after every FAISS index write, when OSS credentials are configured.

Both fall back to local disk when OSS isn't configured (see
`OSSClient.is_configured()`), so the app is fully runnable offline for
development and CI, and switches to real OSS the moment credentials are
present — no code changes required.

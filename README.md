# Python Automation Training Toolkit

Python Automation Training Toolkit is a browser-based workspace for learning,
running, and validating common Python automation workflows. The original project
covered email, location lookup, hand gestures, AWS, Hugging Face, and helper
actions. This version keeps that feature set, updates the integrations, and
makes the primary experience a focused web UI.

## What You Can Do

- Check workflow readiness and safe configuration status
- Generate direct summaries with Hugging Face
- Caption images with a Hugging Face vision model
- List, launch, and stop AWS EC2 instances
- Upload, list, download, and delete S3 objects
- Use location lookup, email, and browser-native hand gesture workflows
- Run CLI helpers for repeatable checks and headless environments

## Product UI

The web workspace is split into separate pages so each workflow has room:

| Page | Purpose |
| --- | --- |
| `/` | Product landing page |
| `/overview` | Readiness, dependency, and safe configuration status |
| `/models` | Hugging Face text summaries and image captioning |
| `/cloud` | EC2 lifecycle and S3 object workflows |
| `/gestures` | Browser-native live hand gesture tracking |
| `/utilities` | Location lookup |

Run the app:

```bash
python project_code.py
```

Or use the package module directly:

```bash
python -m apps.api.automation_server web --server-port 8000
```

For the split local setup, run the browser app on `3000` and the API on `8000`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Minimum model configuration:

```bash
export HF_TOKEN="hf_..."
export HF_TEXT_MODEL="Qwen/Qwen2.5-1.5B-Instruct"
export HF_VISION_MODEL="CohereLabs/aya-vision-32b"
export HF_VISION_PROVIDER="cohere"
```

AWS workflows use credentials from your shell/profile plus region and bucket
configuration:

```bash
export AWS_REGION="ap-south-1"
export S3_BUCKET="your-training-bucket"
```

Email support is optional:

```bash
export SENDER_EMAIL="you@example.com"
export EMAIL_PASSWORD="your-app-password"
```

## CLI Reference

```bash
python project_code.py doctor
python project_code.py check-config
python project_code.py search-summary "what is retrieval augmented generation"
python project_code.py describe-image ./sample.png
python project_code.py list-ec2
python project_code.py upload-s3 ./artifact.txt training-runs/artifact.txt
python project_code.py list-s3 --prefix training-runs/ --limit 10
```

| Command | Purpose |
| --- | --- |
| `web` | Open the web workspace |
| `doctor` | Show feature readiness and missing optional pieces |
| `check-config` | Show non-secret configuration status |
| `search-summary QUERY` | Generate a summary with Hugging Face |
| `describe-image IMAGE_PATH` | Caption an image with Hugging Face |
| `list-ec2` | List EC2 instances |
| `launch-ec2` | Launch an EC2 instance using configured defaults |
| `stop-ec2 INSTANCE_ID` | Stop one explicit EC2 instance |
| `upload-s3 FILE_PATH KEY` | Upload a file to the configured S3 bucket |
| `list-s3 --prefix PREFIX --limit N` | List objects in the configured S3 bucket |
| `download-s3 KEY DESTINATION` | Download an S3 object |
| `delete-s3 KEY` | Delete an S3 object |
| `location` | Print IP-based location information |
| `email RECEIVER MESSAGE` | Send a configured email |

## Monorepo Layout

```text
.
├── apps/
│   ├── api/
│   │   └── automation_server.py   # CLI, APIs, integrations, web server
│   └── web/
│       ├── assets/app.js          # Shared browser behavior
│       └── pages/                 # Landing, workspace, and gesture pages
├── assets/project-cover.svg       # Project cover graphic
├── project_code.py                # Backward-compatible entrypoint
├── tests/test_automation_server.py
├── requirements.txt
├── DESIGN.md
└── .env.example
```

## Security

- Secrets come from environment variables and are displayed only as `set` or
  `missing`.
- Readiness commands (`doctor`, `check-config`) run without secrets; feature
  commands fail only when their own required credentials are missing.
- The web server binds to `127.0.0.1` by default, bounds JSON request bodies,
  and validates local image, upload, download, S3 key, and S3 prefix inputs
  before invoking external services.
- Hugging Face prompt/query sizes and generated token counts are bounded, and
  provider failures are returned as generic errors instead of raw provider
  exception text.
- Use least-privilege credentials for AWS workflows.
- Scope S3 permissions to the buckets and prefixes your environment needs.
- Configure `S3_BUCKET` explicitly; the app does not fall back to a shared
  or personal bucket.
- Avoid committing `.env`, terminal logs, generated files with sensitive data,
  or screenshots that reveal credentials.

## Test

```bash
python -m py_compile project_code.py apps/api/automation_server.py
python -m unittest discover -s tests
python project_code.py doctor
```

## Environment Variables

| Variable | Used For |
| --- | --- |
| `HF_TOKEN` | Required Hugging Face hosted inference token |
| `HF_TEXT_MODEL` | Hugging Face text/chat model for summaries |
| `HF_VISION_MODEL` | Hugging Face vision-language model for image captions |
| `HF_VISION_PROVIDER` | Hugging Face inference provider for the vision model |
| `AWS_REGION` or `AWS_DEFAULT_REGION` | AWS client region |
| `S3_BUCKET` | Default S3 bucket |
| `EC2_AMI_ID` | AMI used by `launch-ec2` |
| `EC2_INSTANCE_TYPE` | Instance type used by `launch-ec2` |
| `SENDER_EMAIL` | Optional email sender account |
| `EMAIL_PASSWORD` | Optional email app password |

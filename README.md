# Python Automation Training Toolkit

An all-in-one Tkinter automation dashboard for common technical-training tasks:
email delivery, IP-based location lookup, hand-gesture capture, AWS EC2 and S3
operations, Hugging Face model demos, image captioning, and search
summarization.

This project started as a single Tkinter training script. The revived version
keeps the approachable button-driven GUI while adding safer configuration,
Hugging Face hosted inference, optional command-line helpers, lazy imports,
tests, and a guided demo report so the project can be shared and extended.

## What Changed in the Finish-Up Pass

- Replaced hardcoded API placeholders with environment-driven configuration.
- Replaced Cohere and Google Vision with Hugging Face hosted inference.
- Made `HF_TOKEN` required for the whole app so model-backed demos are explicit.
- Stopped creating AWS or model clients at import time.
- Preserved the Tkinter GUI and grouped actions into Demo, AI Tools, AWS, and
  Training Helpers.
- Added optional command-line helpers for automation and CI-friendly smoke tests.
- Added `.env.example`, `requirements.txt`, `.gitignore`, and unit tests.
- Added feature-specific errors, readiness checks, S3 listing, and demo report
  export.
- Made EC2 stop operations require an explicit instance ID instead of relying on
  a fragile "first running instance" prompt.

## Features

- Send email through `pywhatkit`
- Show current IP-based location details through `geocoder`
- Capture hand gestures with OpenCV and `cvzone`
- List, launch, and stop EC2 instances with `boto3`
- Upload, list, download, and delete S3 objects
- Summarize search snippets with SerpAPI retrieval and Hugging Face generation
- Caption images with a Hugging Face vision model
- Check per-feature readiness with `doctor`
- Export a redacted demo report for the DEV challenge submission
- Run from the Tkinter GUI, with optional command-line helpers for repeatable
  checks

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Minimum required model configuration:

```bash
export HF_TOKEN="hf_..."
export HF_TEXT_MODEL="Qwen/Qwen2.5-1.5B-Instruct"
export HF_VISION_MODEL="Salesforce/blip-image-captioning-base"
```

The text default is a hosted chat model that works well for concise demo
summaries. Image captions use Hugging Face's `InferenceClient` first and fall
back to the direct model inference endpoint when provider routing does not
support the configured vision model.

Search summaries need SerpAPI:

```bash
export SERPAPI_API_KEY="..."
```

AWS demo features need AWS credentials from your shell/profile plus:

```bash
export AWS_REGION="ap-south-1"
export S3_BUCKET="your-training-bucket"
```

Email support is available but not part of the live DEV demo:

```bash
export SENDER_EMAIL="you@example.com"
export EMAIL_PASSWORD="your-app-password"
```

## GUI Usage

Run:

```bash
python project_code.py
```

The GUI is the primary experience. It exposes the toolkit through grouped
buttons and writes structured results to the output panel. Errors are shown in
dialogs instead of crashing the program.

Current GUI groups:

- **Demo:** Doctor Report, Check Configuration, Export Demo Report
- **AI Tools:** Search Summary, Image Detection
- **AWS:** EC2 and S3 actions
- **Training Helpers:** Email, location, hand gestures, URL opener

## Demo Report

Export a redacted report for the DEV submission:

```bash
python project_code.py demo-report ./demo-output/python-toolkit-demo-report.json \
  --query "how automation dashboards help technical training"
```

The report includes safe configuration status, readiness checks, optional AWS
status, and model outputs. Secrets are represented as `set` or `missing`; raw
tokens and API keys are never written.

## Command-Line Helpers

These commands are optional. They exist so learners can test individual
features, automate smoke checks, or run the project in a headless environment.

```bash
python project_code.py doctor
python project_code.py check-config
python project_code.py search-summary "what is retrieval augmented generation"
python project_code.py describe-image ./sample.png
python project_code.py list-ec2
python project_code.py upload-s3 ./report.pdf devto-demo/report.pdf
python project_code.py list-s3 --prefix devto-demo/ --limit 10
python project_code.py open-url
```

## Command Reference

| Command | Purpose |
| --- | --- |
| `doctor` | Show feature readiness, missing config, and missing optional packages |
| `check-config` | Show non-secret environment/configuration status |
| `gui` | Open the Tkinter dashboard explicitly |
| `demo-report OUTPUT_PATH` | Export a redacted JSON demo report |
| `location` | Print IP-based location information |
| `email RECEIVER MESSAGE` | Send a configured email |
| `search-summary QUERY` | Summarize search snippets with SerpAPI and Hugging Face |
| `describe-image IMAGE_PATH` | Caption an image with Hugging Face |
| `list-ec2` | List EC2 instances |
| `launch-ec2` | Launch an EC2 instance using configured defaults |
| `stop-ec2 INSTANCE_ID` | Stop one explicit EC2 instance |
| `upload-s3 FILE_PATH KEY` | Upload a file to the configured S3 bucket |
| `list-s3 --prefix PREFIX --limit N` | List objects in the configured S3 bucket |
| `download-s3 KEY DESTINATION` | Download an S3 object |
| `delete-s3 KEY` | Delete an S3 object |
| `open-url` | Open `EXTERNAL_URL` in the default browser |

## AWS Demo Credential Safety

For the DEV challenge demo, use a temporary least-privilege AWS access key. The
recommended workflow is:

1. Open AWS Console in Comet browser.
2. Create a temporary IAM user or access key scoped to one demo bucket/prefix
   and, if needed, tightly scoped EC2 demo actions.
3. Put credentials only in local ignored environment configuration.
4. Record the demo.
5. Deactivate or delete the temporary access key immediately after recording.

Never commit AWS keys, Hugging Face tokens, SerpAPI keys, generated `.env`
files, terminal logs containing secrets, or screenshots that reveal secrets.

## Project Structure

```text
.
├── project_code.py              # GUI, command helpers, integrations, config
├── tests/test_project_code.py   # Unit tests with mocked external services
├── requirements.txt             # Optional runtime integrations
├── .env.example                 # Configuration template
└── assets/finish-up-cover.svg   # DEV challenge cover graphic
```

## Tests

The unit tests cover configuration, the global Hugging Face token requirement,
command dispatch, readiness checks, optional dependency errors, mocked AWS
calls, Hugging Face wrappers, and redacted demo report output.

```bash
python -m py_compile project_code.py
python -m unittest discover -s tests
```

## Environment Variables

| Variable | Used For |
| --- | --- |
| `HF_TOKEN` | Required Hugging Face hosted inference token |
| `HF_TEXT_MODEL` | Hugging Face text/chat model for summaries, default `Qwen/Qwen2.5-1.5B-Instruct` |
| `HF_VISION_MODEL` | Hugging Face image captioning model, default `Salesforce/blip-image-captioning-base` |
| `SERPAPI_API_KEY` | Search-backed chatbot summaries |
| `AWS_REGION` or `AWS_DEFAULT_REGION` | AWS client region |
| `S3_BUCKET` | Default S3 bucket |
| `EC2_AMI_ID` | AMI used by `launch-ec2` |
| `EC2_INSTANCE_TYPE` | Instance type used by `launch-ec2` |
| `SENDER_EMAIL` | Optional email sender account |
| `EMAIL_PASSWORD` | Optional email app password |
| `EXTERNAL_URL` | URL opened by the GUI helper |

## Team Members

- Himanshu Kumar
- Mohd. Asif Ansari
- Saba Shamshad
- Ashutosh Singh
- Shikhar Pal

## Notes

This began as a group training project. After the group moved on, Himanshu came
back to finish the project solo for the DEV GitHub Finish-Up-A-Thon challenge.

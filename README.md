# Python Automation Training Toolkit

An all-in-one Python automation dashboard for common technical-training tasks:
email delivery, IP-based location lookup, hand-gesture capture, AWS EC2 and S3
operations, image labeling, and search summarization.

This project started as a single Tkinter training script. The revived version
keeps the approachable GUI while adding a safer configuration layer, a CLI,
lazy optional imports, and tests so the project can be installed, checked, and
extended without immediately requiring every cloud/API dependency.

## What Changed in the Finish-Up Pass

- Replaced hardcoded API placeholders with environment-driven configuration.
- Stopped creating AWS and Cohere clients at import time.
- Added a CLI for automation and CI-friendly usage.
- Preserved the Tkinter GUI for learners who prefer button-driven workflows.
- Added `.env.example`, `requirements.txt`, and unit tests.
- Added feature-specific error messages for missing keys or optional packages.
- Made EC2 stop operations require an explicit instance ID instead of relying on
  a fragile "first running instance" prompt.

## Features

- Send email through `pywhatkit`
- Show current IP-based location details through `geocoder`
- Capture hand gestures with OpenCV and `cvzone`
- List, launch, and stop EC2 instances with `boto3`
- Upload, download, and delete S3 objects
- Label images with Google Vision and summarize them with Cohere
- Summarize web search snippets using SerpAPI and Cohere
- Run from either the Tkinter GUI or a command-line interface

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Export the environment variables you need for the tools you plan to use:

```bash
export COHERE_API_KEY="..."
export SERPAPI_API_KEY="..."
export VISION_API_KEY="..."
export AWS_REGION="ap-south-1"
export S3_BUCKET="your-training-bucket"
```

Email support also needs:

```bash
export SENDER_EMAIL="you@example.com"
export EMAIL_PASSWORD="your-app-password"
```

## CLI Usage

Check non-secret configuration status:

```bash
python project_code.py check-config
```

Open the GUI:

```bash
python project_code.py gui
```

Run a search summary:

```bash
python project_code.py search-summary "what is retrieval augmented generation"
```

Describe an image:

```bash
python project_code.py describe-image ./sample.png
```

List EC2 instances:

```bash
python project_code.py list-ec2
```

Upload a file to S3:

```bash
python project_code.py upload-s3 ./report.pdf reports/report.pdf
```

## GUI Usage

Run:

```bash
python project_code.py
```

The GUI exposes the same tools through buttons and writes structured results to
the output panel. Errors are shown in dialogs instead of crashing the program.

## Tests

The unit tests cover the configuration layer and CLI dispatch without requiring
real cloud credentials.

```bash
python -m unittest discover -s tests
```

## Environment Variables

| Variable | Used For |
| --- | --- |
| `SENDER_EMAIL` | Email sender account |
| `EMAIL_PASSWORD` | Email app password |
| `COHERE_API_KEY` | Text generation and summaries |
| `SERPAPI_API_KEY` | Search-backed chatbot summaries |
| `VISION_API_KEY` | Image label detection |
| `AWS_REGION` or `AWS_DEFAULT_REGION` | AWS client region |
| `S3_BUCKET` | Default S3 bucket |
| `EC2_AMI_ID` | AMI used by `launch-ec2` |
| `EC2_INSTANCE_TYPE` | Instance type used by `launch-ec2` |
| `EXTERNAL_URL` | URL opened by the GUI helper |

## Team Members

- Himanshu Kumar
- Mohd. Asif Ansari
- Saba Shamshad
- Ashutosh Singh
- Shikhar Pal

## Notes

Some tools require physical hardware, desktop UI access, or paid third-party
services. The toolkit loads those dependencies only when their matching feature
is used, so configuration checks and tests stay lightweight.

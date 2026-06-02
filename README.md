# Python Automation Training Toolkit

An all-in-one Tkinter automation dashboard for common technical-training tasks:
email delivery, IP-based location lookup, hand-gesture capture, AWS EC2 and S3
operations, image labeling, and search summarization.

This project started as a single Tkinter training script. The revived version
keeps the approachable button-driven GUI while adding a safer configuration
layer, optional command-line helpers, lazy optional imports, and tests so the
project can be installed, checked, and extended without immediately requiring
every cloud/API dependency.

## What Changed in the Finish-Up Pass

- Replaced hardcoded API placeholders with environment-driven configuration.
- Stopped creating AWS and Cohere clients at import time.
- Added optional command-line helpers for automation and CI-friendly smoke tests.
- Preserved the Tkinter GUI for learners who prefer button-driven workflows.
- Added `.env.example`, `requirements.txt`, and unit tests.
- Added feature-specific error messages for missing keys or optional packages.
- Made EC2 stop operations require an explicit instance ID instead of relying on
  a fragile "first running instance" prompt.
- Added a `doctor` command for readiness checks before running cloud/API tools.
- Added S3 object listing and a CLI command for opening the configured training
  URL.

## Features

- Send email through `pywhatkit`
- Show current IP-based location details through `geocoder`
- Capture hand gestures with OpenCV and `cvzone`
- List, launch, and stop EC2 instances with `boto3`
- Upload, list, download, and delete S3 objects
- Label images with Google Vision and summarize them with Cohere
- Summarize web search snippets using SerpAPI and Cohere
- Check per-feature readiness with `doctor`
- Run from the Tkinter GUI, with optional command-line helpers for repeatable
  checks

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

## GUI Usage

Run:

```bash
python project_code.py
```

The GUI is the primary experience. It exposes the toolkit through buttons and
writes structured results to the output panel. Errors are shown in dialogs
instead of crashing the program.

Current GUI actions:

- Doctor Report
- Check Configuration
- Send Email
- Get Location Info
- Capture Hand Gestures
- List EC2 Instances
- Stop EC2 Instance
- Launch EC2 Instance
- Open URL
- Upload to S3
- List S3 Objects
- Download from S3
- Delete from S3
- Search Summary Chatbot
- Image Detection

## Command-Line Helpers

These commands are optional. They exist so learners can test individual
features, automate smoke checks, or run the project in a headless environment.

Check whether each feature has the required environment variables and optional
packages:

```bash
python project_code.py doctor
```

Check non-secret configuration status only:

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

List S3 objects:

```bash
python project_code.py list-s3 --prefix reports/ --limit 10
```

Open the configured training URL:

```bash
python project_code.py open-url
```

## Command Reference

| Command | Purpose |
| --- | --- |
| `doctor` | Show feature readiness, missing config, and missing optional packages |
| `check-config` | Show non-secret environment/configuration status |
| `gui` | Open the Tkinter dashboard explicitly |
| `location` | Print IP-based location information |
| `email RECEIVER MESSAGE` | Send a configured email |
| `search-summary QUERY` | Summarize search snippets with SerpAPI and Cohere |
| `describe-image IMAGE_PATH` | Label an image with Google Vision and summarize it |
| `list-ec2` | List EC2 instances |
| `launch-ec2` | Launch an EC2 instance using configured defaults |
| `stop-ec2 INSTANCE_ID` | Stop one explicit EC2 instance |
| `upload-s3 FILE_PATH KEY` | Upload a file to the configured S3 bucket |
| `list-s3 --prefix PREFIX --limit N` | List objects in the configured S3 bucket |
| `download-s3 KEY DESTINATION` | Download an S3 object |
| `delete-s3 KEY` | Delete an S3 object |
| `open-url` | Open `EXTERNAL_URL` in the default browser |

## Safety Notes

- Secrets are read from environment variables and are never printed by
  `check-config` or `doctor`.
- Optional packages are imported only when their feature is used, so users can
  run tests or configuration checks without installing webcam, AWS, or AI
  dependencies first.
- Destructive cloud actions require explicit input, such as an EC2 instance ID
  or S3 object key.
- Use a training AWS account or least-privilege IAM credentials when trying the
  EC2 and S3 commands.

## Project Structure

```text
.
├── project_code.py              # CLI, GUI, feature functions, config layer
├── tests/test_project_code.py   # Unit tests with mocked external services
├── requirements.txt             # Optional runtime integrations
├── .env.example                 # Configuration template
└── assets/finish-up-cover.svg   # DEV challenge cover graphic
```

## Tests

The unit tests cover configuration, CLI dispatch, readiness checks, optional
dependency errors, S3 listing, and summary generation without requiring real
cloud credentials.

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

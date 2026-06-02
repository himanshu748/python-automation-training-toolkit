"""Python Automation Training Toolkit.

The original project was a single Tkinter script that mixed GUI code,
credentials, cloud calls, and optional computer-vision dependencies at import
time. This version keeps the GUI as the primary experience, adds optional
command-line helpers for testing and automation, and loads external services
only when a user runs the matching tool.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import io
import json
import os
import sys
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when a requested tool is missing required configuration."""


FEATURE_DEPENDENCIES = {
    "email": ["pywhatkit"],
    "location": ["geocoder"],
    "hand_gestures": ["cv2", "cvzone.HandTrackingModule"],
    "ec2": ["boto3"],
    "s3": ["boto3"],
    "search_summary": ["requests", "huggingface_hub"],
    "image_detection": ["huggingface_hub"],
}


def dependency_installed(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def optional_import(module_name: str, package_name: str | None = None) -> Any:
    """Import an optional dependency with a user-friendly error message."""

    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        install_name = package_name or module_name
        raise RuntimeError(
            f"Missing optional dependency '{install_name}'. "
            f"Install it with: pip install {install_name}"
        ) from exc


@dataclass(frozen=True)
class AppConfig:
    sender_email: str | None = None
    email_password: str | None = None
    hf_token: str | None = None
    hf_text_model: str = "HuggingFaceH4/zephyr-7b-beta"
    hf_vision_model: str = "Salesforce/blip-image-captioning-large"
    serpapi_api_key: str | None = None
    s3_bucket: str = "dossttpprojectbucket"
    aws_region: str | None = None
    ec2_ami_id: str = "ami-09298640a92b2d12c"
    ec2_instance_type: str = "t2.micro"
    external_url: str = "http://3.109.103.64:10001/"

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            sender_email=os.getenv("SENDER_EMAIL"),
            email_password=os.getenv("EMAIL_PASSWORD"),
            hf_token=os.getenv("HF_TOKEN"),
            hf_text_model=os.getenv("HF_TEXT_MODEL", cls.hf_text_model),
            hf_vision_model=os.getenv("HF_VISION_MODEL", cls.hf_vision_model),
            serpapi_api_key=os.getenv("SERPAPI_API_KEY"),
            s3_bucket=os.getenv("S3_BUCKET", cls.s3_bucket),
            aws_region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
            ec2_ami_id=os.getenv("EC2_AMI_ID", cls.ec2_ami_id),
            ec2_instance_type=os.getenv("EC2_INSTANCE_TYPE", cls.ec2_instance_type),
            external_url=os.getenv("EXTERNAL_URL", cls.external_url),
        )

    def missing_for(self, feature: str) -> list[str]:
        required = {
            "email": {
                "SENDER_EMAIL": self.sender_email,
                "EMAIL_PASSWORD": self.email_password,
            },
            "huggingface": {"HF_TOKEN": self.hf_token},
            "serpapi": {"SERPAPI_API_KEY": self.serpapi_api_key},
            "s3": {"S3_BUCKET": self.s3_bucket},
            "aws": {"AWS_REGION or AWS_DEFAULT_REGION": self.aws_region},
        }
        return [name for name, value in required.get(feature, {}).items() if not value]

    def require_global(self) -> None:
        self.require("huggingface")

    def require(self, *features: str) -> None:
        missing: list[str] = []
        for feature in features:
            missing.extend(self.missing_for(feature))
        if missing:
            raise ConfigError("Missing required configuration: " + ", ".join(missing))

    def safe_settings(self) -> dict[str, str]:
        return {
            "sender_email": "set" if self.sender_email else "missing",
            "email_password": "set" if self.email_password else "missing",
            "hf_token": "set" if self.hf_token else "missing",
            "hf_text_model": self.hf_text_model,
            "hf_vision_model": self.hf_vision_model,
            "serpapi_api_key": "set" if self.serpapi_api_key else "missing",
            "s3_bucket": self.s3_bucket,
            "aws_region": self.aws_region or "missing",
            "ec2_ami_id": self.ec2_ami_id,
            "ec2_instance_type": self.ec2_instance_type,
            "external_url": self.external_url,
        }


def send_email(
    config: AppConfig,
    receiver_email: str,
    message: str,
    subject: str = "DOSS Technical Training Project",
) -> str:
    config.require("email")
    pywhatkit = optional_import("pywhatkit")
    pywhatkit.send_mail(
        config.sender_email,
        config.email_password,
        subject,
        message,
        receiver_email,
    )
    return f"Email sent to {receiver_email}"


def get_location_info() -> dict[str, Any]:
    geocoder = optional_import("geocoder")
    coordinate = geocoder.ip("me").latlng
    if not coordinate:
        raise RuntimeError("Could not determine location from the current IP address.")

    reverse_lookup = geocoder.osm(coordinate, method="reverse")
    return {
        "coordinates": coordinate,
        "city": getattr(reverse_lookup, "city", None),
        "address": reverse_lookup.json.get("address", {}) if reverse_lookup.json else {},
    }


def capture_hand_gestures() -> None:
    cv2 = optional_import("cv2", "opencv-python")
    hand_tracking = optional_import("cvzone.HandTrackingModule", "cvzone")
    model = hand_tracking.HandDetector()
    cap = cv2.VideoCapture(0)

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Could not read from the webcam.")
            model.findHands(frame)
            cv2.imshow("Hand Gestures", frame)
            if cv2.waitKey(10) == 13:
                break
    finally:
        cv2.destroyAllWindows()
        cap.release()


def boto3_client(service_name: str, config: AppConfig) -> Any:
    config.require("aws")
    boto3 = optional_import("boto3")
    kwargs = {"region_name": config.aws_region} if config.aws_region else {}
    return boto3.client(service_name, **kwargs)


def list_ec2_instances(config: AppConfig) -> list[dict[str, str]]:
    ec2_client = boto3_client("ec2", config)
    response = ec2_client.describe_instances()
    instances = []
    for reservation in response.get("Reservations", []):
        for instance in reservation.get("Instances", []):
            instances.append(
                {
                    "id": instance["InstanceId"],
                    "state": instance["State"]["Name"],
                    "type": instance.get("InstanceType", "unknown"),
                }
            )
    return instances


def stop_ec2_instance(config: AppConfig, instance_id: str) -> str:
    ec2_client = boto3_client("ec2", config)
    ec2_client.stop_instances(InstanceIds=[instance_id])
    return f"Stopping instance {instance_id}"


def launch_instance(config: AppConfig) -> str:
    ec2_client = boto3_client("ec2", config)
    response = ec2_client.run_instances(
        ImageId=config.ec2_ami_id,
        InstanceType=config.ec2_instance_type,
        MinCount=1,
        MaxCount=1,
    )
    return response["Instances"][0]["InstanceId"]


def upload_to_s3(config: AppConfig, file_path: str, key: str) -> str:
    config.require("s3")
    s3_client = boto3_client("s3", config)
    s3_client.upload_file(file_path, config.s3_bucket, key)
    return f"s3://{config.s3_bucket}/{key}"


def download_from_s3(config: AppConfig, key: str, destination: str) -> str:
    config.require("s3")
    s3_client = boto3_client("s3", config)
    s3_client.download_file(config.s3_bucket, key, destination)
    return destination


def delete_from_s3(config: AppConfig, key: str) -> str:
    config.require("s3")
    s3_client = boto3_client("s3", config)
    s3_client.delete_object(Bucket=config.s3_bucket, Key=key)
    return f"Deleted s3://{config.s3_bucket}/{key}"


def list_s3_objects(
    config: AppConfig,
    prefix: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    config.require("s3")
    s3_client = boto3_client("s3", config)
    response = s3_client.list_objects_v2(
        Bucket=config.s3_bucket,
        Prefix=prefix,
        MaxKeys=limit,
    )
    return [
        {
            "key": item["Key"],
            "size": item.get("Size", 0),
            "last_modified": item.get("LastModified", "").isoformat()
            if hasattr(item.get("LastModified"), "isoformat")
            else str(item.get("LastModified", "")),
        }
        for item in response.get("Contents", [])
    ]


def search_serpapi(config: AppConfig, query: str) -> dict[str, Any]:
    config.require("serpapi")
    requests = optional_import("requests")
    response = requests.get(
        "https://serpapi.com/search",
        params={"engine": "google", "q": query, "api_key": config.serpapi_api_key},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def huggingface_client(config: AppConfig, model: str) -> Any:
    config.require("huggingface")
    huggingface_hub = optional_import("huggingface_hub")
    return huggingface_hub.InferenceClient(model=model, api_key=config.hf_token)


def extract_hf_text(response: Any) -> str:
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, list) and response:
        return extract_hf_text(response[0])
    if isinstance(response, dict):
        for key in ("generated_text", "summary_text", "text"):
            if response.get(key):
                return str(response[key]).strip()
        choices = response.get("choices")
        if choices:
            return extract_hf_text(choices[0])
        message = response.get("message")
        if message:
            return extract_hf_text(message)
        content = response.get("content")
        if content:
            return str(content).strip()

    choices = getattr(response, "choices", None)
    if choices:
        first = choices[0]
        message = getattr(first, "message", None)
        if message is not None:
            content = getattr(message, "content", None)
            if content:
                return str(content).strip()
        text = getattr(first, "text", None)
        if text:
            return str(text).strip()

    generated_text = getattr(response, "generated_text", None)
    if generated_text:
        return str(generated_text).strip()
    raise RuntimeError("Hugging Face returned an unsupported response shape.")


def generate_text_with_huggingface(
    config: AppConfig,
    prompt: str,
    max_tokens: int = 160,
) -> str:
    client = huggingface_client(config, config.hf_text_model)
    messages = [
        {
            "role": "system",
            "content": "You write concise, practical summaries for developer tooling demos.",
        },
        {"role": "user", "content": prompt},
    ]

    if hasattr(client, "chat_completion"):
        response = client.chat_completion(
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.4,
        )
    else:
        response = client.text_generation(prompt, max_new_tokens=max_tokens)
    return extract_hf_text(response)


def describe_image(config: AppConfig, image_path: str) -> str:
    client = huggingface_client(config, config.hf_vision_model)
    with io.open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
    response = client.image_to_text(image_bytes)
    return extract_hf_text(response)


def search_and_generate(config: AppConfig, query: str) -> str:
    search_results = search_serpapi(config, query)
    snippets = [
        result.get("snippet", "")
        for result in search_results.get("organic_results", [])
        if result.get("snippet")
    ]
    if not snippets:
        return "No search snippets were returned."

    prompt = "Based on the following information, write a concise summary:\n\n"
    return generate_text_with_huggingface(config, prompt + "\n".join(snippets))


def open_url(config: AppConfig) -> str:
    webbrowser.open(config.external_url)
    return f"Opened {config.external_url}"


def doctor_report(config: AppConfig) -> dict[str, Any]:
    feature_requirements = {
        "email": ["email"],
        "location": [],
        "hand_gestures": [],
        "ec2": ["aws"],
        "s3": ["aws", "s3"],
        "search_summary": ["huggingface", "serpapi"],
        "image_detection": ["huggingface"],
    }
    report: dict[str, Any] = {"configuration": config.safe_settings(), "features": {}}

    for feature, config_features in feature_requirements.items():
        missing_config: list[str] = []
        for config_feature in config_features:
            missing_config.extend(config.missing_for(config_feature))

        missing_dependencies = [
            dependency
            for dependency in FEATURE_DEPENDENCIES.get(feature, [])
            if not dependency_installed(dependency)
        ]
        report["features"][feature] = {
            "ready": not missing_config and not missing_dependencies,
            "missing_config": missing_config,
            "missing_dependencies": missing_dependencies,
        }

    return report


def build_demo_report(
    config: AppConfig,
    query: str | None = None,
    image_path: str | None = None,
    include_cloud_status: bool = True,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "configuration": config.safe_settings(),
        "doctor": doctor_report(config),
        "outputs": {},
    }

    if include_cloud_status:
        try:
            report["outputs"]["s3_objects"] = list_s3_objects(
                config,
                prefix="devto-demo/",
                limit=10,
            )
        except Exception as exc:
            report["outputs"]["s3_objects_error"] = str(exc)

        try:
            report["outputs"]["ec2_instances"] = list_ec2_instances(config)
        except Exception as exc:
            report["outputs"]["ec2_instances_error"] = str(exc)

    if query:
        try:
            report["outputs"]["search_summary"] = {
                "query": query,
                "summary": search_and_generate(config, query),
            }
        except Exception as exc:
            report["outputs"]["search_summary_error"] = str(exc)

    if image_path:
        try:
            report["outputs"]["image_description"] = {
                "image": Path(image_path).name,
                "description": describe_image(config, image_path),
            }
        except Exception as exc:
            report["outputs"]["image_description_error"] = str(exc)

    return report


def write_demo_report(config: AppConfig, output_path: str, query: str | None = None) -> str:
    report = build_demo_report(config, query=query)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return str(destination)


def launch_gui(config: AppConfig) -> None:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, simpledialog

    root = tk.Tk()
    root.title("Python Automation Toolkit")
    root.configure(bg="lightgrey")

    result_text = tk.Text(root, width=70, height=18, wrap=tk.WORD)
    result_text.pack(pady=8)

    def show_result(value: Any) -> None:
        result_text.delete(1.0, tk.END)
        if isinstance(value, (dict, list)):
            result_text.insert(tk.END, json.dumps(value, indent=2))
        else:
            result_text.insert(tk.END, str(value))

    def run_action(action: Any) -> None:
        try:
            show_result(action())
        except Exception as exc:  # GUI boundary: convert all errors to dialog text.
            messagebox.showerror("Action failed", str(exc))

    def email_action() -> str:
        receiver = simpledialog.askstring("Receiver Email", "Enter receiver email:")
        message = simpledialog.askstring("Message", "Enter your message:")
        if not receiver or not message:
            raise ValueError("Receiver and message are required.")
        return send_email(config, receiver, message)

    def stop_instance_action() -> str:
        instance_id = simpledialog.askstring("Instance ID", "Enter EC2 instance ID:")
        if not instance_id:
            raise ValueError("Instance ID is required.")
        return stop_ec2_instance(config, instance_id)

    def upload_action() -> str:
        file_path = filedialog.askopenfilename()
        key = simpledialog.askstring("S3 Key", "Enter the object key:")
        if not file_path or not key:
            raise ValueError("File path and S3 key are required.")
        return upload_to_s3(config, file_path, key)

    def download_action() -> str:
        key = simpledialog.askstring("S3 Key", "Enter the object key:")
        destination = filedialog.asksaveasfilename(initialfile=Path(key or "download").name)
        if not key or not destination:
            raise ValueError("S3 key and destination are required.")
        return download_from_s3(config, key, destination)

    def delete_action() -> str:
        key = simpledialog.askstring("S3 Key", "Enter the object key:")
        if not key:
            raise ValueError("S3 key is required.")
        return delete_from_s3(config, key)

    def list_s3_action() -> list[dict[str, Any]]:
        prefix = simpledialog.askstring("S3 Prefix", "Enter a prefix filter:") or ""
        return list_s3_objects(config, prefix=prefix)

    def chatbot_action() -> str:
        query = simpledialog.askstring("Search Summary", "Enter your query:")
        if not query:
            raise ValueError("Query is required.")
        return search_and_generate(config, query)

    def image_action() -> str:
        image_path = filedialog.askopenfilename(
            filetypes=[("Image Files", "*.jpg *.jpeg *.png")]
        )
        if not image_path:
            raise ValueError("Image path is required.")
        return describe_image(config, image_path)

    def demo_report_action() -> str:
        output_path = filedialog.asksaveasfilename(
            initialfile="python-toolkit-demo-report.json",
            defaultextension=".json",
        )
        if not output_path:
            raise ValueError("Output path is required.")
        query = simpledialog.askstring(
            "Demo Query",
            "Enter a search query for the demo report:",
            initialvalue="how automation dashboards help technical training",
        )
        return write_demo_report(config, output_path, query=query)

    groups = [
        (
            "Demo",
            [
                ("Doctor Report", lambda: doctor_report(config)),
                ("Check Configuration", lambda: config.safe_settings()),
                ("Export Demo Report", demo_report_action),
            ],
        ),
        (
            "AI Tools",
            [
                ("Search Summary", chatbot_action),
                ("Image Detection", image_action),
            ],
        ),
        (
            "AWS",
            [
                ("List EC2 Instances", lambda: list_ec2_instances(config)),
                ("Stop EC2 Instance", stop_instance_action),
                ("Launch EC2 Instance", lambda: launch_instance(config)),
                ("Upload to S3", upload_action),
                ("List S3 Objects", list_s3_action),
                ("Download from S3", download_action),
                ("Delete from S3", delete_action),
            ],
        ),
        (
            "Training Helpers",
            [
                ("Send Email", email_action),
                ("Get Location Info", get_location_info),
                ("Capture Hand Gestures", capture_hand_gestures),
                ("Open URL", lambda: open_url(config)),
            ],
        ),
    ]

    for group_name, buttons in groups:
        frame = tk.LabelFrame(root, text=group_name, bg="lightgrey", padx=8, pady=6)
        frame.pack(fill="x", padx=10, pady=4)
        for index, (text, command) in enumerate(buttons):
            tk.Button(
                frame,
                text=text,
                command=lambda action=command: run_action(action),
                bg="blue",
                fg="white",
                width=28,
            ).grid(row=index // 3, column=index % 3, padx=4, pady=3, sticky="ew")

    root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python Automation Training Toolkit")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("check-config", help="Show non-secret configuration status")
    subparsers.add_parser("doctor", help="Check feature readiness")
    subparsers.add_parser("location", help="Show location inferred from current IP")
    subparsers.add_parser("list-ec2", help="List EC2 instances")
    subparsers.add_parser("launch-ec2", help="Launch an EC2 instance")
    subparsers.add_parser("open-url", help="Open the configured external URL")
    subparsers.add_parser("gui", help="Open the Tkinter dashboard")

    stop_ec2 = subparsers.add_parser("stop-ec2", help="Stop one EC2 instance")
    stop_ec2.add_argument("instance_id")

    email = subparsers.add_parser("email", help="Send an email")
    email.add_argument("receiver")
    email.add_argument("message")
    email.add_argument("--subject", default="DOSS Technical Training Project")

    upload = subparsers.add_parser("upload-s3", help="Upload a file to S3")
    upload.add_argument("file_path")
    upload.add_argument("key")

    list_s3 = subparsers.add_parser("list-s3", help="List objects in the configured S3 bucket")
    list_s3.add_argument("--prefix", default="")
    list_s3.add_argument("--limit", type=int, default=20)

    download = subparsers.add_parser("download-s3", help="Download a file from S3")
    download.add_argument("key")
    download.add_argument("destination")

    delete = subparsers.add_parser("delete-s3", help="Delete a file from S3")
    delete.add_argument("key")

    search = subparsers.add_parser("search-summary", help="Search web results and summarize")
    search.add_argument("query")

    image = subparsers.add_parser("describe-image", help="Describe an image")
    image.add_argument("image_path")

    demo_report = subparsers.add_parser("demo-report", help="Export a redacted demo report")
    demo_report.add_argument("output_path")
    demo_report.add_argument("--query")

    return parser


def run_cli(args: argparse.Namespace, config: AppConfig) -> Any:
    if args.command == "check-config":
        return config.safe_settings()
    if args.command == "doctor":
        return doctor_report(config)
    if args.command == "location":
        return get_location_info()
    if args.command == "list-ec2":
        return list_ec2_instances(config)
    if args.command == "launch-ec2":
        return {"instance_id": launch_instance(config)}
    if args.command == "stop-ec2":
        return stop_ec2_instance(config, args.instance_id)
    if args.command == "email":
        return send_email(config, args.receiver, args.message, args.subject)
    if args.command == "upload-s3":
        return upload_to_s3(config, args.file_path, args.key)
    if args.command == "list-s3":
        return list_s3_objects(config, args.prefix, args.limit)
    if args.command == "download-s3":
        return download_from_s3(config, args.key, args.destination)
    if args.command == "delete-s3":
        return delete_from_s3(config, args.key)
    if args.command == "search-summary":
        return search_and_generate(config, args.query)
    if args.command == "describe-image":
        return describe_image(config, args.image_path)
    if args.command == "demo-report":
        return write_demo_report(config, args.output_path, query=args.query)
    if args.command == "open-url":
        return open_url(config)
    if args.command == "gui":
        launch_gui(config)
        return None
    raise ValueError("No command selected.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    config = AppConfig.from_env()
    try:
        config.require_global()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if not argv:
        launch_gui(config)
        return 0

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = run_cli(args, config)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if result is not None:
        if isinstance(result, (dict, list)):
            print(json.dumps(result, indent=2))
        else:
            print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

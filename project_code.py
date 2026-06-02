"""Python Automation Training Toolkit.

The original project was a single Tkinter script that mixed GUI code,
credentials, cloud calls, and optional computer-vision dependencies at import
time. This version keeps the GUI, adds a CLI, and loads external services only
when a user runs the matching tool.
"""

from __future__ import annotations

import argparse
import base64
import importlib
import io
import json
import os
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ConfigError(RuntimeError):
    """Raised when a requested tool is missing required configuration."""


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
    cohere_api_key: str | None = None
    serpapi_api_key: str | None = None
    vision_api_key: str | None = None
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
            cohere_api_key=os.getenv("COHERE_API_KEY"),
            serpapi_api_key=os.getenv("SERPAPI_API_KEY"),
            vision_api_key=os.getenv("VISION_API_KEY"),
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
            "cohere": {"COHERE_API_KEY": self.cohere_api_key},
            "serpapi": {"SERPAPI_API_KEY": self.serpapi_api_key},
            "vision": {"VISION_API_KEY": self.vision_api_key},
            "s3": {"S3_BUCKET": self.s3_bucket},
            "aws": {"AWS_REGION or AWS_DEFAULT_REGION": self.aws_region},
        }
        return [name for name, value in required.get(feature, {}).items() if not value]

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
            "cohere_api_key": "set" if self.cohere_api_key else "missing",
            "serpapi_api_key": "set" if self.serpapi_api_key else "missing",
            "vision_api_key": "set" if self.vision_api_key else "missing",
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


def generate_text_with_cohere(config: AppConfig, prompt: str, max_tokens: int = 120) -> str:
    config.require("cohere")
    cohere = optional_import("cohere")
    client = cohere.Client(config.cohere_api_key)
    response = client.generate(
        model="command-light-nightly",
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=0.75,
    )
    return response.generations[0].text.strip()


def describe_image(config: AppConfig, image_path: str) -> str:
    config.require("vision", "cohere")
    requests = optional_import("requests")
    with io.open(image_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode("utf-8")

    response = requests.post(
        f"https://vision.googleapis.com/v1/images:annotate?key={config.vision_api_key}",
        json={
            "requests": [
                {
                    "image": {"content": encoded_image},
                    "features": [{"type": "LABEL_DETECTION", "maxResults": 10}],
                }
            ]
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"].get("message", "Google Vision API error"))

    labels = [
        label["description"]
        for label in payload.get("responses", [{}])[0].get("labelAnnotations", [])
    ]
    if not labels:
        return "No labels detected."

    prompt = f"Based on these image labels, write a concise summary: {', '.join(labels)}"
    return generate_text_with_cohere(config, prompt)


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
    return generate_text_with_cohere(config, prompt + "\n".join(snippets), max_tokens=160)


def open_url(config: AppConfig) -> str:
    webbrowser.open(config.external_url)
    return f"Opened {config.external_url}"


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

    buttons = [
        ("Check Configuration", lambda: config.safe_settings()),
        ("Send Email", email_action),
        ("Get Location Info", get_location_info),
        ("Capture Hand Gestures", capture_hand_gestures),
        ("List EC2 Instances", lambda: list_ec2_instances(config)),
        ("Stop EC2 Instance", stop_instance_action),
        ("Launch EC2 Instance", lambda: launch_instance(config)),
        ("Open URL", lambda: open_url(config)),
        ("Upload to S3", upload_action),
        ("Download from S3", download_action),
        ("Delete from S3", delete_action),
        ("Search Summary Chatbot", chatbot_action),
        ("Image Detection", image_action),
    ]

    for text, command in buttons:
        tk.Button(
            root,
            text=text,
            command=lambda action=command: run_action(action),
            bg="blue",
            fg="white",
            width=28,
        ).pack(pady=3, padx=10)

    root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python Automation Training Toolkit")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("check-config", help="Show non-secret configuration status")
    subparsers.add_parser("location", help="Show location inferred from current IP")
    subparsers.add_parser("list-ec2", help="List EC2 instances")
    subparsers.add_parser("launch-ec2", help="Launch an EC2 instance")
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

    download = subparsers.add_parser("download-s3", help="Download a file from S3")
    download.add_argument("key")
    download.add_argument("destination")

    delete = subparsers.add_parser("delete-s3", help="Delete a file from S3")
    delete.add_argument("key")

    search = subparsers.add_parser("search-summary", help="Search web results and summarize")
    search.add_argument("query")

    image = subparsers.add_parser("describe-image", help="Describe an image")
    image.add_argument("image_path")

    return parser


def run_cli(args: argparse.Namespace, config: AppConfig) -> Any:
    if args.command == "check-config":
        return config.safe_settings()
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
    if args.command == "download-s3":
        return download_from_s3(config, args.key, args.destination)
    if args.command == "delete-s3":
        return delete_from_s3(config, args.key)
    if args.command == "search-summary":
        return search_and_generate(config, args.query)
    if args.command == "describe-image":
        return describe_image(config, args.image_path)
    if args.command == "gui":
        launch_gui(config)
        return None
    raise ValueError("No command selected.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    config = AppConfig.from_env()
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

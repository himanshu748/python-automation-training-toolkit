"""Automation Toolkit server.

The original project was a single Python script that mixed UI code,
credentials, cloud calls, and optional computer-vision dependencies at import
time. This version serves a multi-page browser workspace, adds command-line
helpers, and loads external services only when a user runs the matching
workflow.
"""

from __future__ import annotations

import argparse
import base64
import http.server
import importlib
import importlib.util
import io
import json
import os
import socketserver
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import webbrowser


class ConfigError(RuntimeError):
    """Raised when a requested tool is missing required configuration."""


class RequestError(RuntimeError):
    """Raised when a local HTTP request is malformed."""


FEATURE_DEPENDENCIES = {
    "email": ["pywhatkit"],
    "location": ["geocoder", "requests"],
    "hand_gestures": [],
    "ec2": ["boto3"],
    "s3": ["boto3"],
    "search_summary": ["huggingface_hub"],
    "image_detection": ["huggingface_hub"],
}

DEFAULT_S3_PREFIX = "training-runs/"
MAX_JSON_BODY_BYTES = 1_000_000
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_HF_QUERY_CHARS = 1_000
MAX_HF_PROMPT_CHARS = 4_000
MAX_HF_OUTPUT_TOKENS = 512
MAX_S3_KEY_BYTES = 1_024
IMAGE_SUFFIXES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_APP_DIR = REPO_ROOT / "apps" / "web"
PAGES_DIR = WEB_APP_DIR / "pages"
ASSETS_DIR = WEB_APP_DIR / "assets"
LOCAL_WORKSPACE_ROOTS = (REPO_ROOT, Path.cwd().resolve())
ROUTES = {
    "/": "landing.html",
    "/index.html": "landing.html",
    "/overview": "overview.html",
    "/overview.html": "overview.html",
    "/models": "models.html",
    "/models.html": "models.html",
    "/cloud": "cloud.html",
    "/cloud.html": "cloud.html",
    "/gestures": "gestures.html",
    "/gestures.html": "gestures.html",
    "/utilities": "utilities.html",
    "/utilities.html": "utilities.html",
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
    hf_text_model: str = "Qwen/Qwen2.5-1.5B-Instruct"
    hf_vision_model: str = "CohereLabs/aya-vision-32b"
    hf_vision_provider: str = "cohere"
    s3_bucket: str | None = None
    aws_region: str | None = None
    ec2_ami_id: str = "ami-09298640a92b2d12c"
    ec2_instance_type: str = "t2.micro"

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            sender_email=os.getenv("SENDER_EMAIL"),
            email_password=os.getenv("EMAIL_PASSWORD"),
            hf_token=os.getenv("HF_TOKEN"),
            hf_text_model=os.getenv("HF_TEXT_MODEL", cls.hf_text_model),
            hf_vision_model=os.getenv("HF_VISION_MODEL", cls.hf_vision_model),
            hf_vision_provider=os.getenv("HF_VISION_PROVIDER", cls.hf_vision_provider),
            s3_bucket=os.getenv("S3_BUCKET"),
            aws_region=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
            ec2_ami_id=os.getenv("EC2_AMI_ID", cls.ec2_ami_id),
            ec2_instance_type=os.getenv("EC2_INSTANCE_TYPE", cls.ec2_instance_type),
        )

    def missing_for(self, feature: str) -> list[str]:
        required = {
            "email": {
                "SENDER_EMAIL": self.sender_email,
                "EMAIL_PASSWORD": self.email_password,
            },
            "huggingface": {"HF_TOKEN": self.hf_token},
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
            "hf_vision_provider": self.hf_vision_provider,
            "s3_bucket": self.s3_bucket or "missing",
            "aws_region": self.aws_region or "missing",
            "ec2_ami_id": self.ec2_ami_id,
            "ec2_instance_type": self.ec2_instance_type,
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


def compact_location_payload(
    source: str,
    coordinates: list[float] | None = None,
    city: str | None = None,
    region: str | None = None,
    country: str | None = None,
    ip_address: str | None = None,
    address: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parts = [item for item in [city, region, country] if item]
    return {
        "source": source,
        "ip": ip_address,
        "coordinates": coordinates,
        "city": city,
        "region": region,
        "country": country,
        "address": address or {},
        "display": ", ".join(parts) if parts else "Location detected",
    }


def location_from_ipapi() -> dict[str, Any]:
    requests = optional_import("requests")
    response = requests.get("https://ipapi.co/json/", timeout=10)
    response.raise_for_status()
    payload = response.json()
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    coordinates = [latitude, longitude] if latitude is not None and longitude is not None else None
    return compact_location_payload(
        source="ipapi.co",
        coordinates=coordinates,
        city=payload.get("city"),
        region=payload.get("region"),
        country=payload.get("country_name") or payload.get("country"),
        ip_address=payload.get("ip"),
        address={
            key: value
            for key, value in {
                "postal": payload.get("postal"),
                "timezone": payload.get("timezone"),
                "org": payload.get("org"),
            }.items()
            if value
        },
    )


def location_from_geocoder() -> dict[str, Any]:
    geocoder = optional_import("geocoder")
    current_ip = geocoder.ip("me")
    coordinate = current_ip.latlng
    if not coordinate:
        raise RuntimeError("Geocoder could not determine coordinates.")

    reverse_lookup = geocoder.osm(coordinate, method="reverse")
    reverse_json = reverse_lookup.json or {}
    address = reverse_json.get("address", {}) if isinstance(reverse_json, dict) else {}
    return compact_location_payload(
        source="geocoder.osm",
        coordinates=coordinate,
        city=getattr(reverse_lookup, "city", None) or address.get("city"),
        region=address.get("state") or address.get("region"),
        country=address.get("country"),
        ip_address=getattr(current_ip, "ip", None),
        address=address,
    )


def get_location_info() -> dict[str, Any]:
    errors: list[str] = []
    for provider in (location_from_ipapi, location_from_geocoder):
        try:
            return provider()
        except Exception as exc:
            errors.append(f"{provider.__name__}: {exc}")
    raise RuntimeError("Could not determine location. " + " | ".join(errors))


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


def validate_s3_key(key: str, *, allow_empty: bool = False) -> str:
    normalized = key.strip()
    if not normalized:
        if allow_empty:
            return ""
        raise ValueError("S3 key is required.")
    if len(normalized.encode("utf-8")) > MAX_S3_KEY_BYTES:
        raise ValueError(f"S3 key must be {MAX_S3_KEY_BYTES} bytes or smaller.")
    if normalized.startswith("/") or "\\" in normalized:
        raise ValueError("S3 key must be relative and use forward slashes.")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError("S3 key must not contain control characters.")
    segments = [segment for segment in normalized.split("/") if segment]
    if any(segment in {".", ".."} for segment in segments):
        raise ValueError("S3 key must not contain path traversal segments.")
    return normalized


def validate_s3_prefix(prefix: str) -> str:
    return validate_s3_key(prefix, allow_empty=True)


def validate_local_workspace_path(path_value: str, *, must_exist: bool) -> Path:
    if not path_value.strip():
        raise ValueError("Local file path is required.")
    path = Path(path_value).expanduser().resolve()
    if not any(path_within_directory(path, root) for root in LOCAL_WORKSPACE_ROOTS):
        allowed = ", ".join(str(root) for root in LOCAL_WORKSPACE_ROOTS)
        raise ValueError(f"Local file path must stay inside: {allowed}")
    if must_exist:
        if not path.exists():
            raise ValueError(f"Local file does not exist: {path_value}")
        if not path.is_file():
            raise ValueError(f"Local path must be a file: {path_value}")
    elif path.exists() and path.is_dir():
        raise ValueError(f"Download destination must be a file path: {path_value}")
    return path


def upload_to_s3(config: AppConfig, file_path: str, key: str) -> str:
    validated_path = validate_local_workspace_path(file_path, must_exist=True)
    validated_key = validate_s3_key(key)
    config.require("s3")
    s3_client = boto3_client("s3", config)
    s3_client.upload_file(str(validated_path), config.s3_bucket, validated_key)
    return f"s3://{config.s3_bucket}/{validated_key}"


def download_from_s3(config: AppConfig, key: str, destination: str) -> str:
    validated_key = validate_s3_key(key)
    validated_destination = validate_local_workspace_path(destination, must_exist=False)
    config.require("s3")
    s3_client = boto3_client("s3", config)
    s3_client.download_file(config.s3_bucket, validated_key, str(validated_destination))
    return str(validated_destination)


def delete_from_s3(config: AppConfig, key: str) -> str:
    validated_key = validate_s3_key(key)
    config.require("s3")
    s3_client = boto3_client("s3", config)
    s3_client.delete_object(Bucket=config.s3_bucket, Key=validated_key)
    return f"Deleted s3://{config.s3_bucket}/{validated_key}"


def list_s3_objects(
    config: AppConfig,
    prefix: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    limit = bounded_int(limit, "limit", minimum=1, maximum=100)
    validated_prefix = validate_s3_prefix(prefix)
    config.require("s3")
    s3_client = boto3_client("s3", config)
    response = s3_client.list_objects_v2(
        Bucket=config.s3_bucket,
        Prefix=validated_prefix,
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


def huggingface_client(
    config: AppConfig,
    model: str,
    provider: str | None = None,
) -> Any:
    config.require("huggingface")
    huggingface_hub = optional_import("huggingface_hub")
    kwargs = {"model": model, "api_key": config.hf_token}
    if provider:
        kwargs["provider"] = provider
    return huggingface_hub.InferenceClient(**kwargs)


def bounded_text(value: str, name: str, max_chars: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required.")
    if len(normalized) > max_chars:
        raise ValueError(f"{name} must be {max_chars} characters or fewer.")
    return normalized


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
    safe_prompt = bounded_text(prompt, "Prompt", MAX_HF_PROMPT_CHARS)
    safe_max_tokens = bounded_int(
        max_tokens,
        "max_tokens",
        minimum=1,
        maximum=MAX_HF_OUTPUT_TOKENS,
    )
    client = huggingface_client(config, config.hf_text_model)
    messages = [
        {
            "role": "system",
            "content": "You write concise, practical summaries for developer tooling workflows.",
        },
        {"role": "user", "content": safe_prompt},
    ]

    try:
        if hasattr(client, "chat_completion"):
            response = client.chat_completion(
                messages=messages,
                max_tokens=safe_max_tokens,
                temperature=0.4,
            )
        else:
            response = client.text_generation(safe_prompt, max_new_tokens=safe_max_tokens)
        return extract_hf_text(response)
    except Exception as exc:
        raise RuntimeError(
            "Hugging Face text generation failed. Check the token, model, and provider availability."
        ) from exc


def image_to_text_with_huggingface(
    config: AppConfig,
    image_bytes: bytes,
    mime_type: str,
) -> str:
    client = huggingface_client(
        config,
        config.hf_vision_model,
        provider=config.hf_vision_provider,
    )
    data_url = (
        f"data:{mime_type};base64,"
        + base64.b64encode(image_bytes).decode("ascii")
    )
    try:
        response = client.chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe this image in one concise sentence.",
                        },
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            max_tokens=80,
            temperature=0.1,
        )
        return extract_hf_text(response)
    except Exception as exc:
        raise RuntimeError(
            "Hugging Face image captioning failed. Check the token, model, and provider availability."
        ) from exc


def validate_local_image_path(image_path: str) -> Path:
    if not image_path.strip():
        raise ValueError("Image path is required.")
    path = Path(image_path).expanduser().resolve()
    if not any(path_within_directory(path, root) for root in LOCAL_WORKSPACE_ROOTS):
        allowed = ", ".join(str(root) for root in LOCAL_WORKSPACE_ROOTS)
        raise ValueError(f"Image path must stay inside: {allowed}")
    if not path.exists():
        raise ValueError(f"Image file does not exist: {image_path}")
    if not path.is_file():
        raise ValueError(f"Image path must be a file: {image_path}")
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        allowed = ", ".join(sorted(IMAGE_SUFFIXES))
        raise ValueError(f"Image file must use one of these extensions: {allowed}")
    if path.stat().st_size > MAX_IMAGE_BYTES:
        raise ValueError(f"Image file must be {MAX_IMAGE_BYTES} bytes or smaller.")
    return path


def image_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".bmp":
        return "image/bmp"
    return "application/octet-stream"


def describe_image(config: AppConfig, image_path: str) -> str:
    validated_path = validate_local_image_path(image_path)
    with io.open(validated_path, "rb") as image_file:
        image_bytes = image_file.read()
    return image_to_text_with_huggingface(
        config,
        image_bytes,
        image_mime_type(validated_path),
    )


def search_and_generate(config: AppConfig, query: str) -> str:
    safe_query = bounded_text(query, "Query", MAX_HF_QUERY_CHARS)
    prompt = (
        "Write a concise, practical summary for a developer training workflow.\n"
        "Use current general knowledge from the model. Include clear next steps "
        "when useful, and avoid pretending to browse the web.\n\n"
        f"Topic: {safe_query}"
    )
    return generate_text_with_huggingface(config, prompt)


def readiness_status(config: AppConfig) -> dict[str, Any]:
    feature_requirements = {
        "email": ["email"],
        "location": [],
        "hand_gestures": [],
        "ec2": ["aws"],
        "s3": ["aws", "s3"],
        "search_summary": ["huggingface"],
        "image_detection": ["huggingface"],
    }
    status: dict[str, Any] = {"configuration": config.safe_settings(), "features": {}}

    for feature, config_features in feature_requirements.items():
        missing_config: list[str] = []
        for config_feature in config_features:
            missing_config.extend(config.missing_for(config_feature))

        missing_dependencies = [
            dependency
            for dependency in FEATURE_DEPENDENCIES.get(feature, [])
            if not dependency_installed(dependency)
        ]
        status["features"][feature] = {
            "ready": not missing_config and not missing_dependencies,
            "missing_config": missing_config,
            "missing_dependencies": missing_dependencies,
        }

    return status


def result_payload(action: Any) -> dict[str, Any]:
    try:
        return {"ok": True, "result": action()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")
    return parsed


def path_within_directory(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def parse_request_json(handler: http.server.BaseHTTPRequestHandler) -> dict[str, Any]:
    raw_length = handler.headers.get("Content-Length", "0") or "0"
    try:
        length = int(raw_length)
    except ValueError as exc:
        raise RequestError("Content-Length must be an integer.") from exc
    if length < 0:
        raise RequestError("Content-Length must be positive.")
    if length > MAX_JSON_BODY_BYTES:
        raise RequestError(f"JSON body must be {MAX_JSON_BODY_BYTES} bytes or smaller.")
    if not length:
        return {}
    try:
        body = handler.rfile.read(length).decode("utf-8")
        payload = json.loads(body or "{}")
    except UnicodeDecodeError as exc:
        raise RequestError("JSON body must be UTF-8.") from exc
    except json.JSONDecodeError as exc:
        raise RequestError("JSON body is invalid.") from exc
    if not isinstance(payload, dict):
        raise RequestError("JSON body must be an object.")
    return payload


def json_response(
    handler: http.server.BaseHTTPRequestHandler,
    payload: Any,
    status: int = 200,
) -> None:
    data = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def build_tailwind_handler(config: AppConfig) -> type[http.server.BaseHTTPRequestHandler]:
    class AutomationDashboardHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def do_GET(self) -> None:
            url = urllib.parse.urlparse(self.path)
            try:
                if url.path in ROUTES:
                    self.serve_html_page(ROUTES[url.path])
                elif url.path.startswith("/assets/"):
                    self.serve_static_asset(url.path.removeprefix("/assets/"))
                elif url.path == "/api/health":
                    json_response(self, readiness_status(config))
                elif url.path == "/api/config":
                    json_response(self, config.safe_settings())
                elif url.path == "/api/list-ec2":
                    json_response(self, result_payload(lambda: list_ec2_instances(config)))
                elif url.path == "/api/list-s3":
                    params = urllib.parse.parse_qs(url.query)
                    prefix = params.get("prefix", [DEFAULT_S3_PREFIX])[0]
                    limit = bounded_int(params.get("limit", ["10"])[0] or 10, "limit", minimum=1, maximum=100)
                    json_response(
                        self,
                        result_payload(lambda: list_s3_objects(config, prefix, limit)),
                    )
                elif url.path == "/api/location":
                    json_response(self, result_payload(get_location_info))
                else:
                    json_response(self, {"error": "Not found"}, status=404)
            except (RequestError, ValueError) as exc:
                json_response(self, {"error": str(exc)}, status=400)
            except Exception as exc:
                json_response(self, {"error": str(exc)}, status=500)

        def do_POST(self) -> None:
            url = urllib.parse.urlparse(self.path)
            try:
                payload = parse_request_json(self)
                if url.path == "/api/search-summary":
                    query = str(payload.get("query", "")).strip()
                    json_response(
                        self,
                        result_payload(lambda: search_and_generate(config, query)),
                    )
                elif url.path == "/api/describe-image":
                    image_path = str(payload.get("image_path", "")).strip()
                    json_response(
                        self,
                        result_payload(lambda: describe_image(config, image_path)),
                    )
                elif url.path == "/api/launch-ec2":
                    json_response(
                        self,
                        result_payload(lambda: {"instance_id": launch_instance(config)}),
                    )
                elif url.path == "/api/stop-ec2":
                    instance_id = str(payload.get("instance_id", "")).strip()
                    if not instance_id:
                        raise ValueError("Instance ID is required.")
                    json_response(
                        self,
                        result_payload(lambda: stop_ec2_instance(config, instance_id)),
                    )
                elif url.path == "/api/upload-s3":
                    file_path = str(payload.get("file_path", "")).strip()
                    key = str(payload.get("key", "")).strip()
                    if not file_path or not key:
                        raise ValueError("File path and S3 key are required.")
                    json_response(
                        self,
                        result_payload(lambda: upload_to_s3(config, file_path, key)),
                    )
                elif url.path == "/api/download-s3":
                    key = str(payload.get("key", "")).strip()
                    destination = str(payload.get("destination", "")).strip()
                    if not key or not destination:
                        raise ValueError("S3 key and destination are required.")
                    json_response(
                        self,
                        result_payload(lambda: download_from_s3(config, key, destination)),
                    )
                elif url.path == "/api/delete-s3":
                    key = str(payload.get("key", "")).strip()
                    if not key:
                        raise ValueError("S3 key is required.")
                    json_response(
                        self,
                        result_payload(lambda: delete_from_s3(config, key)),
                    )
                else:
                    json_response(self, {"error": "Not found"}, status=404)
            except (RequestError, ValueError) as exc:
                json_response(self, {"error": str(exc)}, status=400)
            except Exception as exc:
                json_response(self, {"error": str(exc)}, status=500)

        def serve_html_page(self, filename: str) -> None:
            self.serve_file(PAGES_DIR / filename, "text/html; charset=utf-8")

        def serve_static_asset(self, filename: str) -> None:
            try:
                decoded_filename = urllib.parse.unquote(filename)
            except UnicodeDecodeError:
                json_response(self, {"error": "Not found"}, status=404)
                return
            asset_path = (ASSETS_DIR / decoded_filename).resolve()
            if not path_within_directory(asset_path, ASSETS_DIR):
                json_response(self, {"error": "Not found"}, status=404)
                return
            content_type = "application/javascript; charset=utf-8"
            if asset_path.suffix == ".css":
                content_type = "text/css; charset=utf-8"
            self.serve_file(asset_path, content_type)

        def serve_file(self, path: Path, content_type: str) -> None:
            if not path.exists():
                json_response(self, {"error": "Not found"}, status=404)
                return
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return AutomationDashboardHandler


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def launch_tailwind_dashboard(
    config: AppConfig,
    server_name: str = "127.0.0.1",
    server_port: int = 8000,
    inbrowser: bool = True,
) -> None:
    if not PAGES_DIR.exists():
        raise RuntimeError(f"Missing frontend pages directory: {PAGES_DIR}")
    handler = build_tailwind_handler(config)
    with ReusableTCPServer((server_name, server_port), handler) as httpd:
        url = f"http://{server_name}:{server_port}"
        print(f"Automation dashboard running at {url}")
        if inbrowser:
            webbrowser.open(url)
        httpd.serve_forever()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python Automation Training Toolkit")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("check-config", help="Show non-secret configuration status")
    subparsers.add_parser("doctor", help="Check feature readiness")
    subparsers.add_parser("location", help="Show location inferred from current IP")
    subparsers.add_parser("list-ec2", help="List EC2 instances")
    subparsers.add_parser("launch-ec2", help="Launch an EC2 instance")
    web = subparsers.add_parser("web", help="Open the web dashboard")
    web.add_argument("--server-name", default="127.0.0.1")
    web.add_argument("--server-port", type=int, default=8000)
    web.add_argument("--no-browser", action="store_true")

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

    search = subparsers.add_parser("search-summary", help="Generate a Hugging Face summary")
    search.add_argument("query")

    image = subparsers.add_parser("describe-image", help="Describe an image")
    image.add_argument("image_path")

    return parser


def run_cli(args: argparse.Namespace, config: AppConfig) -> Any:
    if args.command == "check-config":
        return config.safe_settings()
    if args.command == "doctor":
        return readiness_status(config)
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
    if args.command == "web":
        launch_tailwind_dashboard(
            config,
            server_name=args.server_name,
            server_port=args.server_port,
            inbrowser=not args.no_browser,
        )
        return None
    raise ValueError("No command selected.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    config = AppConfig.from_env()

    if not argv:
        launch_tailwind_dashboard(config)
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

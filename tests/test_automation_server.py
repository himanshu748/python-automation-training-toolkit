import io
import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from apps.api import automation_server as project_code


class ConfigTests(unittest.TestCase):
    def test_config_reads_environment_without_exposing_secrets(self):
        env = {
            "SENDER_EMAIL": " me@example.com ",
            "EMAIL_PASSWORD": " secret ",
            "HF_TOKEN": " hf-secret ",
            "HF_TEXT_MODEL": "test/text-model",
            "HF_VISION_MODEL": "test/vision-model",
            "HF_VISION_PROVIDER": "test-provider",
            "AWS_REGION": "ap-south-1",
            "S3_BUCKET": " training-bucket ",
        }
        with patch.dict(os.environ, env, clear=True):
            config = project_code.AppConfig.from_env()

        self.assertEqual(config.sender_email, "me@example.com")
        self.assertEqual(config.email_password, "secret")
        self.assertEqual(config.hf_token, "hf-secret")
        self.assertEqual(config.hf_text_model, "test/text-model")
        self.assertEqual(config.hf_vision_model, "test/vision-model")
        self.assertEqual(config.hf_vision_provider, "test-provider")
        self.assertEqual(config.s3_bucket, "training-bucket")
        self.assertEqual(config.safe_settings()["email_password"], "set")
        self.assertNotIn("secret", str(config.safe_settings()))

    def test_blank_environment_values_are_missing(self):
        env = {
            "SENDER_EMAIL": "   ",
            "EMAIL_PASSWORD": "\n",
            "HF_TOKEN": "\t",
            "S3_BUCKET": "",
            "AWS_REGION": "  ",
            "AWS_DEFAULT_REGION": " ap-south-1 ",
        }
        with patch.dict(os.environ, env, clear=True):
            config = project_code.AppConfig.from_env()

        self.assertIsNone(config.sender_email)
        self.assertIsNone(config.email_password)
        self.assertIsNone(config.hf_token)
        self.assertIsNone(config.s3_bucket)
        self.assertEqual(config.aws_region, "ap-south-1")
        self.assertEqual(config.safe_settings()["hf_token"], "missing")

    def test_missing_config_is_feature_specific(self):
        config = project_code.AppConfig()

        self.assertEqual(
            config.missing_for("email"),
            ["SENDER_EMAIL", "EMAIL_PASSWORD"],
        )
        self.assertEqual(config.missing_for("huggingface"), ["HF_TOKEN"])
        self.assertEqual(config.missing_for("s3"), ["S3_BUCKET"])
        self.assertEqual(config.missing_for("unknown"), [])

    def test_require_raises_actionable_error(self):
        with self.assertRaises(project_code.ConfigError) as caught:
            project_code.AppConfig().require("huggingface")

        self.assertIn("HF_TOKEN", str(caught.exception))

    def test_global_huggingface_token_requirement(self):
        with self.assertRaises(project_code.ConfigError):
            project_code.AppConfig().require_global()

        project_code.AppConfig(hf_token="hf-token").require_global()


class CliTests(unittest.TestCase):
    def test_check_config_command_prints_safe_json(self):
        config = project_code.AppConfig(sender_email="me@example.com")
        args = project_code.build_parser().parse_args(["check-config"])

        result = project_code.run_cli(args, config)

        self.assertEqual(result["sender_email"], "set")
        self.assertEqual(result["hf_token"], "missing")
        self.assertEqual(result["email_password"], "missing")
        self.assertEqual(result["s3_bucket"], "missing")

    def test_doctor_command_returns_missing_config_by_feature(self):
        config = project_code.AppConfig()
        args = project_code.build_parser().parse_args(["doctor"])

        result = project_code.run_cli(args, config)

        self.assertIn("features", result)
        self.assertFalse(result["features"]["email"]["ready"])
        self.assertIn("SENDER_EMAIL", result["features"]["email"]["missing_config"])
        self.assertIn("HF_TOKEN", result["features"]["search_summary"]["missing_config"])

    @patch("apps.api.automation_server.launch_tailwind_dashboard")
    def test_web_command_launches_tailwind_dashboard(self, launch_tailwind_dashboard):
        config = project_code.AppConfig(hf_token="hf-token")
        args = project_code.build_parser().parse_args(
            [
                "web",
                "--server-name",
                "0.0.0.0",
                "--server-port",
                "7861",
                "--no-browser",
            ]
        )

        result = project_code.run_cli(args, config)

        self.assertIsNone(result)
        launch_tailwind_dashboard.assert_called_once_with(
            config,
            server_name="0.0.0.0",
            server_port=7861,
            inbrowser=False,
        )


class FeatureTests(unittest.TestCase):
    def test_optional_import_returns_actionable_error(self):
        with self.assertRaises(RuntimeError) as caught:
            project_code.optional_import("definitely_missing_training_tool")

        self.assertIn("pip install", str(caught.exception))

    def test_tailwind_handler_is_available_for_web_dashboard(self):
        config = project_code.AppConfig(hf_token="hf-token")

        handler = project_code.build_tailwind_handler(config)

        self.assertTrue(issubclass(handler, project_code.http.server.BaseHTTPRequestHandler))

    def test_result_payload_sanitizes_unexpected_action_errors(self):
        result = project_code.result_payload(
            lambda: (_ for _ in ()).throw(RuntimeError("provider leaked hf-token /private/path"))
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "RuntimeError; details omitted")
        self.assertNotIn("hf-token", result["error"])

    def test_result_payload_preserves_validation_errors(self):
        result = project_code.result_payload(
            lambda: (_ for _ in ()).throw(ValueError("S3 key is required."))
        )

        self.assertEqual(result, {"ok": False, "error": "S3 key is required."})

    def test_location_provider_failures_are_sanitized(self):
        def fail_ipapi():
            raise RuntimeError("ipapi failed with hf-token and /private/local/path")

        def fail_geocoder():
            raise RuntimeError("geocoder failed with secret and /private/other/path")

        with patch.object(project_code, "location_from_ipapi", fail_ipapi), patch.object(
            project_code,
            "location_from_geocoder",
            fail_geocoder,
        ):
            with self.assertRaises(RuntimeError) as caught:
                project_code.get_location_info()

        message = str(caught.exception)
        self.assertIn("fail_ipapi: RuntimeError; details omitted", message)
        self.assertIn("fail_geocoder: RuntimeError; details omitted", message)
        self.assertNotIn("hf-token", message)
        self.assertNotIn("secret", message)
        self.assertNotIn("/private/local/path", message)

    @patch("apps.api.automation_server.boto3_client")
    def test_list_s3_objects_returns_small_serializable_records(self, boto3_client):
        client = boto3_client.return_value
        client.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "training-runs/artifact.txt",
                    "Size": 1234,
                    "LastModified": datetime(2026, 6, 2, tzinfo=timezone.utc),
                }
            ]
        }
        config = project_code.AppConfig(aws_region="ap-south-1", s3_bucket="training")

        result = project_code.list_s3_objects(config, prefix="training-runs/", limit=5)

        client.list_objects_v2.assert_called_once_with(
            Bucket="training",
            Prefix="training-runs/",
            MaxKeys=5,
        )
        self.assertEqual(
            result,
            [
                {
                    "key": "training-runs/artifact.txt",
                    "size": 1234,
                    "last_modified": "2026-06-02T00:00:00+00:00",
                }
            ],
        )

    def test_list_s3_objects_bounds_limit(self):
        config = project_code.AppConfig(aws_region="ap-south-1", s3_bucket="training")

        with self.assertRaises(ValueError) as caught:
            project_code.list_s3_objects(config, limit=0)

        self.assertIn("limit must be between 1 and 100", str(caught.exception))

    def test_s3_keys_reject_path_traversal_and_absolute_paths(self):
        for key in ("../secret.txt", "training-runs/../secret.txt", "/secret.txt", "folder\\secret.txt"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                project_code.validate_s3_key(key)

    def test_s3_prefix_allows_empty_but_rejects_traversal(self):
        self.assertEqual(project_code.validate_s3_prefix(""), "")
        self.assertEqual(project_code.validate_s3_prefix("training-runs/"), "training-runs/")

        with self.assertRaises(ValueError):
            project_code.validate_s3_prefix("../")

    @patch("apps.api.automation_server.boto3_client")
    def test_upload_to_s3_validates_file_and_key(self, boto3_client):
        config = project_code.AppConfig(aws_region="ap-south-1", s3_bucket="training")
        with tempfile.NamedTemporaryFile(dir=project_code.REPO_ROOT, suffix=".txt") as upload_file:
            upload_file.write(b"artifact")
            upload_file.flush()

            result = project_code.upload_to_s3(
                config,
                upload_file.name,
                "training-runs/artifact.txt",
            )

        client = boto3_client.return_value
        client.upload_file.assert_called_once_with(
            unittest.mock.ANY,
            "training",
            "training-runs/artifact.txt",
        )
        self.assertEqual(result, "s3://training/training-runs/artifact.txt")

    def test_upload_to_s3_rejects_local_path_escape_before_cloud_call(self):
        config = project_code.AppConfig(aws_region="ap-south-1", s3_bucket="training")

        with self.assertRaises(ValueError) as caught:
            project_code.upload_to_s3(config, "/etc/hosts", "training-runs/hosts.txt")

        self.assertIn("must stay inside", str(caught.exception))

    @patch("apps.api.automation_server.boto3_client")
    def test_download_from_s3_validates_destination_and_key(self, boto3_client):
        config = project_code.AppConfig(aws_region="ap-south-1", s3_bucket="training")
        destination = project_code.REPO_ROOT / "downloads" / "artifact.txt"

        result = project_code.download_from_s3(
            config,
            "training-runs/artifact.txt",
            str(destination),
        )

        client = boto3_client.return_value
        client.download_file.assert_called_once_with(
            "training",
            "training-runs/artifact.txt",
            str(destination.resolve()),
        )
        self.assertEqual(result, str(destination.resolve()))

    @patch("apps.api.automation_server.generate_text_with_huggingface")
    def test_search_and_generate_uses_huggingface_directly(
        self,
        generate_text_with_huggingface,
    ):
        config = project_code.AppConfig(hf_token="hf-token")
        generate_text_with_huggingface.return_value = "A concise summary."

        result = project_code.search_and_generate(config, "training automation")

        self.assertEqual(result, "A concise summary.")
        prompt = generate_text_with_huggingface.call_args.args[1]
        self.assertIn("training automation", prompt)
        self.assertIn("avoid pretending to browse", prompt)

    @patch("apps.api.automation_server.huggingface_client")
    def test_generate_text_with_huggingface_uses_configured_model(self, huggingface_client):
        client = huggingface_client.return_value
        client.chat_completion.return_value = {
            "choices": [{"message": {"content": "HF summary"}}]
        }
        config = project_code.AppConfig(
            hf_token="hf-token",
            hf_text_model="org/text-model",
        )

        result = project_code.generate_text_with_huggingface(config, "Summarize this")

        self.assertEqual(result, "HF summary")
        huggingface_client.assert_called_once_with(config, "org/text-model")
        self.assertEqual(client.chat_completion.call_args.kwargs["max_tokens"], 160)

    def test_generate_text_with_huggingface_bounds_tokens_and_prompt(self):
        config = project_code.AppConfig(hf_token="hf-token")

        with self.assertRaisesRegex(ValueError, "Prompt must be"):
            project_code.generate_text_with_huggingface(
                config,
                "x" * (project_code.MAX_HF_PROMPT_CHARS + 1),
            )

        with self.assertRaisesRegex(ValueError, "max_tokens must be"):
            project_code.generate_text_with_huggingface(
                config,
                "short prompt",
                max_tokens=project_code.MAX_HF_OUTPUT_TOKENS + 1,
            )

    @patch("apps.api.automation_server.huggingface_client")
    def test_generate_text_with_huggingface_sanitizes_provider_errors(self, huggingface_client):
        client = huggingface_client.return_value
        client.chat_completion.side_effect = RuntimeError("provider leaked hf-token")
        config = project_code.AppConfig(hf_token="hf-token")

        with self.assertRaises(RuntimeError) as caught:
            project_code.generate_text_with_huggingface(config, "Summarize this")

        message = str(caught.exception)
        self.assertIn("Hugging Face text generation failed", message)
        self.assertNotIn("hf-token", message)

    def test_search_and_generate_bounds_query(self):
        config = project_code.AppConfig(hf_token="hf-token")

        with self.assertRaisesRegex(ValueError, "Query must be"):
            project_code.search_and_generate(
                config,
                "x" * (project_code.MAX_HF_QUERY_CHARS + 1),
            )

    @patch("apps.api.automation_server.huggingface_client")
    def test_describe_image_uses_huggingface_vision_model(self, huggingface_client):
        client = huggingface_client.return_value
        client.chat_completion.return_value = {
            "choices": [{"message": {"content": "a dashboard screenshot"}}]
        }
        config = project_code.AppConfig(
            hf_token="hf-token",
            hf_vision_model="org/vision-model",
            hf_vision_provider="test-provider",
        )
        with tempfile.NamedTemporaryFile(dir=project_code.REPO_ROOT, suffix=".png") as image_file:
            image_file.write(b"fake-image")
            image_file.flush()

            result = project_code.describe_image(config, image_file.name)

        self.assertEqual(result, "a dashboard screenshot")
        huggingface_client.assert_called_once_with(
            config,
            "org/vision-model",
            provider="test-provider",
        )
        request = client.chat_completion.call_args.kwargs
        self.assertEqual(request["max_tokens"], 80)
        content = request["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_describe_image_rejects_non_image_extension(self):
        config = project_code.AppConfig(hf_token="hf-token")
        with tempfile.NamedTemporaryFile(dir=project_code.REPO_ROOT, suffix=".txt") as text_file:
            text_file.write(b"not-image")
            text_file.flush()

            with self.assertRaises(ValueError) as caught:
                project_code.describe_image(config, text_file.name)

        self.assertIn("Image file must use one of these extensions", str(caught.exception))

    def test_describe_image_rejects_local_path_escape(self):
        config = project_code.AppConfig(hf_token="hf-token")
        with tempfile.NamedTemporaryFile(suffix=".png") as image_file:
            image_file.write(b"fake-image")
            image_file.flush()

            with self.assertRaises(ValueError) as caught:
                project_code.describe_image(config, image_file.name)

        self.assertIn("Image path must stay inside", str(caught.exception))

    @patch("apps.api.automation_server.huggingface_client")
    def test_image_to_text_with_huggingface_sanitizes_provider_errors(self, huggingface_client):
        client = huggingface_client.return_value
        client.chat_completion.side_effect = RuntimeError("provider leaked hf-token")
        config = project_code.AppConfig(
            hf_token="hf-token",
            hf_vision_model="org/vision-model",
            hf_vision_provider="test-provider",
        )

        with self.assertRaises(RuntimeError) as caught:
            project_code.image_to_text_with_huggingface(config, b"fake-image", "image/png")

        message = str(caught.exception)
        self.assertIn("Hugging Face image captioning failed", message)
        self.assertNotIn("hf-token", message)

    def test_static_asset_path_helper_rejects_escape(self):
        root = project_code.ASSETS_DIR

        self.assertTrue(project_code.path_within_directory(root / "app.js", root))
        self.assertFalse(project_code.path_within_directory(root.parent / "pages" / "landing.html", root))

    def test_parse_request_json_rejects_invalid_json(self):
        handler = type(
            "Handler",
            (),
            {
                "headers": {"Content-Length": "5"},
                "rfile": io.BytesIO(b"{bad}"),
            },
        )()

        with self.assertRaises(project_code.RequestError) as caught:
            project_code.parse_request_json(handler)

        self.assertIn("invalid", str(caught.exception))

    def test_main_allows_readiness_commands_without_hf_token(self):
        with patch.dict(os.environ, {}, clear=True), patch("sys.stdout"):
            self.assertEqual(project_code.main(["doctor"]), 0)
            self.assertEqual(project_code.main(["check-config"]), 0)

    def test_main_keeps_feature_specific_hf_requirement(self):
        with patch.dict(os.environ, {}, clear=True), patch("sys.stderr"):
            self.assertEqual(project_code.main(["search-summary", "automation"]), 1)


if __name__ == "__main__":
    unittest.main()

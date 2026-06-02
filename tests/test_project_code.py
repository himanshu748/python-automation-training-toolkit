import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import project_code


class ConfigTests(unittest.TestCase):
    def test_config_reads_environment_without_exposing_secrets(self):
        env = {
            "SENDER_EMAIL": "me@example.com",
            "EMAIL_PASSWORD": "secret",
            "HF_TOKEN": "hf-secret",
            "HF_TEXT_MODEL": "test/text-model",
            "HF_VISION_MODEL": "test/vision-model",
            "SERPAPI_API_KEY": "serp-secret",
            "AWS_REGION": "ap-south-1",
            "S3_BUCKET": "training-bucket",
        }
        with patch.dict(os.environ, env, clear=True):
            config = project_code.AppConfig.from_env()

        self.assertEqual(config.sender_email, "me@example.com")
        self.assertEqual(config.hf_text_model, "test/text-model")
        self.assertEqual(config.hf_vision_model, "test/vision-model")
        self.assertEqual(config.s3_bucket, "training-bucket")
        self.assertEqual(config.safe_settings()["email_password"], "set")
        self.assertNotIn("secret", str(config.safe_settings()))

    def test_missing_config_is_feature_specific(self):
        config = project_code.AppConfig()

        self.assertEqual(
            config.missing_for("email"),
            ["SENDER_EMAIL", "EMAIL_PASSWORD"],
        )
        self.assertEqual(config.missing_for("huggingface"), ["HF_TOKEN"])
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

    def test_doctor_command_reports_missing_config_by_feature(self):
        config = project_code.AppConfig()
        args = project_code.build_parser().parse_args(["doctor"])

        result = project_code.run_cli(args, config)

        self.assertIn("features", result)
        self.assertFalse(result["features"]["email"]["ready"])
        self.assertIn("SENDER_EMAIL", result["features"]["email"]["missing_config"])
        self.assertIn("HF_TOKEN", result["features"]["search_summary"]["missing_config"])

    @patch("project_code.open_url")
    def test_open_url_command_dispatches_to_feature(self, open_url):
        open_url.return_value = "Opened https://example.com"
        config = project_code.AppConfig(external_url="https://example.com")
        args = project_code.build_parser().parse_args(["open-url"])

        result = project_code.run_cli(args, config)

        self.assertEqual(result, "Opened https://example.com")
        open_url.assert_called_once_with(config)


class FeatureTests(unittest.TestCase):
    def test_optional_import_returns_actionable_error(self):
        with self.assertRaises(RuntimeError) as caught:
            project_code.optional_import("definitely_missing_training_tool")

        self.assertIn("pip install", str(caught.exception))

    @patch("project_code.boto3_client")
    def test_list_s3_objects_returns_small_serializable_records(self, boto3_client):
        client = boto3_client.return_value
        client.list_objects_v2.return_value = {
            "Contents": [
                {
                    "Key": "reports/report.pdf",
                    "Size": 1234,
                    "LastModified": datetime(2026, 6, 2, tzinfo=timezone.utc),
                }
            ]
        }
        config = project_code.AppConfig(aws_region="ap-south-1", s3_bucket="training")

        result = project_code.list_s3_objects(config, prefix="reports/", limit=5)

        client.list_objects_v2.assert_called_once_with(
            Bucket="training",
            Prefix="reports/",
            MaxKeys=5,
        )
        self.assertEqual(
            result,
            [
                {
                    "key": "reports/report.pdf",
                    "size": 1234,
                    "last_modified": "2026-06-02T00:00:00+00:00",
                }
            ],
        )

    @patch("project_code.generate_text_with_huggingface")
    @patch("project_code.search_serpapi")
    def test_search_and_generate_summarizes_only_returned_snippets(
        self,
        search_serpapi,
        generate_text_with_huggingface,
    ):
        config = project_code.AppConfig(
            hf_token="hf-token",
            serpapi_api_key="serpapi",
        )
        search_serpapi.return_value = {
            "organic_results": [
                {"snippet": "First useful result."},
                {"title": "No snippet"},
                {"snippet": "Second useful result."},
            ]
        }
        generate_text_with_huggingface.return_value = "A concise summary."

        result = project_code.search_and_generate(config, "training automation")

        self.assertEqual(result, "A concise summary.")
        prompt = generate_text_with_huggingface.call_args.args[1]
        self.assertIn("First useful result.", prompt)
        self.assertIn("Second useful result.", prompt)
        self.assertNotIn("No snippet", prompt)

    @patch("project_code.huggingface_client")
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

    @patch("project_code.huggingface_client")
    def test_describe_image_uses_huggingface_vision_model(self, huggingface_client):
        client = huggingface_client.return_value
        client.image_to_text.return_value = [{"generated_text": "a dashboard screenshot"}]
        config = project_code.AppConfig(
            hf_token="hf-token",
            hf_vision_model="org/vision-model",
        )
        with tempfile.NamedTemporaryFile(suffix=".png") as image_file:
            image_file.write(b"fake-image")
            image_file.flush()

            result = project_code.describe_image(config, image_file.name)

        self.assertEqual(result, "a dashboard screenshot")
        huggingface_client.assert_called_once_with(config, "org/vision-model")

    @patch("project_code.search_and_generate")
    @patch("project_code.list_ec2_instances")
    @patch("project_code.list_s3_objects")
    def test_demo_report_redacts_secrets(
        self,
        list_s3_objects,
        list_ec2_instances,
        search_and_generate,
    ):
        list_s3_objects.return_value = [{"key": "devto-demo/report.txt", "size": 12}]
        list_ec2_instances.return_value = [{"id": "i-123", "state": "running"}]
        search_and_generate.return_value = "Demo summary"
        config = project_code.AppConfig(
            hf_token="hf-secret",
            serpapi_api_key="serp-secret",
            aws_region="ap-south-1",
            s3_bucket="training",
        )

        report = project_code.build_demo_report(config, query="demo query")

        report_text = str(report)
        self.assertIn("Demo summary", report_text)
        self.assertNotIn("hf-secret", report_text)
        self.assertNotIn("serp-secret", report_text)

    def test_main_fails_without_global_hf_token(self):
        with patch.dict(os.environ, {}, clear=True), patch("sys.stderr"):
            self.assertEqual(project_code.main(["doctor"]), 1)


if __name__ == "__main__":
    unittest.main()

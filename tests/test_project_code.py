import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import project_code


class ConfigTests(unittest.TestCase):
    def test_config_reads_environment_without_exposing_secrets(self):
        env = {
            "SENDER_EMAIL": "me@example.com",
            "EMAIL_PASSWORD": "secret",
            "COHERE_API_KEY": "cohere-secret",
            "SERPAPI_API_KEY": "serp-secret",
            "VISION_API_KEY": "vision-secret",
            "AWS_REGION": "ap-south-1",
            "S3_BUCKET": "training-bucket",
        }
        with patch.dict(os.environ, env, clear=True):
            config = project_code.AppConfig.from_env()

        self.assertEqual(config.sender_email, "me@example.com")
        self.assertEqual(config.s3_bucket, "training-bucket")
        self.assertEqual(config.safe_settings()["email_password"], "set")
        self.assertNotIn("secret", str(config.safe_settings()))

    def test_missing_config_is_feature_specific(self):
        config = project_code.AppConfig()

        self.assertEqual(
            config.missing_for("email"),
            ["SENDER_EMAIL", "EMAIL_PASSWORD"],
        )
        self.assertEqual(config.missing_for("cohere"), ["COHERE_API_KEY"])
        self.assertEqual(config.missing_for("unknown"), [])

    def test_require_raises_actionable_error(self):
        with self.assertRaises(project_code.ConfigError) as caught:
            project_code.AppConfig().require("vision", "cohere")

        self.assertIn("VISION_API_KEY", str(caught.exception))
        self.assertIn("COHERE_API_KEY", str(caught.exception))


class CliTests(unittest.TestCase):
    def test_check_config_command_prints_safe_json(self):
        config = project_code.AppConfig(sender_email="me@example.com")
        args = project_code.build_parser().parse_args(["check-config"])

        result = project_code.run_cli(args, config)

        self.assertEqual(result["sender_email"], "set")
        self.assertEqual(result["email_password"], "missing")

    def test_doctor_command_reports_missing_config_by_feature(self):
        config = project_code.AppConfig()
        args = project_code.build_parser().parse_args(["doctor"])

        result = project_code.run_cli(args, config)

        self.assertIn("features", result)
        self.assertFalse(result["features"]["email"]["ready"])
        self.assertIn("SENDER_EMAIL", result["features"]["email"]["missing_config"])
        self.assertIn("COHERE_API_KEY", result["features"]["search_summary"]["missing_config"])

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

    @patch("project_code.generate_text_with_cohere")
    @patch("project_code.search_serpapi")
    def test_search_and_generate_summarizes_only_returned_snippets(
        self,
        search_serpapi,
        generate_text_with_cohere,
    ):
        config = project_code.AppConfig(
            cohere_api_key="cohere",
            serpapi_api_key="serpapi",
        )
        search_serpapi.return_value = {
            "organic_results": [
                {"snippet": "First useful result."},
                {"title": "No snippet"},
                {"snippet": "Second useful result."},
            ]
        }
        generate_text_with_cohere.return_value = "A concise summary."

        result = project_code.search_and_generate(config, "training automation")

        self.assertEqual(result, "A concise summary.")
        prompt = generate_text_with_cohere.call_args.args[1]
        self.assertIn("First useful result.", prompt)
        self.assertIn("Second useful result.", prompt)
        self.assertNotIn("No snippet", prompt)


if __name__ == "__main__":
    unittest.main()

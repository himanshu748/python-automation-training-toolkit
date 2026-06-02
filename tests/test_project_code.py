import os
import unittest
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


if __name__ == "__main__":
    unittest.main()

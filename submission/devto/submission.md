---
title: Python Automation Training Toolkit: from abandoned script to browser-first automation workspace
published: false
tags: devchallenge, githubchallenge, python, ai
cover_image: https://raw.githubusercontent.com/himanshu748/python-automation-training-toolkit/main/submission/assets/cover-devto.png
---

*This is a submission for the [GitHub Finish-Up-A-Thon Challenge](https://dev.to/challenges/github-2026-05-21)*

## What I Built

I finished **Python Automation Training Toolkit**, a Python project that started as a collection of automation exercises and is now a browser-first workspace for running practical developer workflows.

The app now has focused pages for:

- Hugging Face text summaries and image captioning
- AWS EC2 and S3 actions
- Browser-native live hand gesture tracking
- IP-based location lookup
- Readiness checks with redacted configuration output
- CLI and API workflows for repeatable automation

Repository: https://github.com/himanshu748/python-automation-training-toolkit

## Demo

Video walkthrough: https://github.com/himanshu748/python-automation-training-toolkit/blob/main/submission/video/automation-toolkit-demo.mp4

The demo shows the product as a real workspace instead of a one-page script wrapper: the landing page, readiness dashboard, model workflows, separate cloud actions, live browser gesture tracking, and utilities.

## The Comeback Story

This began as a Python automation training project with useful ideas but a scattered experience. The original direction included desktop-style UI, scripts, and separate automation helpers. I brought it back by rebuilding the experience around a clean browser interface and a monorepo layout.

The biggest changes:

- Replaced desktop UI with a multi-page web workspace
- Moved the app into a clearer `apps/api` and `apps/web` structure
- Swapped model workflows to Hugging Face hosted inference
- Added browser-controlled hand gestures with MediaPipe
- Removed stale helper flows and old UI references
- Improved README and design documentation
- Added tests around configuration, model wrappers, cloud wrappers, API behavior, and secret redaction

The project still keeps the spirit of the original toolkit: it teaches and runs automation workflows. It just feels like a product now.

## My Experience with GitHub Copilot

GitHub Copilot helped me move quickly through the finish-up work: restructuring the repository, tightening repetitive UI patterns, mocking external integrations in tests, and checking that old references did not leak into the final product.

The best part was using it as a second pair of eyes while turning a pile of useful scripts into a cleaner product surface. The final result is still intentionally practical: easy to run, easy to inspect, and safe about secrets.

from __future__ import annotations

import math
import os
import struct
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
ASSETS = SUBMISSION / "assets"
VIDEO = SUBMISSION / "video"
DEVTO = SUBMISSION / "devto"

W, H = 1280, 720
FPS = 24
DURATION = 78
TOTAL_FRAMES = FPS * DURATION

COLORS = {
    "bg": (248, 250, 252),
    "ink": (15, 23, 42),
    "muted": (100, 116, 139),
    "panel": (255, 255, 255),
    "line": (226, 232, 240),
    "teal": (13, 148, 136),
    "teal_dark": (15, 118, 110),
    "blue": (37, 99, 235),
    "amber": (217, 119, 6),
    "fuchsia": (192, 38, 211),
    "violet": (124, 58, 237),
    "green": (22, 163, 74),
    "slate": (15, 23, 42),
}


def ensure_dirs() -> None:
    for path in (ASSETS, VIDEO, DEVTO):
        path.mkdir(parents=True, exist_ok=True)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


FONT = {
    "xs": font(16),
    "sm": font(20),
    "base": font(24),
    "md": font(30),
    "lg": font(42, True),
    "xl": font(58, True),
    "hero": font(72, True),
    "mono": font(19),
}


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill, outline=None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str, fill=COLORS["ink"], fnt=None, anchor=None) -> None:
    draw.text(xy, value, fill=fill, font=fnt or FONT["base"], anchor=anchor)


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, value: str, color=COLORS["teal"], bg=(240, 253, 250)) -> None:
    bbox = draw.textbbox((0, 0), value, font=FONT["sm"])
    rounded(draw, (x, y, x + bbox[2] + 34, y + 38), 19, bg, outline=(153, 246, 228))
    text(draw, (x + 17, y + 8), value, fill=color, fnt=FONT["sm"])


def shadow_panel(base: Image.Image, box: tuple[int, int, int, int], radius: int, fill=(255, 255, 255), outline=COLORS["line"]) -> ImageDraw.ImageDraw:
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((box[0] + 0, box[1] + 10, box[2], box[3] + 18), radius=radius, fill=(15, 23, 42, 28))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    base.alpha_composite(shadow)
    draw = ImageDraw.Draw(base)
    rounded(draw, box, radius, fill, outline=outline)
    return draw


def base_frame() -> Image.Image:
    img = Image.new("RGBA", (W, H), COLORS["bg"] + (255,))
    d = ImageDraw.Draw(img)
    for i, color in enumerate([(204, 251, 241, 130), (219, 234, 254, 105), (253, 230, 138, 100)]):
        cx = 220 + i * 470
        cy = 110 + (i % 2) * 440
        d.ellipse((cx - 260, cy - 180, cx + 260, cy + 180), fill=color)
    return img.filter(ImageFilter.GaussianBlur(0.2))


def draw_browser_shell(img: Image.Image, title: str, active: str = "Overview") -> ImageDraw.ImageDraw:
    d = shadow_panel(img, (70, 78, 1210, 650), 24, COLORS["panel"], outline=(203, 213, 225))
    rounded(d, (70, 78, 1210, 132), 24, COLORS["slate"])
    d.rectangle((70, 108, 1210, 132), fill=COLORS["slate"])
    for x, c in [(100, (251, 113, 133)), (128, (251, 191, 36)), (156, (52, 211, 153))]:
        d.ellipse((x, 98, x + 14, 112), fill=c)
    rounded(d, (230, 94, 640, 118), 8, (30, 41, 59))
    text(d, (246, 97), f"localhost:3000/{active.lower()}", fill=(203, 213, 225), fnt=FONT["xs"])
    d.rectangle((70, 132, 255, 650), fill=COLORS["slate"])
    text(d, (96, 162), ">_", fill=(94, 234, 212), fnt=FONT["md"])
    text(d, (137, 161), "Automation Toolkit", fill=(248, 250, 252), fnt=FONT["sm"])
    items = [("Overview", COLORS["teal"]), ("Models", COLORS["blue"]), ("Cloud", COLORS["amber"]), ("Gestures", COLORS["fuchsia"]), ("Utilities", COLORS["violet"])]
    for idx, (name, color) in enumerate(items):
        y = 220 + idx * 52
        if name == active:
            rounded(d, (92, y - 11, 232, y + 28), 10, (51, 65, 85))
            fill = (255, 255, 255)
        else:
            fill = (148, 163, 184)
        d.ellipse((104, y, 114, y + 10), fill=color)
        text(d, (126, y - 8), name, fill=fill, fnt=FONT["sm"])
    text(d, (300, 160), title, fnt=FONT["lg"])
    return d


def draw_cover(path: Path, devto: bool = False) -> None:
    size = (1200, 630) if not devto else (1000, 420)
    img = Image.new("RGBA", size, (248, 250, 252, 255))
    d = ImageDraw.Draw(img)
    for x, y, r, c in [
        (120, 60, 260, (204, 251, 241, 190)),
        (850, 40, 280, (219, 234, 254, 170)),
        (710, 330, 260, (253, 230, 138, 145)),
    ]:
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    img = img.filter(ImageFilter.GaussianBlur(0.4))
    d = ImageDraw.Draw(img)
    pill(d, 72, 70, "GitHub Finish-Up-A-Thon", color=COLORS["teal_dark"])
    title_font = font(66 if not devto else 50, True)
    sub_font = font(28 if not devto else 22)
    text(d, (72, 140), "Python Automation", fill=COLORS["ink"], fnt=title_font)
    text(d, (72, 212 if not devto else 194), "Training Toolkit", fill=COLORS["ink"], fnt=title_font)
    text(d, (76, 315 if not devto else 282), "A forgotten Python utility revived", fill=(51, 65, 85), fnt=sub_font)
    text(d, (76, 350 if not devto else 310), "as a browser-first automation workspace.", fill=(51, 65, 85), fnt=sub_font)
    cards = [
        ("HF", "Models", COLORS["blue"]),
        ("S3", "Cloud", COLORS["amber"]),
        ("✋", "Gestures", COLORS["fuchsia"]),
        ("IP", "Location", COLORS["violet"]),
    ]
    start_x = 72
    card_y = 450 if not devto else 345
    for i, (icon, label, color) in enumerate(cards):
        x = start_x + i * 170
        rounded(d, (x, card_y, x + 142, card_y + 74), 18, (255, 255, 255), outline=(203, 213, 225))
        text(d, (x + 22, card_y + 16), icon, fill=color, fnt=font(25, True))
        text(d, (x + 22, card_y + 43), label, fill=COLORS["ink"], fnt=FONT["sm"])
    if not devto:
        shadow_panel(img, (810, 118, 1135, 520), 24, (255, 255, 255), outline=(203, 213, 225))
        d = ImageDraw.Draw(img)
        rounded(d, (838, 154, 1108, 306), 18, (15, 23, 42), outline=(30, 41, 59))
        for p in [(890, 240), (925, 204), (964, 220), (1002, 190), (1040, 236)]:
            d.ellipse((p[0] - 8, p[1] - 8, p[0] + 8, p[1] + 8), fill=(217, 70, 239))
        for a, b in [((890, 240), (925, 204)), ((925, 204), (964, 220)), ((964, 220), (1002, 190)), ((1002, 190), (1040, 236))]:
            d.line((a[0], a[1], b[0], b[1]), fill=(34, 211, 238), width=5)
        text(d, (844, 348), "Browser camera", fnt=FONT["md"])
        text(d, (844, 388), "Multi-hand gestures", fill=COLORS["muted"], fnt=FONT["sm"])
        text(d, (844, 430), "No desktop popup. No secrets.", fill=COLORS["muted"], fnt=FONT["sm"])
    img.convert("RGB").save(path, quality=95)


def progress(t: float, start: float, end: float) -> float:
    if t <= start:
        return 0.0
    if t >= end:
        return 1.0
    x = (t - start) / (end - start)
    return x * x * (3 - 2 * x)


def cursor(draw: ImageDraw.ImageDraw, x: float, y: float) -> None:
    pts = [(x, y), (x + 4, y + 38), (x + 15, y + 26), (x + 30, y + 52), (x + 42, y + 46), (x + 27, y + 20), (x + 42, y + 18)]
    draw.polygon(pts, fill=(255, 255, 255), outline=(15, 23, 42))


def scene_intro(t: float) -> Image.Image:
    img = base_frame()
    d = ImageDraw.Draw(img)
    pill(d, 86, 92, "Finished from abandoned utility to real product")
    text(d, (86, 165), "Python Automation", fnt=FONT["hero"])
    text(d, (86, 242), "Training Toolkit", fnt=FONT["hero"])
    text(d, (90, 340), "Browser-first automation for models, cloud, location, and live hand gestures.", fill=(51, 65, 85), fnt=FONT["md"])
    for i, label in enumerate(["Hugging Face", "AWS S3 + EC2", "Browser gestures", "Location tools"]):
        x = 90 + i * 278
        rounded(d, (x, 472, x + 232, 548), 18, (255, 255, 255), outline=(203, 213, 225))
        text(d, (x + 22, 500), label, fill=COLORS["ink"], fnt=FONT["sm"])
    return img


def scene_overview(t: float) -> Image.Image:
    img = base_frame()
    d = draw_browser_shell(img, "Overview", "Overview")
    metrics = [("Workflows Ready", "6 / 7", COLORS["green"]), ("HF Token", "set", COLORS["blue"]), ("Secrets", "redacted", COLORS["teal"]), ("Gestures", "browser", COLORS["fuchsia"])]
    for i, (label, value, color) in enumerate(metrics):
        x = 300 + (i % 2) * 405
        y = 220 + (i // 2) * 122
        rounded(d, (x, y, x + 360, y + 90), 14, (255, 255, 255), outline=(226, 232, 240))
        text(d, (x + 20, y + 16), label, fill=COLORS["muted"], fnt=FONT["xs"])
        text(d, (x + 20, y + 44), value, fill=color, fnt=FONT["md"])
    rows = [("Text Summary", "Ready", "Models"), ("Image Captioning", "Ready", "Models"), ("S3 Objects", "Ready", "Cloud"), ("Hand Gestures", "Ready", "Gestures")]
    rounded(d, (300, 478, 1118, 615), 14, (255, 255, 255), outline=(226, 232, 240))
    for i, row in enumerate(rows):
        y = 505 + i * 28
        text(d, (325, y), row[0], fnt=FONT["xs"])
        text(d, (640, y), row[1], fill=COLORS["green"], fnt=FONT["xs"])
        text(d, (850, y), row[2], fill=COLORS["muted"], fnt=FONT["xs"])
    cursor(d, 1000 - 120 * math.sin(t * 1.5), 182 + 24 * math.sin(t))
    return img


def scene_models(t: float) -> Image.Image:
    img = base_frame()
    d = draw_browser_shell(img, "Models", "Models")
    rounded(d, (300, 220, 690, 585), 16, (255, 255, 255), outline=(226, 232, 240))
    text(d, (326, 246), "Text Summary", fnt=FONT["md"])
    rounded(d, (326, 306, 662, 376), 12, (248, 250, 252), outline=(226, 232, 240))
    query = "Explain browser automation workflows"
    reveal = int(len(query) * min(1, max(0, t - 20) / 3))
    text(d, (346, 330), query[:reveal], fill=(51, 65, 85), fnt=FONT["sm"])
    rounded(d, (326, 420, 504, 468), 12, COLORS["blue"])
    text(d, (352, 433), "Generate", fill=(255, 255, 255), fnt=FONT["sm"])
    rounded(d, (725, 220, 1115, 585), 16, (255, 255, 255), outline=(226, 232, 240))
    text(d, (751, 246), "Image Captioning", fnt=FONT["md"])
    rounded(d, (752, 306, 1088, 448), 14, (239, 246, 255), outline=(191, 219, 254))
    text(d, (782, 352), "Upload image", fill=COLORS["blue"], fnt=FONT["md"])
    text(d, (326, 522), "Powered by Hugging Face Inference API", fill=COLORS["muted"], fnt=FONT["sm"])
    cursor(d, 504 + 160 * math.sin(t * 1.2), 470 - 35 * math.cos(t * 0.8))
    return img


def scene_cloud(t: float) -> Image.Image:
    img = base_frame()
    d = draw_browser_shell(img, "Cloud", "Cloud")
    text(d, (300, 210), "Separate controls for each AWS service", fill=COLORS["muted"], fnt=FONT["sm"])
    services = [("EC2", "List, launch, and stop instances", COLORS["amber"]), ("S3", "Upload, list, download, delete objects", COLORS["blue"])]
    for i, (name, desc, color) in enumerate(services):
        x = 300 + i * 420
        rounded(d, (x, 260, x + 380, 535), 18, (255, 255, 255), outline=(226, 232, 240))
        text(d, (x + 28, 298), name, fill=color, fnt=FONT["lg"])
        text(d, (x + 28, 360), desc, fill=COLORS["muted"], fnt=FONT["sm"])
        for j, button in enumerate(["List", "Run", "Stop" if name == "EC2" else "Download"]):
            rounded(d, (x + 28, 420 + j * 48, x + 170, 454 + j * 48), 10, color if j == 0 else (248, 250, 252), outline=(226, 232, 240))
            text(d, (x + 48, 427 + j * 48), button, fill=(255, 255, 255) if j == 0 else COLORS["ink"], fnt=FONT["xs"])
    cursor(d, 362 + 410 * progress(t, 31, 35), 435 + 36 * math.sin(t * 2.4))
    return img


def scene_gestures(t: float) -> Image.Image:
    img = base_frame()
    d = draw_browser_shell(img, "Hand Gestures", "Gestures")
    rounded(d, (300, 220, 815, 575), 18, (15, 23, 42), outline=(30, 41, 59))
    text(d, (330, 250), "Live Camera", fill=(255, 255, 255), fnt=FONT["md"])
    cx = 555 + 50 * math.sin(t * 2)
    cy = 400 + 25 * math.sin(t * 1.4)
    points = []
    for i in range(21):
        ang = i * 0.9 + t * 0.8
        r = 22 + (i % 5) * 10
        points.append((cx + math.cos(ang) * r + (i % 4) * 14, cy - 72 + (i // 4) * 34 + math.sin(ang) * 12))
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 4), (0, 5), (5, 6), (6, 7), (7, 8), (0, 9), (9, 10), (10, 11), (11, 12), (0, 13), (13, 14), (14, 15), (15, 16), (0, 17), (17, 18), (18, 19), (19, 20)]:
        d.line((*points[a], *points[b]), fill=(34, 211, 238), width=5)
    for x, y in points:
        d.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(217, 70, 239), outline=(255, 255, 255))
    rounded(d, (850, 220, 1115, 575), 18, (255, 255, 255), outline=(226, 232, 240))
    for i, (label, value, color) in enumerate([("Status", "Tracking", COLORS["green"]), ("Hands", "2", COLORS["fuchsia"]), ("FPS", "24", COLORS["blue"])]):
        y = 250 + i * 82
        text(d, (880, y), label, fill=COLORS["muted"], fnt=FONT["xs"])
        text(d, (880, y + 26), value, fill=color, fnt=FONT["md"])
    rounded(d, (880, 505, 1068, 545), 12, COLORS["fuchsia"])
    text(d, (902, 515), "Open Palm 96%", fill=(255, 255, 255), fnt=FONT["xs"])
    return img


def scene_utilities(t: float) -> Image.Image:
    img = base_frame()
    d = draw_browser_shell(img, "Utilities", "Utilities")
    rounded(d, (300, 240, 760, 545), 18, (255, 255, 255), outline=(226, 232, 240))
    text(d, (330, 280), "Location Lookup", fnt=FONT["lg"])
    text(d, (332, 338), "Formatted output from a focused utility page.", fill=COLORS["muted"], fnt=FONT["sm"])
    for i, (label, value) in enumerate([("City", "New Delhi"), ("Region", "Delhi"), ("Country", "India"), ("Latitude", "28.6139")]):
        y = 400 + i * 34
        text(d, (334, y), label, fill=COLORS["muted"], fnt=FONT["xs"])
        text(d, (500, y), value, fill=COLORS["ink"], fnt=FONT["xs"])
    rounded(d, (805, 240, 1115, 545), 18, (15, 23, 42), outline=(30, 41, 59))
    text(d, (836, 284), "Clean JSON", fill=(255, 255, 255), fnt=FONT["md"])
    code = ['{', '  "ready": true,', '  "secrets": "redacted",', '  "output": "formatted"', '}']
    for i, line in enumerate(code):
        text(d, (836, 340 + i * 32), line, fill=(203, 213, 225), fnt=FONT["mono"])
    cursor(d, 1010, 522 + 14 * math.sin(t * 2))
    return img


def scene_close(t: float) -> Image.Image:
    img = base_frame()
    d = ImageDraw.Draw(img)
    pill(d, 86, 110, "Solo finish-up")
    text(d, (86, 190), "From abandoned script", fnt=FONT["hero"])
    text(d, (86, 270), "to usable product.", fnt=FONT["hero"])
    text(d, (90, 378), "Monorepo, focused pages, Hugging Face models, cloud controls, live browser gestures, tests, and docs.", fill=(51, 65, 85), fnt=FONT["md"])
    rounded(d, (90, 520, 460, 586), 18, COLORS["teal"])
    text(d, (125, 538), "github.com/himanshu748/python-automation-training-toolkit", fill=(255, 255, 255), fnt=FONT["xs"])
    return img


SCENES = [
    (0, 10, scene_intro),
    (10, 20, scene_overview),
    (20, 31, scene_models),
    (31, 43, scene_cloud),
    (43, 60, scene_gestures),
    (60, 68, scene_utilities),
    (68, 78, scene_close),
]


def frame_at(t: float) -> Image.Image:
    for start, end, fn in SCENES:
        if start <= t < end:
            img = fn(t)
            break
    else:
        img = scene_close(t)
    d = ImageDraw.Draw(img)
    rounded(d, (86, 660, 1194, 684), 12, (226, 232, 240))
    rounded(d, (86, 660, int(86 + 1108 * (t / DURATION)), 684), 12, COLORS["teal"])
    return img.convert("RGB")


def write_audio(path: Path, duration: int = DURATION, sr: int = 44100) -> None:
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(sr)
        for n in range(duration * sr):
            t = n / sr
            env = min(1, t / 5, (duration - t) / 5)
            pad = (
                math.sin(2 * math.pi * 196 * t) * 0.19
                + math.sin(2 * math.pi * 246.94 * t) * 0.13
                + math.sin(2 * math.pi * 329.63 * t) * 0.10
                + math.sin(2 * math.pi * 392 * t) * 0.08
            )
            pulse = math.sin(2 * math.pi * 0.25 * t) * 0.08
            sample = int(max(-1, min(1, (pad + pulse) * env * 0.32)) * 32767)
            wav.writeframes(struct.pack("<hh", sample, sample))


def render_video() -> None:
    temp_video = VIDEO / "automation-toolkit-demo-silent.mp4"
    audio = VIDEO / "soothing-ambient.wav"
    final = VIDEO / "automation-toolkit-demo.mp4"
    write_audio(audio)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-vcodec",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-preset",
        "medium",
        "-crf",
        "18",
        str(temp_video),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, cwd=str(ROOT))
    assert proc.stdin is not None
    for i in range(TOTAL_FRAMES):
        proc.stdin.write(frame_at(i / FPS).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg video render failed")
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(temp_video),
            "-i",
            str(audio),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-shortest",
            str(final),
        ],
        check=True,
        cwd=str(ROOT),
    )


def write_copy() -> None:
    youtube_description = """Python Automation Training Toolkit turns an abandoned Python automation script into a browser-first workspace for real workflows.

What the walkthrough shows:
- Readiness and safe configuration status
- Hugging Face text summaries and image captions
- Separate AWS EC2 and S3 controls
- Browser-native live hand gesture tracking with MediaPipe
- Location utilities, CLI/API support, tests, and docs

Built for the DEV GitHub Finish-Up-A-Thon Challenge.

Repository:
https://github.com/himanshu748/python-automation-training-toolkit

Local run:
python project_code.py

#devchallenge #githubchallenge #python #huggingface #automation
"""
    (SUBMISSION / "youtube-description.txt").write_text(youtube_description, encoding="utf-8")
    (SUBMISSION / "youtube-title.txt").write_text(
        "Python Automation Training Toolkit | Browser-first automation workspace",
        encoding="utf-8",
    )
    dev_post = """---
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
"""
    (DEVTO / "submission.md").write_text(dev_post, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    draw_cover(ASSETS / "cover-youtube.png")
    draw_cover(ASSETS / "cover-devto.png", devto=True)
    render_video()
    write_copy()
    print(f"wrote {VIDEO / 'automation-toolkit-demo.mp4'}")
    print(f"wrote {ASSETS / 'cover-youtube.png'}")
    print(f"wrote {ASSETS / 'cover-devto.png'}")
    print(f"wrote {DEVTO / 'submission.md'}")


if __name__ == "__main__":
    main()

# Design Direction

## Product

Python Automation Training Toolkit is a customer-facing developer operations
workspace. It should feel like a useful product, not an internal script or
one-page prototype.

## Information Architecture

- `/` is a distinct landing page with product positioning, navigation, product
  preview, and clear calls to action.
- `/overview` is the workspace health page for readiness, configuration, and
  environment status.
- `/models` is the Hugging Face page for text summaries and image captions.
- `/cloud` is the AWS page for EC2 and S3 workflows.
- `/gestures` is the browser-native camera page for live hand gesture tracking.
- `/utilities` is the helper page for location lookup and URL opening.

## Visual System

- Use a v0-inspired product interface: crisp white surfaces, slate text, dark
  navy product chrome, restrained shadows, and precise spacing.
- Accent colors:
  - Teal for readiness and primary action
  - Blue for cloud operations
  - Amber for model vision work
  - Violet for utilities
  - Rose only for destructive cloud actions
- Cards are functional panels, not decorative filler. Keep them readable with
  compact 8-12px radii and clear labels.
- Avoid one crowded all-in-one screen. Each page should have one primary job
  and a focused set of controls.

## Landing Page

- The first viewport must immediately show the product name and a realistic
  workspace preview.
- Primary CTA: `Open Workspace`
- Secondary CTA: `View Docs`
- The landing page should show the separate product areas: Overview, Models,
  Cloud, Utilities.
- Avoid language that sounds internal, temporary, or event-specific.

## Workspace Pages

- Keep the shared left sidebar across app pages.
- Each page has a short header, one primary action panel, and one output/status
  area.
- Hand gestures must be treated as a first-class workflow because it was part
  of the original automation toolkit. Camera control belongs in the browser,
  with live landmarks and gesture labels rendered in the page.
- Secrets are displayed only as `set` or `missing`.
- Cloud destructive actions must be visually distinct.
- S3 and local file workflows must validate keys, prefixes, and local paths
  before any AWS call runs.

## Repo Shape

- `apps/api/automation_server.py` owns Python APIs, CLI dispatch, and the web
  server.
- `apps/web/pages` owns individual HTML pages.
- `apps/web/assets` owns shared browser JavaScript and future static assets.
- `tests` validates the API module and route wiring.

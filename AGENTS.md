# Python Automation Training Toolkit Notes

## Project Shape
- `apps/api/automation_server.py` owns the CLI, HTTP API, optional integrations, and static web server.
- `apps/web/pages/` contains the split HTML workspace pages.
- `apps/web/assets/` contains shared browser JavaScript and static assets.
- `project_code.py` is a backward-compatible entrypoint that re-exports the API module.

## Common Commands
- Syntax check: `python -m py_compile project_code.py apps/api/automation_server.py`
- Tests: `python -m unittest discover -s tests`
- Readiness check: `python project_code.py doctor`
- Web app: `python project_code.py web --server-port 8000`

## Conventions
- Keep readiness and configuration commands runnable without secrets.
- Display secrets only as `set` or `missing`.
- Keep optional integrations lazy: import external services only when their workflow runs.
- Keep local HTTP endpoints conservative when they accept filesystem paths.
- Bound model prompts/output tokens before provider calls, and avoid returning raw provider exceptions.
- Keep browser workflow buttons user-visible on failure; failed API calls should render in the output panel instead of becoming unhandled promises.

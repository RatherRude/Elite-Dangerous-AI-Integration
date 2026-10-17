# Development guidelines

## Project

- Python 3.12 backend in `src`, Angular UI in `ui`, Electron shell in `electron`.
- English is the primary project language because most users speak English. Use English for new documentation, code comments and default user-facing text. Keep user-facing text external and localizable, and use the user's language for localized responses.
- See [CONTRIBUTING.md](./CONTRIBUTING.md) for setup and [plugin development](./docs/plugins/Development.md) for extension contracts.
- Use typed constructors for new or modified Python classes: annotate every parameter and the `-> None` return. Dataclass fields must also be typed. Keep TypeScript constructor dependencies explicitly typed.
- Keep changes within the requested feature and follow the surrounding code's naming and formatting.
- Update user-facing documentation when changing settings or behavior.

## Python environment

Run Python commands with **Python 3.12**, after activating `.venv312\Scripts\Activate.ps1` in PowerShell:

```powershell
. .\.venv312\Scripts\Activate.ps1
python --version
python -m pytest test\lib\test_STT.py -q
```

For worktrees without their own environment, activate the main checkout's environment using its location on your machine:

```powershell
$mainCheckout = Read-Host 'Path to the main checkout'
. (Join-Path $mainCheckout '.venv312\Scripts\Activate.ps1')
python --version
```

Activate in the same shell invocation as tests or other Python commands. Separate tool invocations do not share activation state. Do not substitute the system Python or create another environment when the existing one is available.

## Validation

- Python tests live in `test`; run the tests covering the changed modules first.
- UI dependencies and scripts are in `ui\package.json`. Use `npm --prefix ui ci` when dependencies need restoring, `npm --prefix ui run build` to build, and `npm --prefix ui test -- --watch=false --browsers=ChromeHeadless` for browser tests. Set `CHROME_BIN` to a compatible Chromium executable when necessary.
- Mock microphones, provider responses and clocks in automated audio/session tests. Do not download models or call paid providers from unit tests.
- Distinguish passing automated tests from real microphone or packaged-application validation.

## Integrations and compatibility

- Reuse existing interfaces and plugin mechanisms rather than importing optional integrations directly.
- Keep optional dependencies optional and report missing or failed integrations explicitly.
- Preserve existing behavior and configuration compatibility when adding features.
- Document when user data is sent to external services. Avoid logging secrets or unnecessary sensitive user data.

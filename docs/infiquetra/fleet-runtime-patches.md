# Infiquetra Fleet Runtime Patches

`infiquetra/fleet-runtime` is rebuilt from the audited
`NousResearch/hermes-agent` `main` commit:

```text
3a1a3c7e6727a31df89b61b27bad313430bdac45
```

The full commit is the immutable upstream boundary for this rebuild. A newer
upstream `main` requires a separate audit; do not substitute a release tag or a
moving ref. Carry only the five behavior groups below, and drop a group when
its keep/drop test passes against a future audited upstream base without the
patch.

## Carried Runtime Patches

### Configurable Discord voice timeouts

- Files: `hermes_cli/config.py`, `plugins/platforms/discord/adapter.py`,
  `tests/gateway/test_discord_voice_mixer.py`,
  `tests/gateway/test_voice_command.py`, and
  `website/docs/user-guide/messaging/discord.md`.
- Behavior: configure inactivity and playback limits, allow zero to disable
  inactivity only, retain the one-second playback floor, extend playback from
  media duration when available, and safely cancel or rearm timers.
- Keep/drop test: remove the patch only when upstream provides equivalent
  mixer and legacy-playback behavior and the focused voice suite passes without
  these changes.
- Verification: `scripts/run_tests.sh tests/gateway/test_discord_voice_mixer.py
  tests/gateway/test_voice_command.py -q`.

### Interim Discord voice commentary

- Files: `gateway/display_config.py`, `gateway/run.py`,
  `hermes_cli/config.py`, `plugins/platforms/discord/adapter.py`,
  `tests/gateway/test_display_config.py`,
  `tests/gateway/test_voice_command.py`, and
  `website/docs/user-guide/messaging/discord.md`.
- Behavior: optionally speak eligible short interim assistant commentary only
  into an active Discord voice connection. The feature defaults off and rejects
  empty, oversized, code, media, audio-marker, traceback, and error content.
- Keep/drop test: remove the patch only when upstream provides equivalent
  source-scope routing, eligibility, TTS cleanup, and no-chat-attachment
  behavior and all three focused gateway suites pass without these changes.
- Verification: `scripts/run_tests.sh tests/gateway/test_display_config.py
  tests/gateway/test_discord_voice_mixer.py tests/gateway/test_voice_command.py
  -q`.

### `HERMES_DISABLE_COPILOT`

- Files: `hermes_cli/copilot_auth.py`,
  `tests/hermes_cli/test_copilot_auth.py`, and
  `tests/hermes_cli/test_copilot_token_exchange.py`.
- Behavior: accepted truthy values bypass token discovery and exchange. The
  resolver returns `("", "HERMES_DISABLE_COPILOT")`; API-token retrieval
  returns `("", None)`.
- Keep/drop test: remove the patch only when upstream natively preserves both
  tuple contracts and makes no resolution or exchange call while disabled.
- Verification: `scripts/run_tests.sh tests/hermes_cli/test_copilot_auth.py
  tests/hermes_cli/test_copilot_token_exchange.py -q`.

### `hermes cron create --dry-run --json`

- Files: `cron/jobs.py`, `hermes_cli/cron.py`,
  `hermes_cli/subcommands/cron.py`, `tools/cronjob_tools.py`,
  `tests/cron/test_jobs.py`, `tests/cron/test_jobs_changed_notify.py`,
  `tests/hermes_cli/test_cron.py`,
  `tests/hermes_cli/test_cron_parser_builder.py`, and
  `tests/tools/test_cronjob_tools.py`.
- Behavior: preview uses the normal validation and schedule parser, emits
  structured `dry_run`, `would_create`, and `parsed_schedule` fields, rejects
  JSON outside dry-run mode, and never persists or notifies.
- Keep/drop test: remove the patch only when upstream provides an equivalent
  side-effect-free preview and the job-store and provider-notification negative
  tests pass without these changes.
- Verification: `scripts/run_tests.sh tests/cron/test_jobs.py
  tests/cron/test_jobs_changed_notify.py tests/hermes_cli/test_cron.py
  tests/hermes_cli/test_cron_parser_builder.py
  tests/tools/test_cronjob_tools.py -q`.

### `HERMES_TUI_SESSION_TITLE`

- Files: `ui-tui/src/config/env.ts`,
  `ui-tui/src/app/createGatewayEventHandler.ts`, and
  `ui-tui/src/__tests__/createGatewayEventHandler.test.ts`.
- Behavior: trim the requested startup title and pass it only to new sessions
  created because auto-resume is disabled, no recent session exists, or the
  startup config/RPC path fails. Explicit resume and crash recovery retain the
  existing session identity.
- Keep/drop test: remove the patch only when upstream provides equivalent
  cold-start naming without retitling resume or recovery paths.
- Verification: `npm --prefix ui-tui test --
  src/__tests__/createGatewayEventHandler.test.ts`,
  `npm --prefix ui-tui run typecheck`, and
  `npm --prefix ui-tui run build`.

## Required Fork CI and Attribution Support

The following non-runtime paths are maintained in separate commits and are not
fleet behavior patches: `.github/workflows/ci.yml`,
`.github/workflows/contributor-check.yml`, `scripts/release.py`,
`tests/ci/test_contributor_check_workflow.py`, and
`tests/agent/test_anthropic_adapter.py`. They make fork pull-request attribution
use the actual PR base ref, recognize the existing fork author, and keep the
Anthropic setup-token subprocess tests isolated from the macOS Keychain probe.

## Complete Candidate Verification

After the locked Python 3.11 and Node 22 bootstrap, run all focused commands
above and the repository entrypoint:

```bash
scripts/run_tests.sh
```

The diff from the audited upstream base must contain exactly the 24
runtime/doc/test/manifest paths named above plus the five required CI,
attribution, and test-isolation paths. Neither the retired CLI status-bar
behavior nor npm normalization is a carried patch.

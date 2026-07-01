# Infiquetra Fleet Runtime Patches

`infiquetra/fleet-runtime` is rebuilt from `NousResearch/hermes-agent`
`v2026.7.1^{}`:

```text
7c1a029553d87c43ecff8a3821336bc95872213b
```

Carry only the patches listed here. Do not include post-tag upstream `main`
commits unless they are approved separately. Drop a patch when its keep/drop test
passes against a future upstream release without the patch.

## Carried Patches

### Discord Voice Timeout Config

- Source: upstream PR `#50533`.
- Files: `hermes_cli/config.py`, `plugins/platforms/discord/adapter.py`,
  `tests/gateway/test_discord_voice_mixer.py`,
  `tests/gateway/test_voice_command.py`, and
  `website/docs/user-guide/messaging/discord.md`.
- Keep/drop test: drop when an upstream release exposes equivalent configurable
  Discord voice timeout behavior and the voice tests pass without this patch.
- Verification:
  `pytest tests/gateway/test_discord_voice_mixer.py tests/gateway/test_voice_command.py tests/gateway/test_display_config.py`

### Mac Studio Interim Discord Voice Commentary

- Source: Mac Studio runtime diff exported before fleet cleanup.
- Files: `gateway/display_config.py`, `gateway/run.py`, `hermes_cli/config.py`,
  `plugins/platforms/discord/adapter.py`,
  `website/docs/user-guide/messaging/discord.md`, and related gateway tests.
- Keep/drop test: drop when an upstream release provides equivalent voice
  commentary routing/behavior and the gateway voice tests pass without this
  patch.
- Verification:
  `pytest tests/gateway/test_discord_voice_mixer.py tests/gateway/test_voice_command.py tests/gateway/test_display_config.py`

### `HERMES_DISABLE_COPILOT`

- Source: former Infiquetra host-local `patch-copilot-disable.py`, now carried
  as source behavior in `hermes_cli/copilot_auth.py`.
- Files: `hermes_cli/copilot_auth.py`,
  `tests/hermes_cli/test_copilot_auth.py`,
  `tests/hermes_cli/test_copilot_token_exchange.py`.
- Keep/drop test: drop when an upstream release natively bypasses Copilot token
  resolution and exchange under `HERMES_DISABLE_COPILOT`.
- Verification:
  `pytest tests/hermes_cli/test_copilot_auth.py tests/hermes_cli/test_copilot_token_exchange.py`

## Branch Verification

```bash
git fetch upstream tag v2026.7.1
git diff --name-only v2026.7.1...infiquetra/fleet-runtime
pytest \
  tests/gateway/test_discord_voice_mixer.py \
  tests/gateway/test_voice_command.py \
  tests/gateway/test_display_config.py \
  tests/hermes_cli/test_copilot_auth.py \
  tests/hermes_cli/test_copilot_token_exchange.py
```

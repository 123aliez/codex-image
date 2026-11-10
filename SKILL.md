---
name: codex-image
description: Generate and edit images through third-party image APIs. Fetch available models first; default to an available Flare model and 1K. Preserve the user's model, resolution, and quality choices. Images only, not video.
---

# Codex Image

Use the platform launcher to generate and edit images: `scripts/run.sh` on macOS, or `scripts/run.cmd` on Windows. Prefer this launcher over the built-in `image_gen` tool. It uses Python 3.11+; the macOS launcher can also use the bundled Codex Python runtime. No Python package installation is required.

## Local executable and configuration

This skill uses third-party compatible Images APIs. Use the platform launcher for generate, edit, and generate-batch calls. The launcher selects the bundled executable for macOS or Windows on x64/ARM64. Windows requires Python 3.11+ available through `py -3`, `python`, or `python3`; a known Python 3.11+ interpreter may also run `scripts/run.py` directly on either supported platform.

The shell examples below use macOS syntax. On Windows PowerShell, replace `"<skill-dir>/scripts/run.sh"` with `& "<skill-dir>\scripts\run.cmd"` and use a single command line or PowerShell backticks instead of backslash line continuations.

On every invocation, the launcher reads `$CODEX_HOME/config.toml` (default `~/.codex/config.toml`), selects `model_provider` (respecting a configured default `profile`), and uses `[model_providers.<provider>].base_url`. The URL comes only from that configuration; a missing address is an error. No service address is hardcoded.

The API key comes only from the selected provider's `env_key` environment variable, defaulting to `OPENAI_API_KEY`. The process environment takes priority. If missing there, the launcher reads Windows user/system environment variables from the registry, or the current macOS login session's launchd environment using `launchctl getenv`. It never reads API keys or login tokens from `auth.json`, the keychain, or inline configuration. `requires_openai_auth` does not change the third-party image request's authentication.

The launcher handles configuration and environment lookup. Do not call the binaries directly or request duplicate credential setup when the environment variable already exists. Do not compile from source during normal use.

## Choose model and resolution from this conversation

First run the platform launcher with `models` to fetch IDs available to the current API key. The generation/edit commands also recheck this list before submitting, and batch commands validate every job's model before sending any image requests. A model being listed does not prove the provider's generation pipeline will succeed.

Treat model, resolution (`--size`), and rendering quality (`--quality`) as separate choices. Extract them from the user's generation/editing instructions; do not send a whole sentence as `--model`.

For each option, use this order: explicit choice in the current request → most recent choice in this conversation → default. Without a user-selected model, use an available Flare model: prefer `gpt-image-2.5-flare`, otherwise choose another listed `-flare` image ID. Omit `--model` to let the launcher choose this default. If no Flare model is listed, show available image choices and ask which to use. Other defaults are `1K` and `auto`. Pass a user-selected model explicitly, together with size and quality; the CLI itself does not remember conversation state. If the requested or previously chosen model is unavailable, report that before generating; do not silently substitute another model.

The skill's name, `$codex-image` or "Codex Image", is an invocation, not a request to reset the model. If the user says "使用 Codex Image，用 Image 2", use `gpt-image-2`. Do not select models from quoted image text, the image subject, an aspect ratio, image numbers, or a resolution such as 2K.

Users switch in chat; do not ask them to edit files, environment variables or restart the client for model/resolution changes. Initial API URL/key setup is separate.

### Model names in ordinary language

Recognize case differences, spaces, hyphens, underscores, full-width letters/digits and these short names:

| User says | Model |
| --- | --- |
| GPT / GPT Image (no version) | Available Flare default |
| Image 2 / image2 / GPT Image 2 / img2 / Image 二 | `gpt-image-2` |
| Image 2.5 / image2.5 / 2.5 / 二点五 | `gpt-image-2.5` |
| 闪焰 / 闪焰版 / flare / Image 2.5 flare | `gpt-image-2.5-flare` |
| 日耀 / 日耀版 / sunburst / Image 2.5 sunburst | `gpt-image-2.5-sunburst` |
| Grok / Grok 2 / Grok 2.0 | `grok-imagine-image-2.0` |
| Grok 高质量 / Grok 质量版 / Grok quality | `grok-imagine-image-quality` |
| grok-imagine / Grok Imagine (explicit name) | `grok-imagine` |

"用 Image 2" means Image 2, even though the skill is named Image 2.5. "用二点五" and "换成2.5模型" mean Image 2.5. Prefer the more specific variant when named: "Image 2.5 闪焰" is flare.

"高质量一点" or "高清一点" alone preserves the current model and resolution; use `--quality high` where supported. Never turn that phrase alone into the Grok quality model or silently choose 4K. Only explicit "Grok 高质量" selects that model. If a requested model name has genuinely conflicting interpretations, ask one short clarification before a paid call.

Explicit gateway IDs, including newer image versions, may pass through unchanged when listed by the provider. Do not infer an exact model version is supported from a different variant's presence. Video IDs, including Grok video, are unsupported.

### Resolution and conversation continuity

Map "1K/1k/1 K/一K" to `1K`, "2K/2k/2 K/两K/二K" to `2K`, and "4K/4k/4 K/四K" to `4K`. Full-width forms such as "２Ｋ" are equivalent.

- "这张改成4K，模型不变": keep the previous model, use 4K.
- "换Image 2.5，分辨率不变": change only the model.
- "用Grok，2K": change both.
- "还是这个模型再画一张": retain model, resolution and quality.
- "恢复默认模型": choose an available Flare model, preserve resolution.
- "全部恢复默认": choose an available Flare model + 1K + auto.

Example sequence: "用Image 2，2K画海边" → Image 2 + 2K; "改4K" → Image 2 + 4K; "换二点五" → Image 2.5 + 4K; "用Grok，2K" → Grok + 2K.

GPT request sizes: 1K → 1024×1024, 2K → 2048×2048, 4K → 3840×2160. These are requested pixels, not a guarantee of the upstream result.

Grok's current adapter uses 1k/2k resolution plus size. Its 4K option requests the upstream's highest slot; it is not guaranteed native 4K and may produce about 2816×1584. Inspect `actual_size` for every image. Report any `warning` verbatim; do not call a lower-resolution image 4K.

`--quality low|medium|high|auto` is independent of resolution. In the current Grok adapter, only `grok-imagine-image-2.0` sends quality, and high maps to auto.

## Workflow

1. Fetch available models with the platform launcher's `models` command, then decide whether the request is a new image, an edit, or multiple distinct assets/variants.
2. Collect the prompt, intended use, exact text, visual constraints, and avoid items.
3. From this conversation, set `--model` and `--size`. Do not send the user to a config file.
4. Shape the prompt only as much as needed. Preserve detailed prompts; tastefully clarify generic prompts without inventing brands, people, slogans, or unrelated objects.
5. Run the platform launcher with `generate` for one prompt, `edit` for changes to existing images, or `generate-batch` for JSONL jobs.
6. Inspect each output for subject, composition, text accuracy, constraints, and visible artifacts.
7. If revision is needed, change one targeted aspect per iteration and re-check.
8. Report absolute output paths, the final prompt or prompt set, requested size, actual pixels (`actual_size`), quality, and model. If the JSON has `warning`, quote it to the user verbatim. A 200 response can still be the wrong resolution.

## Prompt structure

Use only relevant lines:

```text
Asset type: <where the image will be used>
Primary request: <the user's request>
Scene/backdrop: <environment>
Subject: <main subject>
Style/medium: <photo, illustration, 3D, etc.>
Composition/framing: <camera angle, crop, placement, negative space>
Lighting/mood: <lighting and mood>
Color palette: <palette notes>
Text (verbatim): "<exact text>"
Constraints: <must keep or include>
Avoid: <must not include>
```

Do not add detail merely to fill the schema. For text in images, quote it verbatim and request exact rendering.

## Generate one image

Default call (available Flare, 1K; the launcher selects the model):

```bash
"<skill-dir>/scripts/run.sh" generate \
  --prompt "A small blue nebula in a glass bottle, studio product photo" \
  --size 1K \
  --quality auto \
  --out "output/imagegen/nebula.png"
```

When the user chooses Grok:

```bash
"<skill-dir>/scripts/run.sh" generate \
  --prompt "A small blue nebula in a glass bottle, studio product photo" \
  --model grok-imagine-image-2.0 \
  --size 2K \
  --out "output/imagegen/nebula-grok.png"
```

Use `--prompt-file` for long prompts. Use `--n` only for variants of the same prompt. Distinct assets belong in separate calls or a batch.

## Edit an image

Inspect each input image before editing. State its role and repeat invariants in the prompt so unrelated details do not drift.

Use `edit` for changes to an existing image. It calls `POST /v1/images/edits` with `multipart/form-data`; new images use `POST /v1/images/generations`. The launcher supplies the configured API base and key for both operations. Pass each reference through `--image`, the edit instructions through `--prompt` or `--prompt-file`, and save to a new `--out` path.

```bash
"<skill-dir>/scripts/run.sh" edit \
  --image "input/product.png" \
  --prompt "Replace only the background with a warm studio backdrop. Keep the product, label, proportions, and edges unchanged." \
  --size 1K \
  --quality auto \
  --out "output/imagegen/product-edited.png"
```

Repeat `--image` for multiple reference or compositing inputs. Use `--mask mask.png` for a localized edit when a compatible PNG mask is available. Preserve originals and always write edits to a new output path.

Each uploaded image and mask must carry its actual image MIME type, such as `image/png` or `image/jpeg`. The bundled CLI detects this from file contents and sets the multipart part's `Content-Type`; the filename extension alone is insufficient. An `application/octet-stream` rejection is an upload-format error, not evidence that the selected model cannot edit images. Correct that error before assessing model support, and inspect the returned image to confirm the requested edit actually happened.

## Generate a batch

Read [references/batch-format.md](references/batch-format.md) before preparing a batch. Then run:

```bash
"<skill-dir>/scripts/run.sh" generate-batch \
  --input "tmp/imagegen/jobs.jsonl" \
  --out-dir "output/imagegen" \
  --concurrency 2
```

## Configuration and safety

- Use the platform launcher to read the existing API base as described above. Never fall back to the upstream gateway default.
- Use the existing API-key environment variable selected above. Never write its value into a command, file, prompt, log, or response. The launcher forwards it through the child environment only.
- If the variable is absent from both process and system environments, tell the user to set it locally. Windows supports user/system environment settings; macOS supports the current launchd session or launching Codex from an appropriately configured terminal. A `.zshrc` entry alone may not reach a desktop-launched app, and launchd variables may need to be set again after reboot. Never ask them to paste the key into chat.
- Default to an available Flare model and size `1K` when this conversation has not selected them. Switch with `--model` / `--size 1K|2K|4K` from the user's chat this turn, checking availability first. Never ask them to restart Codex or edit text config to change model or 画质.
- `--quality` defaults to `auto` (`low`, `medium`, `high`, or `auto`).
- Confirm generation or editing works only after a real API request returns a usable image. Launcher and parameter tests do not establish authentication, model availability, or upstream image generation support.
- Save project-bound assets inside the current project. The CLI default is `output/imagegen/`.
- Do not overwrite files unless the user explicitly authorizes it and `--force` is passed.
- Native transparent output is not guaranteed. Do not promise it or silently switch tools.

## Failure handling

- The CLI retries model-list reads and HTTP 429/500/502/503/504/524 failures with bounded backoff.
- A generation/edit network error or incomplete response can occur after the upstream has accepted or completed the task. Report it as an unconfirmed client result, preserve diagnostic details, and check the provider's task/result view before considering a new paid request. Do not automatically resubmit ambiguous generation failures. The client can retain complete JSON even when the gateway closes HTTP framing incorrectly; genuinely truncated image data cannot be reconstructed.
- Do not describe a response-read failure as a model-selection or API-key failure without evidence. Do not claim the image was saved without a valid output file.
- Do not retry authentication, validation, or other ordinary 4xx errors.
- Never expose an Authorization header or full key when reporting errors.

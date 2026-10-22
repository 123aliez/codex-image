"""Adapt the active local Codex configuration to the bundled image CLI."""

import os
from pathlib import Path
import platform
import sys
import tomllib


def api_url(environ):
    codex_dir = Path(environ.get("CODEX_HOME") or Path.home() / ".codex")
    config_path = codex_dir / "config.toml"
    config = {}
    if config_path.exists():
        try:
            with config_path.open("rb") as stream:
                config = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError):
            raise ValueError(f"Cannot read valid TOML from {config_path}") from None

    provider = config.get("model_provider", "openai")
    profile = config.get("profile")
    if profile:
        provider = config.get("profiles", {}).get(profile, {}).get("model_provider", provider)
    url = config.get("model_providers", {}).get(provider, {}).get("base_url")
    if not url:
        url = environ.get("OPENAI_BASE_URL") or environ.get("OPENAI_API_BASE")
    if not isinstance(url, str) or not url.strip():
        raise ValueError(
            f"No API base_url for provider {provider!r} in {config_path}; "
            "configure that provider or set OPENAI_BASE_URL."
        )
    return url.strip()


def main():
    args = sys.argv[1:]
    environ = os.environ.copy()
    key = environ.get("OPENAI_API_KEY", "").strip()
    offline = any(arg in {"--dry-run", "--help", "-h", "help"} for arg in args)
    if not key and not offline:
        raise ValueError("OPENAI_API_KEY is not set; set it locally, then retry.")
    environ["CODEX_API_URL"] = api_url(environ)
    environ["CODEX_API_KEY"] = key
    arch = {"arm64": "arm64", "x86_64": "amd64"}.get(platform.machine())
    if platform.system() != "Darwin" or arch is None:
        raise ValueError("This local launcher supports macOS Intel and Apple Silicon.")
    executable = Path(__file__).resolve().parent.parent / "bin" / f"codex-image2-5-darwin-{arch}"
    os.execve(str(executable), [str(executable), *args], environ)


if __name__ == "__main__":
    try:
        main()
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)

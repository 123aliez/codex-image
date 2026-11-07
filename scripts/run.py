"""Adapt the active local Codex configuration to the bundled image CLI."""

import os
from pathlib import Path
import platform
import subprocess
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


def executable_path():
    system = platform.system()
    machine = platform.machine().lower()
    target = {"Darwin": "darwin", "Windows": "windows"}.get(system)
    arch = {
        "arm64": "arm64", "aarch64": "arm64",
        "x86_64": "amd64", "amd64": "amd64",
    }.get(machine)
    if target is None or arch is None:
        raise ValueError(
            f"Unsupported platform: {system} {machine}. "
            "Supported: macOS and Windows on x64 or ARM64."
        )
    suffix = ".exe" if target == "windows" else ""
    executable = Path(__file__).resolve().parent.parent / "bin" / f"codex-image2-5-{target}-{arch}{suffix}"
    if not executable.is_file():
        raise ValueError(f"Bundled executable not found: {executable}. Reinstall the complete skill.")
    return executable


def main():
    executable = executable_path()
    args = sys.argv[1:]
    environ = os.environ.copy()
    key = environ.get("OPENAI_API_KEY", "").strip()
    offline = any(arg in {"--dry-run", "--help", "-h", "help"} for arg in args)
    if not key and not offline:
        raise ValueError("OPENAI_API_KEY is not set; set it locally, then retry.")
    environ["CODEX_API_URL"] = api_url(environ)
    environ["CODEX_API_KEY"] = key
    # Waiting for the child also preserves output and exit status on Windows,
    # where execve does not provide the same process replacement as on POSIX.
    return subprocess.run([str(executable), *args], env=environ).returncode


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)

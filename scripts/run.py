"""Adapt the active local Codex configuration to the bundled image CLI."""

import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tomllib


def settings(environ):
    codex_dir = Path(environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    config_path = codex_dir / "config.toml"
    config = {}
    if config_path.exists():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, tomllib.TOMLDecodeError):
            raise ValueError(f"Cannot read valid TOML from {config_path}") from None

    provider = config.get("model_provider", "openai")
    profile = config.get("profile")
    if profile:
        provider = config.get("profiles", {}).get(profile, {}).get("model_provider", provider)
    provider_config = config.get("model_providers", {}).get(provider, {})
    return codex_dir, config, provider, provider_config


def api_url(environ, current=None):
    codex_dir, config, provider, provider_config = current or settings(environ)
    url = provider_config.get("base_url")
    if not isinstance(url, str) or not url.strip():
        raise ValueError(
            f"No API base_url for provider {provider!r} in {codex_dir / 'config.toml'}; "
            "configure base_url for that provider."
        )
    return url.strip()


def nonempty_string(value):
    return value.strip() if isinstance(value, str) else ""


def system_environment(name):
    """Read current user/system environment when the app inherited an older copy."""
    system = platform.system()
    if system == "Windows":
        import winreg

        for hive, path in [
            (winreg.HKEY_CURRENT_USER, r"Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        ]:
            try:
                with winreg.OpenKey(hive, path) as registry:
                    value, kind = winreg.QueryValueEx(registry, name)
            except FileNotFoundError:
                continue
            except OSError:
                raise ValueError(f"Cannot read Windows environment variable {name!r}.") from None
            if kind in {winreg.REG_SZ, winreg.REG_EXPAND_SZ} and nonempty_string(value):
                return nonempty_string(value)
    elif system == "Darwin":
        try:
            result = subprocess.run(
                ["/bin/launchctl", "getenv", name], capture_output=True,
                text=True, encoding="utf-8", timeout=5,
            )
        except (OSError, UnicodeError, subprocess.TimeoutExpired):
            raise ValueError(f"Cannot read macOS launchd environment variable {name!r}.") from None
        if result.returncode == 0:
            return nonempty_string(result.stdout)
    return ""


def api_key(environ, current=None):
    codex_dir, config, provider, provider_config = current or settings(environ)
    name = provider_config.get("env_key", "OPENAI_API_KEY")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError(f"Provider {provider!r} has an invalid env_key in config.toml.")
    key = nonempty_string(environ.get(name)) or system_environment(name)
    if key:
        return key
    raise ValueError(
        f"API-key environment variable {name!r} is not set in the process or system environment. "
        "Set the third-party service's key in Windows user/system environment variables or "
        "the macOS launchd environment (launchctl setenv); a temporary value in another conversation is not shared."
    )


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
    current = settings(environ)
    offline = any(arg in {"--dry-run", "--help", "-h", "help"} for arg in args)
    environ["CODEX_API_URL"] = api_url(environ, current)
    environ["CODEX_API_KEY"] = "" if offline else api_key(environ, current)
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

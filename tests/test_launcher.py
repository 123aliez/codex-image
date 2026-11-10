import importlib.util
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("image_launcher", ROOT / "scripts" / "run.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class PlatformTests(unittest.TestCase):
    def test_bundled_targets_and_machine_aliases(self):
        for system, target, machines in [
            ("Darwin", "darwin", {"x86_64": "amd64", "arm64": "arm64"}),
            ("Windows", "windows", {"AMD64": "amd64", "ARM64": "arm64"}),
        ]:
            for machine, arch in machines.items():
                with self.subTest(system=system, machine=machine), \
                        patch.object(launcher.platform, "system", return_value=system), \
                        patch.object(launcher.platform, "machine", return_value=machine):
                    suffix = ".exe" if system == "Windows" else ""
                    executable = launcher.executable_path()
                    self.assertEqual(executable.name, f"codex-image2-5-{target}-{arch}{suffix}")
                    self.assertTrue(executable.is_file())

    def test_unsupported_platforms_have_actionable_errors(self):
        for system, machine in [("Linux", "x86_64"), ("FreeBSD", "amd64"), ("Windows", "x86")]:
            with self.subTest(system=system, machine=machine), \
                    patch.object(launcher.platform, "system", return_value=system), \
                    patch.object(launcher.platform, "machine", return_value=machine):
                with self.assertRaisesRegex(ValueError, "Unsupported platform"):
                    launcher.executable_path()

    def test_incomplete_installation_has_actionable_error(self):
        with patch.object(Path, "is_file", return_value=False):
            with self.assertRaisesRegex(ValueError, "Reinstall the complete skill"):
                launcher.executable_path()


class ConfigurationTests(unittest.TestCase):
    def test_profile_provider_url_comes_only_from_config(self):
        with tempfile.TemporaryDirectory(prefix="codex image config ") as directory:
            config = Path(directory) / "config.toml"
            config.write_text(
                'model_provider = "base"\nprofile = "images"\n'
                '[profiles.images]\nmodel_provider = "image-provider"\n'
                '[model_providers.base]\nbase_url = "https://base.invalid"\n'
                '[model_providers.image-provider]\nbase_url = "https://images.invalid/v1"\n',
                encoding="utf-8",
            )
            environ = {"CODEX_HOME": directory, "OPENAI_BASE_URL": "https://fallback.invalid"}
            self.assertEqual(launcher.api_url(environ), "https://images.invalid/v1")
            config.unlink()
            environ["OPENAI_API_BASE"] = "https://legacy.invalid"
            with self.assertRaisesRegex(ValueError, "No API base_url"):
                launcher.api_url(environ)

    def test_windows_utf8_bom_config(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "config.toml").write_text(
                'model_provider = "third-party"\n[model_providers.third-party]\n'
                'base_url = "https://images.invalid/v1"\n', encoding="utf-8-sig",
            )
            self.assertEqual(launcher.api_url({"CODEX_HOME": directory}), "https://images.invalid/v1")

    def test_child_receives_arguments_and_credentials_without_shell(self):
        executable = ROOT / "a path with spaces" / "image.exe"
        environ = {"OPENAI_API_KEY": "test-only-key"}
        args = ["generate", "--prompt", "蓝色 cup with spaces", "--out", "output path/cup.png"]
        with patch.object(launcher, "executable_path", return_value=executable), \
                patch.object(launcher, "settings", return_value=(ROOT, {}, "test", {})), \
                patch.object(launcher, "api_url", return_value="https://test.invalid"), \
                patch.dict(os.environ, environ, clear=True), \
                patch.object(sys, "argv", ["run.py", *args]), \
                patch.object(launcher.subprocess, "run") as child:
            child.return_value.returncode = 17
            self.assertEqual(launcher.main(), 17)
            self.assertEqual(child.call_args.args[0], [str(executable), *args])
            child_environ = child.call_args.kwargs["env"]
            self.assertEqual(child_environ["CODEX_API_KEY"], "test-only-key")
            self.assertEqual(child_environ["CODEX_API_URL"], "https://test.invalid")
            self.assertNotIn("shell", child.call_args.kwargs)

    def test_generation_without_key_stops_before_child(self):
        with patch.object(launcher, "executable_path", return_value=ROOT / "unused.exe"), \
                patch.object(launcher, "settings", return_value=(ROOT, {}, "test", {})), \
                patch.object(launcher, "api_url", return_value="https://test.invalid"), \
                patch.object(launcher, "system_environment", return_value=""), \
                patch.dict(os.environ, {}, clear=True), \
                patch.object(sys, "argv", ["run.py", "generate", "--prompt", "cup"]), \
                patch.object(launcher.subprocess, "run") as child:
            with self.assertRaisesRegex(ValueError, "API-key environment variable 'OPENAI_API_KEY' is not set"):
                launcher.main()
            child.assert_not_called()


class EnvironmentTests(unittest.TestCase):
    def test_process_environment_takes_priority(self):
        with patch.object(launcher, "system_environment") as system:
            self.assertEqual(launcher.api_key(
                {"OPENAI_API_KEY": " process-key "}, (ROOT, {}, "third-party", {})), "process-key")
            system.assert_not_called()

    def test_provider_environment_name_is_respected(self):
        current = (ROOT, {}, "third-party", {"env_key": "PROVIDER_KEY", "requires_openai_auth": True})
        with patch.object(launcher, "system_environment", return_value="system-provider-key") as system:
            self.assertEqual(launcher.api_key({"OPENAI_API_KEY": "unrelated-key"}, current), "system-provider-key")
            system.assert_called_once_with("PROVIDER_KEY")
        with patch.object(launcher, "system_environment", return_value=""):
            with self.assertRaisesRegex(ValueError, "'PROVIDER_KEY' is not set"):
                launcher.api_key({"OPENAI_API_KEY": "unrelated-key"}, current)

    def test_credentials_are_never_read_from_files_or_inline_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "auth.json").write_text('{"OPENAI_API_KEY":"file-key"}', encoding="utf-8")
            current = (Path(directory), {}, "third-party", {"experimental_bearer_token": "inline-key"})
            with patch.object(launcher, "system_environment", return_value=""):
                with self.assertRaisesRegex(ValueError, "API-key environment variable") as error:
                    launcher.api_key({}, current)
                self.assertNotIn("file-key", str(error.exception))
                self.assertNotIn("inline-key", str(error.exception))

    def test_invalid_environment_name_stops_before_system_lookup(self):
        for name in ["", "--help", "KEY with spaces", 12]:
            with self.subTest(name=name), patch.object(launcher, "system_environment") as system:
                with self.assertRaisesRegex(ValueError, "invalid env_key"):
                    launcher.api_key({}, (ROOT, {}, "third-party", {"env_key": name}))
                system.assert_not_called()

    def test_macos_launchd_lookup_and_missing_value(self):
        with patch.object(launcher.platform, "system", return_value="Darwin"), \
                patch.object(launcher.subprocess, "run") as command:
            command.return_value = SimpleNamespace(returncode=0, stdout=" launchd-key\n")
            self.assertEqual(launcher.system_environment("PROVIDER_KEY"), "launchd-key")
            self.assertEqual(command.call_args.args[0], ["/bin/launchctl", "getenv", "PROVIDER_KEY"])
            self.assertTrue(command.call_args.kwargs["capture_output"])
            command.return_value = SimpleNamespace(returncode=1, stdout="")
            self.assertEqual(launcher.system_environment("PROVIDER_KEY"), "")
            command.side_effect = subprocess.TimeoutExpired("launchctl", 5, output="secret")
            with self.assertRaisesRegex(ValueError, "Cannot read macOS") as error:
                launcher.system_environment("PROVIDER_KEY")
            self.assertNotIn("secret", str(error.exception))

    def test_windows_user_environment_precedes_system(self):
        registry = SimpleNamespace(HKEY_CURRENT_USER=1, HKEY_LOCAL_MACHINE=2, REG_SZ=1, REG_EXPAND_SZ=2)
        opened = []

        class RegistryKey:
            def __init__(self, hive): self.hive = hive
            def __enter__(self): return self
            def __exit__(self, *args): pass

        def open_key(hive, path):
            opened.append((hive, path))
            return RegistryKey(hive)

        def query_value(key, name):
            self.assertEqual(name, "PROVIDER_KEY")
            return ("user-key" if key.hive == 1 else "machine-key"), 1

        registry.OpenKey = open_key
        registry.QueryValueEx = query_value
        with patch.dict(sys.modules, {"winreg": registry}), \
                patch.object(launcher.platform, "system", return_value="Windows"):
            self.assertEqual(launcher.system_environment("PROVIDER_KEY"), "user-key")
            self.assertEqual(opened, [(1, "Environment")])

            def query_system_only(key, name):
                if key.hive == 1:
                    raise FileNotFoundError
                return "machine-key", 1

            registry.QueryValueEx = query_system_only
            self.assertEqual(launcher.system_environment("PROVIDER_KEY"), "machine-key")

    def test_native_system_environment_without_process_inheritance(self):
        name = f"CODEX_IMAGE_TEST_KEY_{os.getpid()}"
        value = "test-system-key"
        self.assertNotIn(name, os.environ)
        if platform.system() == "Windows":
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                try:
                    previous = winreg.QueryValueEx(key, name)
                except FileNotFoundError:
                    previous = None
                try:
                    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
                    self.assertEqual(launcher.system_environment(name), value)
                finally:
                    if previous is None:
                        winreg.DeleteValue(key, name)
                    else:
                        winreg.SetValueEx(key, name, 0, previous[1], previous[0])
        else:
            try:
                subprocess.run(["/bin/launchctl", "setenv", name, value], check=True, capture_output=True, timeout=5)
                self.assertEqual(launcher.system_environment(name), value)
            finally:
                subprocess.run(["/bin/launchctl", "unsetenv", name], capture_output=True, timeout=5)


class NativeLauncherTests(unittest.TestCase):
    def test_authenticated_generation_editing_and_exit_status(self):
        png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF1sAAAAASUVORK5CYII="
        png = base64.b64decode(png_b64)
        requests = []

        class ImageService(BaseHTTPRequestHandler):
            def log_message(self, *args): pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                requests.append((self.path, self.headers.get("Authorization"), self.headers.get("Content-Type"), body))
                if self.headers.get("Authorization") != "Bearer test-only-provider-key":
                    self.send_response(401)
                    self.end_headers()
                    self.wfile.write(b'{"error":{"message":"invalid test key"}}')
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": [{"b64_json": png_b64}]}).encode())

        server = ThreadingHTTPServer(("127.0.0.1", 0), ImageService)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory(prefix="codex image smoke ") as directory:
            skill_dir = Path(directory) / "skill with spaces"
            (skill_dir / "scripts").mkdir(parents=True)
            (skill_dir / "bin").mkdir()
            for name in ["run.py", "run.sh", "run.cmd"]:
                shutil.copy2(ROOT / "scripts" / name, skill_dir / "scripts" / name)
            executable = launcher.executable_path()
            shutil.copy2(executable, skill_dir / "bin" / executable.name)
            commands = [[sys.executable, str(skill_dir / "scripts" / "run.py")]]
            entrypoint = "run.cmd" if platform.system() == "Windows" else "run.sh"
            commands.append([str(skill_dir / "scripts" / entrypoint)])
            environ = os.environ.copy()
            for key in ["OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "OPENAI_API_BASE"]:
                environ.pop(key, None)
            environ["CODEX_IMAGE_PROVIDER_TEST_KEY"] = "test-only-provider-key"
            environ["CODEX_HOME"] = directory
            environ["PYTHONUTF8"] = "1"
            (Path(directory) / "config.toml").write_text(
                'model_provider = "other"\nprofile = "images"\n'
                '[profiles.images]\nmodel_provider = "test"\n'
                '[model_providers.test]\n'
                f'base_url = "http://127.0.0.1:{server.server_port}/v1"\n'
                'env_key = "CODEX_IMAGE_PROVIDER_TEST_KEY"\nrequires_openai_auth = true\n', encoding="utf-8-sig",
            )
            for index, command in enumerate(commands):
                with self.subTest(command=command):
                    out = f"output path/cup-{index}.png"
                    result = subprocess.run(
                        [*command, "generate", "--prompt", "A blue cup with spaces", "--model",
                         "gpt-image-2.5", "--size", "1K", "--out", out, "--max-attempts", "1"],
                        cwd=directory, env=environ, capture_output=True, text=True, encoding="utf-8", timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    data = json.loads(result.stdout)
                    self.assertEqual(Path(data["outputs"][0]).read_bytes(), png)
                    path, authorization, content_type, body = requests[-1]
                    self.assertEqual(path, "/v1/images/generations")
                    self.assertEqual(authorization, "Bearer test-only-provider-key")
                    self.assertEqual(json.loads(body)["prompt"], "A blue cup with spaces")
                    edited = subprocess.run(
                        [*command, "edit", "--image", out, "--prompt", "Change the cup color", "--model",
                         "gpt-image-2.5", "--size", "1K", "--out", f"output path/edited-{index}.png",
                         "--max-attempts", "1"],
                        cwd=directory, env=environ, capture_output=True, text=True, encoding="utf-8", timeout=30,
                    )
                    self.assertEqual(edited.returncode, 0, edited.stderr)
                    self.assertEqual(Path(json.loads(edited.stdout)["outputs"][0]).read_bytes(), png)
                    path, authorization, content_type, body = requests[-1]
                    self.assertEqual(path, "/v1/images/edits")
                    self.assertIn("multipart/form-data", content_type)
                    self.assertIn(b"Content-Type: image/png", body)
                    self.assertIn(png, body)
                    self.assertNotIn("test-only-provider-key", result.stdout + result.stderr + edited.stdout + edited.stderr)
                    bad_args = subprocess.run(
                        [*command, "generate", "--unknown-flag"],
                        cwd=directory, env=environ, capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(bad_args.returncode, 2, bad_args.stderr)
                    wrong_key = {**environ, "CODEX_IMAGE_PROVIDER_TEST_KEY": "wrong-test-key"}
                    denied = subprocess.run(
                        [*command, "generate", "--prompt", "cup", "--out", f"denied-{index}.png", "--max-attempts", "1"],
                        cwd=directory, env=wrong_key, capture_output=True, text=True, timeout=30,
                    )
                    self.assertNotEqual(denied.returncode, 0)
                    self.assertIn("401", denied.stderr)
                    self.assertNotIn("wrong-test-key", denied.stdout + denied.stderr)


if __name__ == "__main__":
    unittest.main()

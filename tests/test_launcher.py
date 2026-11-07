import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
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
    def test_profile_provider_and_environment_fallback(self):
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
            self.assertEqual(launcher.api_url(environ), "https://fallback.invalid")
            del environ["OPENAI_BASE_URL"]
            environ["OPENAI_API_BASE"] = "https://legacy.invalid"
            self.assertEqual(launcher.api_url(environ), "https://legacy.invalid")
            del environ["OPENAI_API_BASE"]
            with self.assertRaisesRegex(ValueError, "No API base_url"):
                launcher.api_url(environ)

    def test_child_receives_arguments_and_credentials_without_shell(self):
        executable = ROOT / "a path with spaces" / "image.exe"
        environ = {"OPENAI_API_KEY": "test-only-key"}
        args = ["generate", "--prompt", "蓝色 cup with spaces", "--out", "output path/cup.png"]
        with patch.object(launcher, "executable_path", return_value=executable), \
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
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(sys, "argv", ["run.py", "generate", "--prompt", "cup"]), \
                patch.object(launcher.subprocess, "run") as child:
            with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY is not set"):
                launcher.main()
            child.assert_not_called()


class NativeLauncherTests(unittest.TestCase):
    def test_dry_run_and_exit_status_through_native_entrypoints(self):
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
            environ["CODEX_HOME"] = directory
            environ["PYTHONUTF8"] = "1"
            (Path(directory) / "config.toml").write_text(
                'model_provider = "test"\n[model_providers.test]\n'
                'base_url = "https://example.invalid/v1"\n', encoding="utf-8",
            )
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(
                        [*command, "generate", "--prompt", "A blue cup with spaces", "--model",
                         "gpt-image-2.5", "--size", "1K", "--out", "output path/cup.png", "--dry-run"],
                        cwd=directory, env=environ, capture_output=True, text=True, encoding="utf-8", timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    data = json.loads(result.stdout)
                    self.assertTrue(data["dry_run"])
                    self.assertEqual(data["endpoint"], "https://example.invalid/v1/images/generations")
                    self.assertEqual(data["payload"]["prompt"], "A blue cup with spaces")
                    self.assertEqual(Path(data["outputs"][0]).name, "cup.png")
                    bad_args = subprocess.run(
                        [*command, "generate", "--unknown-flag", "--dry-run"],
                        cwd=directory, env=environ, capture_output=True, text=True, timeout=30,
                    )
                    self.assertEqual(bad_args.returncode, 2, bad_args.stderr)


if __name__ == "__main__":
    unittest.main()

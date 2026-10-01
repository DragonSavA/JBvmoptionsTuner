from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import main as entry
from jetbrains_vmoptions_tuner import bootstrap


RUNTIME_MODULE = "winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap"


class RuntimeSetupTests(unittest.TestCase):
    def test_compatible_runtime_requires_no_install(self) -> None:
        module = types.ModuleType(RUNTIME_MODULE)
        module.initialize = Mock(return_value=contextlib.nullcontext())
        with (
            patch.dict(sys.modules, {RUNTIME_MODULE: module}),
            patch.object(bootstrap.subprocess, "run") as run,
        ):
            bootstrap.ensure_windows_runtime()
            run.assert_not_called()

    def test_missing_runtime_installs_the_binding_release_and_python_architecture(self) -> None:
        attempts = 0

        def initialize(version="1.7", min_version="7000.498.2246.0", options=0):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError("No compatible Windows App Runtime")
            return contextlib.nullcontext()

        module = types.ModuleType(RUNTIME_MODULE)
        module.initialize = initialize
        with (
            patch.dict(sys.modules, {RUNTIME_MODULE: module}),
            patch.object(bootstrap.subprocess, "run") as run,
        ):
            with patch.object(bootstrap.sysconfig, "get_platform", return_value="win-arm64"):
                bootstrap.ensure_windows_runtime()
            command = run.call_args.args[0]
            self.assertEqual(command[command.index("-Release") + 1], "1.7")
            self.assertEqual(command[command.index("-Architecture") + 1], "arm64")
            self.assertEqual(attempts, 2)

    def test_dependency_failure_stops_before_runtime_and_shortcut_setup(self) -> None:
        with patch.object(bootstrap.sys, "platform", "win32"):
            with patch.object(
                bootstrap,
                "ensure_python_dependencies",
                side_effect=subprocess.CalledProcessError(1, "pip"),
            ):
                with (
                    patch.object(bootstrap, "ensure_windows_runtime") as runtime,
                    patch.object(bootstrap.desktop_shortcut, "reconcile") as shortcut,
                ):
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(bootstrap.main(), 1)
                    runtime.assert_not_called()
                    shortcut.assert_not_called()


class DirectLaunchTests(unittest.TestCase):
    def test_pythonw_delegation_preserves_silent_background_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
            pythonw.parent.mkdir(parents=True)
            pythonw.touch()
            script = root / "main.py"
            with (
                patch.object(entry, "__file__", str(script)),
                patch.object(entry, "os", types.SimpleNamespace(name="nt")),
            ):
                with (
                    patch.object(entry.sys, "executable", str(root / "system" / "pythonw.exe")),
                    patch.object(entry.sys, "argv", [str(script), "--background"]),
                ):
                    with patch.object(
                        entry.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)
                    ) as run:
                        self.assertEqual(entry.main(), 0)
                        self.assertEqual(Path(run.call_args.args[0][0]), pythonw.resolve())

    def test_direct_python_uses_prepared_environment_and_preserves_arguments_and_exit_code(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / ".venv" / "Scripts" / "python.exe"
            python.parent.mkdir(parents=True)
            python.touch()
            script = root / "main.py"
            with (
                patch.object(entry, "__file__", str(script)),
                patch.object(entry, "os", types.SimpleNamespace(name="nt")),
            ):
                with patch.object(entry.sys, "argv", [str(script), "--background"]):
                    with patch.object(
                        entry.subprocess, "run", return_value=types.SimpleNamespace(returncode=7)
                    ) as run:
                        self.assertEqual(entry.main(), 7)
                        self.assertEqual(
                            run.call_args.args[0],
                            [str(python.resolve()), str(script.resolve()), "--background"],
                        )


if __name__ == "__main__":
    unittest.main()

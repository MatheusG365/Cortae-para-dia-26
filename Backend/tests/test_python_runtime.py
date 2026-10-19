"""Architecture rejection and safe environment migration, without external services."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import runtime_check


ROOT = Path(__file__).resolve().parents[2]


class PythonRuntimeTests(unittest.TestCase):
    def test_accepts_python_312_x86(self):
        with patch.object(runtime_check.struct, 'calcsize', return_value=4), \
                patch.object(runtime_check.sys, 'version_info', (3, 12, 10)):
            self.assertEqual(runtime_check.require_supported_python(), 32)

    def test_rejects_x64_even_with_recent_python(self):
        with patch.object(runtime_check.struct, 'calcsize', return_value=8), \
                patch.object(runtime_check.sys, 'version_info', (3, 13, 0)):
            with self.assertRaisesRegex(RuntimeError, '64 bits'):
                runtime_check.require_supported_python()

    def test_rejects_older_x86(self):
        with patch.object(runtime_check.struct, 'calcsize', return_value=4), \
                patch.object(runtime_check.sys, 'version_info', (3, 11, 9)):
            with self.assertRaisesRegex(RuntimeError, '3.12'):
                runtime_check.require_supported_python()

    def test_application_rejects_x64_before_third_party_imports(self):
        # -S disables installed dependencies; the architecture error must still win.
        code = "import struct; struct.calcsize=lambda _:8; import application"
        result = subprocess.run([sys.executable, '-S', '-c', code],
                                cwd=ROOT / 'Backend', capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('64 bits', result.stderr)
        self.assertNotIn('ModuleNotFoundError', result.stderr)


@unittest.skipUnless(shutil.which('powershell.exe'), 'Windows PowerShell required')
class PythonSetupTests(unittest.TestCase):
    def run_script(self, code):
        helper = str(ROOT / 'Python-Cortae.ps1').replace("'", "''")
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command',
             "$ErrorActionPreference='Stop'; . '" + helper + "'; " + code],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_probe_reads_actual_interpreter(self):
        interpreter = sys.executable.replace("'", "''")
        output = self.run_script(
            "$info = Get-CortaePythonInfo '" + interpreter + "'; "
            "if ($info.bits -ne 32 -or $info.major -lt 3 -or $info.minor -lt 12) { throw 'Bad probe' }")
        self.assertEqual(output.strip(), '')

    def test_explicit_x64_is_rejected(self):
        interpreter = sys.executable.replace("'", "''")
        self.run_script(
            "function Get-CortaePythonInfo { @{bits=64; major=3; minor=12; version='3.12'} }; "
            "$rejected=$false; try { Resolve-CortaePython '" + interpreter + "' } "
            "catch { $rejected=$_.Exception.Message -match '64 bits' }; "
            "if (-not $rejected) { throw 'x64 accepted' }")

    def test_valid_environment_is_kept(self):
        self.run_script(
            "function Get-CortaePythonInfo { @{bits=32; major=3; minor=12; version='3.12'} }; "
            "function New-CortaeVirtualEnvironment { throw 'Must not recreate' }; "
            "$result=Initialize-CortaePythonEnvironment 'C:\\fixture\\Backend'; "
            "if ($result -notlike '*Scripts\\python.exe') { throw 'Bad interpreter' }")

    def test_missing_launcher_version_falls_back_to_valid_path_python(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / 'missing-python.cmd'
            launcher.write_text('@echo off\necho Missing interpreter 1>&2\nexit /b 1\n')
            launcher_ps = str(launcher).replace("'", "''")
            interpreter = sys.executable.replace("'", "''")
            self.run_script(
                "function Get-Command { param($Name); if ($Name -eq 'py.exe') "
                "{ return @{Source='" + launcher_ps + "'} }; "
                "if ($Name -eq 'python.exe') { return @{Source='" + interpreter + "'} } }; "
                "$selected=Resolve-CortaePython; "
                "if ($selected -ne '" + interpreter + "') { throw 'Fallback failed' }")

    def run_migration(self, fail=False, unavailable=False):
        with tempfile.TemporaryDirectory() as directory:
            backend = Path(directory) / 'Backend'
            environment = backend / '.venv'
            environment.mkdir(parents=True)
            (environment / 'preserve.txt').write_text('original', encoding='utf-8')
            backend_ps = str(backend).replace("'", "''")
            creation = (
                "function New-CortaeVirtualEnvironment { param($BasePython,$EnvironmentPath); "
                "New-Item -ItemType Directory -Path (Join-Path $EnvironmentPath 'Scripts') -Force | Out-Null; "
                "Set-Content -LiteralPath (Join-Path $EnvironmentPath 'ready') -Value 'new'; "
                + ("throw 'Simulated creation failure'" if fail else '') + " }; ")
            resolver = ("function Resolve-CortaePython { throw 'No x86 available' }; " if unavailable
                        else "function Resolve-CortaePython { return 'C:\\base\\python.exe' }; ")
            probe = (
                "function Get-CortaePythonInfo { param($PythonPath); "
                "$envPath=Split-Path -Parent (Split-Path -Parent $PythonPath); "
                "if (Test-Path -LiteralPath (Join-Path $envPath 'ready')) "
                "{ return @{bits=32;major=3;minor=12;version='3.12'} }; return $null }; ")
            command = "$failed=$false; try { Initialize-CortaePythonEnvironment '" + backend_ps + "' | Out-Null } catch { $failed=$true }; "
            command += ("if (-not $failed) { throw 'Expected failure' }" if fail or unavailable
                        else "if ($failed) { throw 'Unexpected failure' }")
            self.run_script(resolver + probe + creation + command)
            archives = Path(directory) / '.runtime' / 'python-environments'
            if fail or unavailable:
                self.assertEqual((environment / 'preserve.txt').read_text(), 'original')
                if unavailable:
                    self.assertFalse(archives.exists())
                else:
                    self.assertEqual(len(list(archives.glob('venv-failed-*'))), 1)
            else:
                self.assertTrue((environment / 'ready').exists())
                backups = list(archives.glob('venv-backup-*'))
                self.assertEqual(len(backups), 1)
                self.assertEqual((backups[0] / 'preserve.txt').read_text(), 'original')

    def test_migration_preserves_original_environment(self):
        self.run_migration()

    def test_creation_failure_restores_original_and_preserves_failed_attempt(self):
        self.run_migration(fail=True)

    def test_missing_x86_keeps_original_untouched(self):
        self.run_migration(unavailable=True)


if __name__ == '__main__':
    unittest.main()

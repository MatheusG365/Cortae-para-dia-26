"""Portable runtime checks use mocks or disposable files, never application data."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import firebird_runtime as runtime


class FirebirdVersionChecks(unittest.TestCase):
    def test_defaults_local3054_and_explicit_remote_configuration(self):
        with patch.object(runtime, 'dotenv_values', return_value={}), patch.dict(os.environ, {}, clear=True):
            main, log = runtime.settings()
            self.assertEqual((main['port'], log['port']), (3054, 3054))
            self.assertEqual(Path(main['database']).name, 'CORTAE.FDB')
            self.assertEqual(Path(log['database']).name, 'LOG_CORTAE.FDB')
        with patch.object(runtime, 'dotenv_values', return_value={}), patch.dict(os.environ,
                {'DB_HOST':'remote.example','DB_PORT':'4054','DB_PASSWORD':'private'}, clear=True):
            main, log = runtime.settings()
            self.assertEqual((main['host'], main['port'], log['port']), ('remote.example',4054,4054))

    def server(self, version='WI-V4.0.4.3010 Firebird 4.0', arch='Firebird/x86/Windows NT'):
        service=MagicMock();service.getServerVersion.return_value=version;service.getArchitecture.return_value=arch
        return service

    def test_exact_version_and_x86_required_without_database_attach(self):
        for version, arch, accepted in (
            ('WI-V4.0.4.3010 Firebird 4.0','Firebird/x86/Windows NT',True),
            ('WI-V4.0.4.3010 Firebird 4.0','Firebird/Windows/Intel/i386',True),
            ('WI-V5.0.2.1613 Firebird 5.0','Firebird/x86/Windows NT',False),
            ('WI-V4.0.4.3011 Firebird 4.0','Firebird/x86/Windows NT',False),
            ('WI-V4.0.4.3010 Firebird 4.0','Firebird/AMD64/Windows NT',False)):
            with self.subTest(version=version,arch=arch), patch.object(runtime.services,'connect',return_value=self.server(version,arch)), \
                    patch.object(runtime.firebirdsql,'connect') as attach:
                if accepted:self.assertIn('3010',runtime.check_server({'host':'fixture','password':'private'})['version'])
                else:
                    with self.assertRaises(runtime.FirebirdRuntimeError):runtime.check_server({'host':'fixture','password':'private'})
                attach.assert_not_called()

    def test_cleanup_failures_are_independent_and_never_expose_private_details(self):
        service=self.server();service.close.side_effect=RuntimeError('private-service-close')
        with patch.object(runtime.services,'connect',return_value=service):
            self.assertIn('3010',runtime.check_server({})['version'])
        connection=MagicMock();cursor=connection.cursor.return_value
        cursor.fetchone.return_value=(13,1)
        connection.rollback.side_effect=RuntimeError('private-rollback')
        cursor.close.side_effect=RuntimeError('private-cursor-close')
        connection.close.side_effect=RuntimeError('private-connection-close')
        with patch.object(runtime,'check_server',return_value={}),patch.object(runtime.firebirdsql,'connect',return_value=connection):
            with self.assertRaises(runtime.FirebirdRuntimeError) as error:runtime.check_database({})
        self.assertIn('ODS 13.0',str(error.exception));self.assertNotIn('private',str(error.exception))
        cursor.close.assert_called_once();connection.close.assert_called_once()

    def test_ods130_accepted_and_131_rejected_with_readonly_transaction(self):
        for ods in ((13,0),(13,1)):
            connection=MagicMock();connection.cursor.return_value.fetchone.return_value=ods
            with self.subTest(ods=ods), patch.object(runtime,'check_server',return_value={'version':'4.0.4.3010'}), \
                    patch.object(runtime.firebirdsql,'connect',return_value=connection) as attach:
                if ods==(13,0):self.assertEqual(runtime.check_database({'database':'fixture'})['ods'],[13,0])
                else:
                    with self.assertRaises(runtime.FirebirdRuntimeError):runtime.check_database({'database':'fixture'})
                self.assertEqual(attach.call_args.kwargs['isolation_level'],runtime.ISOLATION_LEVEL_READ_COMMITED_RO)
                connection.commit.assert_not_called();connection.rollback.assert_called_once()

    def test_private_connection_error_never_reaches_cli_message(self):
        with patch.object(runtime.services,'connect',side_effect=RuntimeError('secret-private-password')):
            with self.assertRaises(runtime.FirebirdRuntimeError) as error:runtime.check_server({})
        self.assertNotIn('secret-private-password',str(error.exception))

    def test_bootstrap_only_fresh_marker_password_in_stdin_and_never_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder);marker=home/'.cortae-init-pending.json'
            marker.write_text(json.dumps({'owner':'Cortae','version':'4.0.4.3010','phase':'fresh'}))
            with patch.object(runtime,'settings',return_value=({'user':'SYSDBA','password':"private'quote"},{})), \
                    patch.object(runtime.subprocess,'run',return_value=MagicMock(returncode=0)) as process:
                runtime.initialize_home(home)
                self.assertNotIn('private',str(process.call_args.args))
                self.assertIn("PASSWORD 'private''quote'",process.call_args.kwargs['input'])
                self.assertTrue(process.call_args.kwargs['capture_output'])
            self.assertFalse(marker.exists());self.assertTrue((home/'.cortae-initialized').exists())

    def test_existing_or_interrupted_installation_never_resets_password(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(runtime.subprocess,'run') as process:
            home=Path(folder)
            with self.assertRaises(runtime.FirebirdRuntimeError):runtime.initialize_home(home)
            (home/'.cortae-init-pending.json').write_text(json.dumps({'owner':'Cortae','version':'4.0.4.3010','phase':'initializing'}))
            with self.assertRaises(runtime.FirebirdRuntimeError):runtime.initialize_home(home)
            process.assert_not_called()


@unittest.skipUnless(shutil.which('powershell.exe'),'Windows PowerShell required')
class FirebirdLauncherChecks(unittest.TestCase):
    def run_script(self, code):
        root=Path(__file__).resolve().parents[2]
        helper=str(root/'Firebird-Cortae.ps1').replace("'","''")
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-Command',
            "$ErrorActionPreference='Stop'; . '"+helper+"'; "+code],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_remote_or_explicit3050_never_autostarts_or_reads_runtime(self):
        self.run_script("$env:DB_HOST='remote.example';$env:DB_PORT='3054';$env:LOG_DB_HOST='remote.example';$env:LOG_DB_PORT='3054'; "
            "function Assert-CortaeFirebirdFiles {throw 'Must not access runtime'}; Start-CortaeFirebird 'C:\\fixture'; "
            "$env:DB_HOST='localhost';$env:DB_PORT='3050';$env:LOG_DB_HOST='localhost';$env:LOG_DB_PORT='3050'; Start-CortaeFirebird 'C:\\fixture'")

    def test_stop_preserves_reused_pid_or_wrong_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            project=Path(folder);(project/'.runtime').mkdir();home=project/'engine';home.mkdir()
            state={'Pid':12345,'Exe':str(home/'firebird.exe'),'Home':str(home),'ProjectRoot':str(project),'Started':'2026-10-19T00:00:00Z'}
            statepath=project/'.runtime'/'firebird-process.json';statepath.write_text(json.dumps(state))
            project_ps=str(project).replace("'","''");home_ps=str(home).replace("'","''")
            self.run_script("$env:CORTAE_FIREBIRD_HOME='"+home_ps+"'; "
                "function Get-Process { @{StartTime=[DateTime]'2026-10-19T00:00:00Z'} }; "
                "function Get-CimInstance { @{ExecutablePath='C:\\foreign\\firebird.exe'} }; "
                "function Stop-Process { throw 'Foreign process must survive' }; Stop-CortaeFirebird '"+project_ps+"'")
            self.assertTrue(statepath.exists())

    def test_local_reuse_does_not_collide_with_powershell_home_or_claim_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root=str(Path(folder)).replace("'","''")
            self.run_script("$env:DB_HOST='localhost';$env:LOG_DB_HOST='localhost';$env:DB_PORT='3054';$env:LOG_DB_PORT='3054'; "
                "$env:CORTAE_FIREBIRD_HOME='"+root+"'; "
                "function Assert-CortaeFirebirdFiles { return 'C:\\fixture\\firebird.exe' }; "
                "function Assert-CortaeFirebirdBinding {}; function Get-NetTCPConnection { @{OwningProcess=42} }; "
                "function Get-CimInstance { @{ExecutablePath='C:\\fixture\\firebird.exe'} }; "
                "function Start-Process { throw 'Existing runtime must not restart' }; Start-CortaeFirebird '"+root+"'")
            self.assertFalse((Path(folder)/'.runtime'/'firebird-process.json').exists())

    def test_ownership_write_failure_stops_only_just_started_process(self):
        with tempfile.TemporaryDirectory() as folder:
            root=str(Path(folder)).replace("'","''")
            self.run_script("$env:DB_HOST='localhost';$env:LOG_DB_HOST='localhost';$env:DB_PORT='3054';$env:LOG_DB_PORT='3054'; "
                "$env:CORTAE_FIREBIRD_HOME='"+root+"'; "
                "function Assert-CortaeFirebirdFiles { return 'C:\\fixture\\firebird.exe' }; function Assert-CortaeFirebirdBinding {}; "
                "function Get-NetTCPConnection {}; $script:stopped=$false; "
                "$script:created=@{Id=42;StartTime=[DateTime]'2026-10-19T00:00:00Z';HasExited=$false}; "
                "function Start-Process {$script:created}; function Set-Content {throw 'Synthetic ownership failure'}; "
                "function Get-Process {$script:created}; function Get-CimInstance {@{ExecutablePath='C:\\fixture\\firebird.exe'}}; "
                "function Stop-Process {param($Id);if ($Id -ne 42) {throw 'Wrong PID'};$script:stopped=$true}; "
                "$rejected=$false;try {Start-CortaeFirebird '"+root+"'} catch {$rejected=$true}; "
                "if (-not $rejected -or -not $script:stopped) {throw 'Unregistered child survived'}")


if __name__=='__main__':unittest.main()

"""Focused WAHA contract/security tests. Never contacts WhatsApp or a WAHA server."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

import requests
import configurar_whatsapp as setup
from waha_client import WahaClient, WahaError, MAX_RESPONSE_BYTES, PNG_SIGNATURE

SETTINGS = {'WAHA_ENABLED':True,'WAHA_BASE_URL':'http://127.0.0.1:3000',
    'WAHA_API_KEY':'synthetic-private-key','WAHA_SESSION':'default','WAHA_TIMEOUT':20}


class WahaClientTests(unittest.TestCase):
    def response(self, data=None, *, status=200, raw=None, content_type='application/json'):
        response = MagicMock()
        response.status_code = status
        response.headers = {'Content-Type':content_type}
        response.iter_content.return_value = [raw if raw is not None else json.dumps(data or {}).encode()]
        return response

    def test_disabled_methods_do_not_create_transport_or_contact_network(self):
        with patch('waha_client.requests.Session') as factory:
            client = WahaClient({})
            for method in (client.status,client.create_session,client.start_session,client.stop_session,client.qr_png):
                with self.assertRaisesRegex(WahaError,'desativado'):
                    method()
            with self.assertRaises(WahaError):client.send_text('5511999999999','QA')
            factory.assert_not_called()

    def test_configuration_rejects_credentials_url_remote_http_and_injection(self):
        for base in ('http://example.invalid','https://user:pass@example.invalid','https://example.invalid/api',
                     'https://example.invalid?key=secret','https://example.invalid#token','file:///tmp/x',
                     'http://127.0.0.1:99999','https://example.invalid\n','//example.invalid',None):
            with self.subTest(base=base),self.assertRaises(WahaError):WahaClient(SETTINGS|{'WAHA_BASE_URL':base})
        for session in ('../default','default/api','default?x=y','',None):
            with self.assertRaises(WahaError):WahaClient(SETTINGS|{'WAHA_SESSION':session})

    def test_configuration_rejects_missing_hash_or_invalid_header_key_and_timeout(self):
        for key in ('','x\r\nheader: value','sha512:abc',None):
            with self.assertRaises(WahaError):WahaClient(SETTINGS|{'WAHA_API_KEY':key})
        for timeout in (0,121,'NaN','Infinity',True,None):
            with self.assertRaises(WahaError):WahaClient(SETTINGS|{'WAHA_TIMEOUT':timeout})
        for base in ('http://localhost:3000','http://[::1]:3000','https://waha.example.invalid'):
            WahaClient(SETTINGS|{'WAHA_BASE_URL':base})

    def test_status_sanitizes_private_provider_fields_and_closes_response(self):
        response = self.response({'name':'default','status':'WORKING','me':{'id':'private-number'},'config':{'secret':'private'}})
        with patch('waha_client.requests.Session') as factory:
            factory.return_value.request.return_value=response
            with WahaClient(SETTINGS) as client:
                self.assertEqual(client.status(),{'name':'default','status':'WORKING','connected':True})
            transport=factory.return_value
            self.assertFalse(transport.trust_env)
            args,kwargs=transport.request.call_args
            self.assertEqual(args,('GET','http://127.0.0.1:3000/api/sessions/default'))
            self.assertFalse(kwargs['allow_redirects']);self.assertTrue(kwargs['stream'])
            self.assertEqual(kwargs['timeout'],(5,20))
            self.assertEqual(kwargs['headers']['X-Api-Key'],SETTINGS['WAHA_API_KEY'])
            response.close.assert_called_once();transport.close.assert_called_once()

    def test_invalid_status_cannot_claim_connected(self):
        for data in ({'name':'other','status':'WORKING'},{'name':'default','status':'secret\nleak'},[]):
            with patch('waha_client.requests.Session') as factory:
                factory.return_value.request.return_value=self.response(raw=json.dumps(data).encode())
                with WahaClient(SETTINGS) as client,self.assertRaises(WahaError):client.status()

    def test_session_administration_uses_documented_routes_without_send(self):
        with patch('waha_client.requests.Session') as factory:
            transport=factory.return_value;transport.request.return_value=self.response()
            with WahaClient(SETTINGS) as client:
                client.create_session();client.start_session();client.stop_session()
            calls=transport.request.call_args_list
            self.assertEqual([call.args[1] for call in calls],[
                'http://127.0.0.1:3000/api/sessions','http://127.0.0.1:3000/api/sessions/default/start',
                'http://127.0.0.1:3000/api/sessions/default/stop'])
            self.assertEqual(calls[0].kwargs['json'],{'name':'default','start':False})

    def test_redirect_and_error_bodies_never_expose_secret_or_retry(self):
        for code in (301,401,403,409,500):
            with patch('waha_client.requests.Session') as factory:
                response=self.response({'error':'synthetic-private-key leaked'},status=code)
                factory.return_value.request.return_value=response
                with WahaClient(SETTINGS) as client,self.assertRaises(WahaError) as caught:client.status()
                self.assertNotIn('synthetic-private-key',str(caught.exception))
                factory.return_value.request.assert_called_once();response.close.assert_called_once()

    def test_response_bound_and_invalid_json_are_rejected(self):
        for raw in (b'x'*(MAX_RESPONSE_BYTES+1),b'not-json',b'\xff'):
            with patch('waha_client.requests.Session') as factory:
                response=self.response(raw=raw);factory.return_value.request.return_value=response
                with WahaClient(SETTINGS) as client,self.assertRaises(WahaError):client.status()
                response.close.assert_called_once()

    def test_qr_requires_png_header_and_signature(self):
        for raw,mime,valid in ((PNG_SIGNATURE+b'qa','image/png',True),(b'html','image/png',False),
                               (PNG_SIGNATURE,'text/html',False)):
            with patch('waha_client.requests.Session') as factory:
                factory.return_value.request.return_value=self.response(raw=raw,content_type=mime)
                with WahaClient(SETTINGS) as client:
                    if valid:self.assertEqual(client.qr_png(),raw)
                    else:
                        with self.assertRaises(WahaError):client.qr_png()
                self.assertEqual(factory.return_value.request.call_args.args[1],'http://127.0.0.1:3000/api/default/auth/qr')

    def test_send_text_validates_destination_and_body_before_network(self):
        with patch('waha_client.requests.Session') as factory:
            client=WahaClient(SETTINGS)
            for destination,text in (('0','QA'),('5511@g.us','QA'),('5511999999999',''),
                                      ('5511999999999','x'*4097),('5511999999999',None),('55 11','QA')):
                with self.assertRaises(WahaError):client.send_text(destination,text)
            factory.assert_not_called()

    def test_explicit_send_contract_and_uncertain_delivery_never_retries(self):
        with patch('waha_client.requests.Session') as factory:
            transport=factory.return_value;transport.request.return_value=self.response({'id':'mock-only'})
            with WahaClient(SETTINGS) as client:
                client.send_text('+5511999999999','Teste local sem envio real')
                self.assertEqual(transport.request.call_args.kwargs['json'],{'session':'default',
                    'chatId':'5511999999999@c.us','text':'Teste local sem envio real'})
                transport.request.reset_mock()
                transport.request.side_effect=requests.Timeout('private-key and recipient must not escape')
                with self.assertRaisesRegex(WahaError,'pode ter sido aceito') as caught:
                    client.send_text('5511999999999','QA')
                self.assertNotIn('private-key',str(caught.exception));transport.request.assert_called_once()


class WahaSetupTests(unittest.TestCase):
    def test_import_and_help_do_not_load_app_database_or_config(self):
        code="import configurar_whatsapp,sys; assert 'application' not in sys.modules; assert 'main' not in sys.modules; assert 'config' not in sys.modules; configurar_whatsapp.main(['--help'])"
        result=subprocess.run([sys.executable,'-c',code],cwd=Path(setup.__file__).parent,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('enviar-texto',result.stdout)

    def test_cli_status_has_no_send_or_private_fields(self):
        with patch.object(setup,'load_settings',return_value=SETTINGS),patch.object(setup,'WahaClient') as factory,contextlib.redirect_stdout(io.StringIO()) as output:
            client=factory.return_value.__enter__.return_value
            client.status.return_value={'name':'default','status':'STOPPED','connected':False}
            self.assertEqual(setup.main(['status']),0)
            client.send_text.assert_not_called();client.qr_png.assert_not_called()
            self.assertEqual(json.loads(output.getvalue())['connected'],False)

    def test_qr_destination_is_external_and_never_overwrites(self):
        with self.assertRaises(WahaError):setup.save_qr(setup.PROJECT/'qr.png',PNG_SIGNATURE)
        with TemporaryDirectory() as directory:
            path=Path(directory)/'qr.png'
            self.assertEqual(setup.save_qr(path,PNG_SIGNATURE),path)
            self.assertEqual(path.read_bytes(),PNG_SIGNATURE)
            with self.assertRaises(WahaError):setup.save_qr(path,b'overwrite')
            self.assertEqual(path.read_bytes(),PNG_SIGNATURE)

    def test_only_explicit_send_command_calls_send_text(self):
        with patch.object(setup,'load_settings',return_value=SETTINGS),patch.object(setup,'WahaClient') as factory,contextlib.redirect_stdout(io.StringIO()):
            client=factory.return_value.__enter__.return_value
            self.assertEqual(setup.main(['enviar-texto','--destino','5511999999999','--texto','mock only']),0)
            client.send_text.assert_called_once_with('5511999999999','mock only')


if __name__=='__main__':
    unittest.main()

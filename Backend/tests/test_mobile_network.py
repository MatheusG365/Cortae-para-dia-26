"""Cross-origin mobile web requests retain the existing authentication rules."""
import os
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
import runpy
from pathlib import Path
from unittest.mock import patch
import main


class MobileNetworkTests(unittest.TestCase):
    def test_server_uses_configured_listener_and_port_without_starting_it(self):
        for host in ('0.0.0.0', '127.0.0.1', '::'):
            with self.subTest(host=host), patch.dict(main.app.config, {
                    'API_HOST': host, 'PORT': 5432,
                    'DEBUG': False,
            }), patch('application.app.run') as serve:
                runpy.run_path(str(Path(main.__file__)), run_name='__main__')
                serve.assert_called_once_with(host=host, port=5432,
                                              debug=False, use_reloader=False)

    def test_preflight_allows_native_client_header_from_current_lan_origin(self):
        response = main.app.test_client().options('/login', headers={
            'Origin': 'http://192.168.42.18:8081',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'content-type,x-cortae-client',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'],
                         'http://192.168.42.18:8081')
        allowed = response.headers['Access-Control-Allow-Headers'].lower()
        self.assertIn('content-type', allowed)
        self.assertIn('x-cortae-client', allowed)

    def test_new_network_origin_does_not_authenticate_protected_requests(self):
        response = main.app.test_client().get('/barbearia/perfil', headers={
            'Origin': 'http://192.168.42.18:8081',
            'X-Cortae-Client': 'mobile',
        })
        self.assertEqual(response.status_code, 401)

    def test_preflight_does_not_allow_arbitrary_extra_headers(self):
        response = main.app.test_client().options('/login', headers={
            'Origin': 'http://192.168.42.18:8081',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'x-untrusted-admin',
        })
        self.assertNotIn('x-untrusted-admin',
                         response.headers.get('Access-Control-Allow-Headers', '').lower())

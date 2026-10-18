"""Visagismo image transaction/privacy regressions; no live Drive, AI or Firebird."""
import os
import base64
from contextlib import ExitStack
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from flask import Response
import main
import visagismo
from tests.test_visagismo import PNG, CHARACTERISTICS
from visagismo_ia import ErroVisagismoIA


class VisagismoDriveStorage(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.context = main.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.client = main.app.test_client()
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value
        self.user = {'id_usuario': 7, 'tipo': 1}
        self.stack.enter_context(patch.object(visagismo, 'obter_usuario_logado', side_effect=lambda: self.user))
        self.stack.enter_context(patch.object(visagismo, 'conectar_banco', return_value=self.connection))
        self.stack.enter_context(patch.object(visagismo, 'find_image', return_value=None))
        self.stack.enter_context(patch.object(visagismo, 'capturar_registro', return_value={}))
        self.stack.enter_context(patch.object(visagismo, 'registrar_registro'))
        self.stack.enter_context(patch.object(visagismo, 'carregar_servicos', return_value=[{
            'id_servico': 100, 'nome': 'Pintar cabelo', 'duracao': 30, 'genero': 'masculino'}]))
        self.batch = MagicMock()
        self.batch.save.return_value = SimpleNamespace(filename='a' * 32 + '.webp', content=PNG)
        self.stack.enter_context(patch.object(visagismo, 'ImageBatch', return_value=self.batch))
        self.read = self.stack.enter_context(patch.object(visagismo, 'read_image', return_value=PNG))
        self.serve = self.stack.enter_context(patch.object(visagismo, 'serve_image', return_value=Response(PNG, mimetype='image/webp')))
        self.provider = MagicMock()
        self.provider.images.edit.return_value = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG).decode())])
        self.stack.enter_context(patch.object(visagismo, 'OpenAI', return_value=self.provider))
        self.stack.enter_context(patch.object(visagismo, 'motivo_sem_ia', return_value=None))

    def upload_photo(self, route='/visagismo/salvar-foto'):
        return self.client.post(route, data={'id_barbearia': '8', 'ids_servicos': '100',
            'imagem': (io.BytesIO(PNG), 'photo.png')}, content_type='multipart/form-data')

    def assert_no_image_fetch(self):
        self.read.assert_not_called()
        self.serve.assert_not_called()

    def test_anonymous_private_image_denied_before_database_or_drive(self):
        self.user = None
        response = self.client.get('/uploads/visagismo/fotos/' + 'a' * 32 + '.webp')
        self.assertEqual(response.status_code, 403)
        self.connection.cursor.assert_not_called()
        self.assert_no_image_fetch()

    def test_old_filename_prefix_never_grants_access_without_session(self):
        self.cursor.fetchone.return_value = None
        response = self.client.get('/uploads/visagismo/fotos/cliente_7_guessed.png')
        self.assertEqual(response.status_code, 403)
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('ID_USUARIO=?', sql)
        self.assertEqual(params, ('cliente_7_guessed.png', 7))
        self.assert_no_image_fetch()

    def test_client_uuid_image_requires_actual_ownership_then_fetches_once(self):
        self.cursor.fetchone.return_value = (91,)
        filename = 'a' * 32 + '.webp'
        response = self.client.get('/uploads/visagismo/resultados/' + filename)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.cursor.execute.call_args.args[1], (filename, 7))
        self.serve.assert_called_once()
        self.assertEqual(self.serve.call_args.args, ('visagismo/resultados', filename))

    def test_other_salon_private_image_denied_before_drive(self):
        self.user = {'id_usuario': 8, 'tipo': 2}
        self.cursor.fetchone.return_value = None
        response = self.client.get('/uploads/visagismo/fotos/private.webp')
        self.assertEqual(response.status_code, 403)
        self.assertIn('ID_BARBEARIA=?', self.cursor.execute.call_args.args[0])
        self.assertEqual(self.cursor.execute.call_args.args[1], ('private.webp', 8))
        self.assert_no_image_fetch()

    def test_responsible_barber_uses_booking_and_salon_relation(self):
        self.user = {'id_usuario': 10, 'tipo': 3}
        self.cursor.fetchone.return_value = (99,)
        with patch.object(visagismo, 'funcionario_logado', return_value=(3, 8)):
            response = self.client.get('/uploads/visagismo/resultados/private.webp')
        self.assertEqual(response.status_code, 200)
        sql, params = self.cursor.execute.call_args.args
        self.assertIn('A.ID_FUNCIONARIO=? AND A.ID_BARBEARIA=?', sql)
        self.assertEqual(params, (3, 8, 'private.webp'))
        self.serve.assert_called_once()

    def test_unassigned_barber_never_fetches_image(self):
        self.user = {'id_usuario': 10, 'tipo': 3}
        with patch.object(visagismo, 'funcionario_logado', return_value=None):
            response = self.client.get('/uploads/visagismo/fotos/private.webp')
        self.assertEqual(response.status_code, 403)
        self.assert_no_image_fetch()

    def test_public_catalog_remains_application_proxy_not_public_drive_url(self):
        self.user = None
        response = self.client.get('/uploads/visagismo/cortes/example.webp')
        self.assertEqual(response.status_code, 200)
        self.connection.cursor.assert_not_called()
        self.serve.assert_called_once()

    def test_invalid_nested_filename_is_rejected_before_provider(self):
        response = self.client.get('/uploads/visagismo/fotos/nested/private.webp')
        self.assertEqual(response.status_code, 404)
        self.assert_no_image_fetch()

    def test_manual_upload_commits_image_only_after_session_commit(self):
        calls = []
        self.cursor.fetchone.return_value = (91,)
        self.connection.commit.side_effect = lambda: calls.append('database')
        self.batch.commit.side_effect = lambda: calls.append('images')
        response = self.upload_photo()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(calls, ['database', 'images'])
        self.assertIn('a' * 32 + '.webp', response.json['foto_url'])
        self.batch.abort.assert_not_called()
        self.assertEqual(self.batch.save.call_args.args[1], 'visagismo/fotos')
        self.assertEqual(self.batch.save.call_args.kwargs['owner_id'], 7)

    def test_manual_upload_db_failure_aborts_only_new_image(self):
        self.cursor.fetchone.return_value = (91,)
        self.connection.commit.side_effect = RuntimeError('database unavailable')
        response = self.upload_photo()
        self.assertEqual(response.status_code, 500)
        self.connection.rollback.assert_called_once()
        self.batch.abort.assert_called_once()
        self.batch.commit.assert_not_called()

    def prepare_analysis(self):
        self.cursor.fetchall.return_value = [(11, 'Corte curto', 'Descrição', 'masculino', 'ref.webp', 1, 'masculino')]
        self.cursor.fetchone.return_value = (91,)

    def test_analysis_uses_new_compressed_bytes_without_refetching_drive(self):
        self.prepare_analysis()
        analysis = {'caracteristicas': CHARACTERISTICS, 'recomendacoes': [{'id_corte': 11, 'motivo': 'Rosto oval',
            'compativel_com_cabelo_existente': True}]}
        with patch.object(visagismo, 'analisar_com_ia', return_value=analysis) as analyze:
            response = self.upload_photo('/visagismo/analisar')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(analyze.call_args.args[0], PNG)
        self.read.assert_not_called()
        self.batch.commit.assert_called_once()

    def test_analysis_ai_failure_rolls_back_and_cleans_new_asset(self):
        self.prepare_analysis()
        with patch.object(visagismo, 'analisar_com_ia', side_effect=ErroVisagismoIA('Indisponível', 502)):
            response = self.upload_photo('/visagismo/analisar')
        self.assertEqual(response.status_code, 502)
        self.assertTrue(self.connection.rollback.called)
        self.batch.abort.assert_called_once()
        self.batch.commit.assert_not_called()

    def test_simulation_db_failure_aborts_new_result_but_never_removes_old_photo(self):
        self.cursor.fetchone.return_value = ('original.webp', json.dumps({'apenas_cor': True}), 8, '[100]')
        self.connection.commit.side_effect = RuntimeError('database unavailable')
        response = self.client.post('/visagismo/91/simular', json={'cor': '#112233'})
        self.assertEqual(response.status_code, 500)
        self.read.assert_called_once()
        self.assertEqual(self.read.call_args.args, ('visagismo/fotos', 'original.webp'))
        self.batch.save.assert_called_once_with(PNG, 'visagismo/resultados', owner_id=7)
        self.batch.abort.assert_called_once()
        self.batch.commit.assert_not_called()
        self.connection.rollback.assert_called_once()

    def test_simulation_cross_client_session_denied_without_drive_or_ai(self):
        self.cursor.fetchone.return_value = None
        response = self.client.post('/visagismo/91/simular', json={'cor': '#112233'})
        self.assertEqual(response.status_code, 404)
        self.assertIn('ID_USUARIO=?', self.cursor.execute.call_args.args[0])
        self.assert_no_image_fetch()
        self.provider.images.edit.assert_not_called()
        self.batch.save.assert_not_called()

    def test_edit_failure_keeps_previous_reference_and_aborts_replacement(self):
        self.user = {'id_usuario': 8, 'tipo': 2}
        self.cursor.fetchone.side_effect = [None, ('old.webp',)]
        self.connection.commit.side_effect = RuntimeError('database unavailable')
        response = self.client.put('/visagismo/cortes/11', data={
            'nome': 'Novo corte', 'categoria': 'masculino',
            'imagem': (io.BytesIO(PNG), 'new.png')}, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 500)
        self.batch.abort.assert_called_once()
        self.batch.commit.assert_not_called()
        self.batch.save.assert_called_once()
        self.assertEqual(self.batch.save.call_args.args[1], 'visagismo/cortes')


if __name__ == '__main__':
    unittest.main()

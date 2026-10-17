"""Profile/salon image routes preserve authorization and the business transaction."""
import io
import os
os.environ['STARTUP_MIGRATIONS'] = 'false'
os.environ['WAITLIST_WORKER'] = 'false'
import unittest
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import main
import barbearia
import editar_usuario
import funcoes
import image_storage
from marketplace_perfil import business_images


class ProfileDriveImages(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()
        self.con = MagicMock()
        self.cur = self.con.cursor.return_value
        self.cur.fetchone.return_value = (10, 'Cliente QA', 'qa@example.invalid', '11999999999', 'hash', 1, 'outro')

    def edit(self, *, error=None, fail_commit=False):
        batch = MagicMock()
        batch.save.return_value = SimpleNamespace(url='/uploads/perfil/'+'a'*32+'.webp')
        batch.save.side_effect = error
        if fail_commit:
            self.con.commit.side_effect = RuntimeError('simulated DB failure')
        with ExitStack() as stack:
            stack.enter_context(patch.object(editar_usuario, 'decodificar_token', return_value={'id_usuario': 10, 'tipo': 1}))
            stack.enter_context(patch.object(editar_usuario, 'conectar_banco', return_value=self.con))
            stack.enter_context(patch.object(editar_usuario, 'buscar_foto_perfil', return_value='/fotos-perfil/10.jpg'))
            stack.enter_context(patch.object(editar_usuario, 'ImageBatch', return_value=batch))
            stack.enter_context(patch.object(editar_usuario, 'capturar_registro', return_value={}))
            stack.enter_context(patch.object(editar_usuario, 'registrar_registro'))
            stack.enter_context(patch.object(editar_usuario, 'registrar_log'))
            response = self.client.put('/editar-usuario/10', data={'foto': (io.BytesIO(b'picture'), 'photo.png')})
        return response, batch

    def test_profile_upload_uses_owner_slot_and_commits_after_database(self):
        response, batch = self.edit()
        self.assertEqual(response.status_code, 200, response.json)
        args, kwargs = batch.save.call_args
        self.assertEqual(args[1], 'perfil')
        self.assertEqual(kwargs, {'owner_id': 10, 'slot': 'profile'})
        self.con.commit.assert_called_once()
        batch.commit.assert_called_once()
        batch.abort.assert_called_once()  # A committed batch abort is deliberately a no-op.

    def test_rejected_image_rolls_back_and_never_commits_new_reference(self):
        response, batch = self.edit(error=ValueError('Imagem inválida.'))
        self.assertEqual(response.status_code, 400)
        self.assertIn('Imagem inválida', response.json['mensagem']['informacao'])
        self.con.rollback.assert_called_once()
        self.con.commit.assert_not_called()
        batch.commit.assert_not_called()
        batch.abort.assert_called_once()

    def test_unconfigured_drive_has_clear_503_without_provider_secrets(self):
        response, batch = self.edit(error=image_storage.ImageStorageError('Armazenamento de imagens não configurado.', 503))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('detalhes', response.json)
        batch.commit.assert_not_called()
        self.con.rollback.assert_called_once()

    def test_database_failure_cleans_new_upload_and_preserves_previous_slot(self):
        response, batch = self.edit(fail_commit=True)
        self.assertEqual(response.status_code, 500)
        batch.commit.assert_not_called()
        self.con.rollback.assert_called_once()
        batch.abort.assert_called_once()

    def test_other_client_cannot_upload_or_delete_another_profile(self):
        with patch.object(editar_usuario, 'decodificar_token', return_value={'id_usuario': 11, 'tipo': 1}), \
             patch.object(editar_usuario, 'conectar_banco') as connect:
            self.assertEqual(self.client.put('/editar-usuario/10', data={}).status_code, 403)
            self.assertEqual(self.client.delete('/excluir-foto-perfil/10').status_code, 403)
        connect.assert_not_called()

    def test_profile_delete_updates_slot_transaction_before_storage_cleanup(self):
        batch = MagicMock()
        with patch.object(editar_usuario, 'decodificar_token', return_value={'id_usuario': 10, 'tipo': 1}), \
             patch.object(editar_usuario, 'conectar_banco', return_value=self.con), \
             patch.object(editar_usuario, 'buscar_foto_perfil', return_value='/uploads/perfil/a.webp'), \
             patch.object(editar_usuario, 'ImageBatch', return_value=batch), \
             patch.object(editar_usuario, 'registrar_log'):
            response = self.client.delete('/excluir-foto-perfil/10')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json['usuario']['foto_perfil'])
        batch.delete.assert_called_once_with('perfil', 10, 'profile')
        self.con.commit.assert_called_once()
        batch.commit.assert_called_once()

    def test_failed_profile_delete_rolls_back_before_batch_abort(self):
        batch = MagicMock()
        events = []
        self.con.commit.side_effect = RuntimeError('commit failed')
        self.con.rollback.side_effect = lambda: events.append('rollback')
        batch.abort.side_effect = lambda: events.append('abort')
        with patch.object(editar_usuario, 'decodificar_token', return_value={'id_usuario': 10, 'tipo': 1}), \
             patch.object(editar_usuario, 'conectar_banco', return_value=self.con), \
             patch.object(editar_usuario, 'buscar_foto_perfil', return_value='/uploads/perfil/a.webp'), \
             patch.object(editar_usuario, 'ImageBatch', return_value=batch):
            response = self.client.delete('/excluir-foto-perfil/10')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(events, ['rollback', 'abort'])
        batch.commit.assert_not_called()

    def test_profile_database_reference_and_tombstone_take_precedence_over_legacy(self):
        with TemporaryDirectory() as folder, main.app.app_context(), \
             patch.dict(main.app.config, {'PERFIL_FOLDER': folder, 'IMAGE_STORAGE_PROVIDER': 'local'}):
            (Path(folder)/'10.jpg').write_bytes(b'legacy')
            cur = object()
            with patch.object(image_storage, 'slot_state', return_value=(True, SimpleNamespace(url='/uploads/perfil/new.webp'))) as state:
                self.assertEqual(funcoes.buscar_foto_perfil(10, cursor=cur), '/uploads/perfil/new.webp')
                state.assert_called_once_with('perfil', 10, 'profile', cursor=cur)
            with patch.object(image_storage, 'slot_state', return_value=(True, None)):
                self.assertIsNone(funcoes.buscar_foto_perfil(10, cursor=cur))
            with patch.object(image_storage, 'slot_state', return_value=(False, None)):
                self.assertEqual(funcoes.buscar_foto_perfil(10, cursor=cur), '/fotos-perfil/10.jpg')
            self.assertTrue((Path(folder)/'10.jpg').is_file())

    def test_both_old_profile_urls_resolve_current_slot_without_exposing_drive_id(self):
        image = SimpleNamespace(filename='a'*32+'.webp')
        for prefix in ('/fotos-perfil/', '/uploads/perfil/'):
            with self.subTest(prefix=prefix), patch.object(editar_usuario, 'slot_state', return_value=(True, image)), \
                 patch.object(editar_usuario, 'serve_image', return_value=('webp', 200)) as serve:
                response = self.client.get(prefix+'10.jpg')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(serve.call_args.args[:2], ('perfil', image.filename))
        with patch.object(editar_usuario, 'slot_state', return_value=(True, None)), \
             patch.object(editar_usuario, 'serve_image') as serve:
            self.assertEqual(self.client.get('/uploads/perfil/10.jpg').status_code, 404)
            serve.assert_not_called()


class SalonDriveImages(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()

    def test_logo_gallery_database_reference_is_scoped_and_overrides_old_files(self):
        with TemporaryDirectory() as folder:
            old = Path(folder)/'barbearia'
            old.mkdir()
            (old/'10.jpg').write_bytes(b'old')
            (old/'10_2.jpg').write_bytes(b'old')
            (old/'11.jpg').write_bytes(b'other')
            cursor = object()
            calls = []
            def state(area, owner, slot, cursor=None):
                calls.append((area, owner, slot, cursor))
                return True, SimpleNamespace(url='/uploads/barbearia/logo.webp') if slot == 'logo' else None
            with patch.object(image_storage, 'slot_state', side_effect=state):
                self.assertEqual(business_images(folder, 10, cursor=cursor), ('/uploads/barbearia/logo.webp', []))
            self.assertEqual(len(calls), 6)
            self.assertTrue(all(area == 'barbearia' and owner == 10 and cur is cursor for area, owner, _, cur in calls))

    def test_slot_names_are_derived_from_authenticated_business_identity(self):
        batch = MagicMock()
        batch.save.return_value.url = '/uploads/barbearia/new.webp'
        upload = SimpleNamespace(filename='logo.png')
        self.assertEqual(barbearia.salvar_imagem(upload, '10', batch), '/uploads/barbearia/new.webp')
        batch.save.assert_called_once_with(upload, 'barbearia', owner_id=10, slot='logo')
        batch.reset_mock()
        barbearia.salvar_imagem(upload, '10_5', batch)
        batch.save.assert_called_once_with(upload, 'barbearia', owner_id=10, slot='gallery5')
        with self.assertRaises(ValueError):
            barbearia.salvar_imagem(upload, '../11_6', batch)

    def test_old_salon_urls_resolve_owner_gallery_or_tombstone(self):
        image = SimpleNamespace(filename='b'*32+'.webp')
        with patch.object(barbearia, 'slot_state', return_value=(True, image)) as state, \
             patch.object(barbearia, 'serve_image', return_value=('webp', 200)) as serve:
            response = self.client.get('/uploads/barbearia/10_2.jpg')
        self.assertEqual(response.status_code, 200)
        state.assert_called_once_with('barbearia', 10, 'gallery2')
        self.assertEqual(serve.call_args.args[:2], ('barbearia', image.filename))
        with patch.object(barbearia, 'slot_state', return_value=(True, None)), patch.object(barbearia, 'serve_image') as serve:
            self.assertEqual(self.client.get('/uploads/barbearia/10_2.jpg').status_code, 404)
            serve.assert_not_called()

    def create(self, error=None, commit_error=False):
        con = MagicMock()
        cur = con.cursor.return_value
        cur.fetchone.side_effect = [(10,), None, (123,), (456,)]
        cur.fetchall.return_value = []
        if commit_error:
            con.commit.side_effect = RuntimeError('simulated commit failure')
        batch = MagicMock()
        batch.save.return_value.url = '/uploads/barbearia/new.webp'
        batch.save.side_effect = error
        data = {'num_funcionarios': '1', 'funcionarios[0][nome]': 'QA',
                'chave_pix': 'fake', 'arkhe_client_id': 'fake', 'arkhe_client_secret': 'fake',
                'logo': (io.BytesIO(b'picture'), 'logo.png'),
                'foto1': (io.BytesIO(b'picture'), 'gallery.png'), 'id_usuario': '11'}
        with ExitStack() as stack:
            for name, replacement in [('conectar_banco', con), ('ImageBatch', batch)]:
                stack.enter_context(patch.object(barbearia, name, return_value=replacement))
            stack.enter_context(patch.object(barbearia, 'pegar_id_barbearia_alvo', return_value=10))
            stack.enter_context(patch.object(barbearia, 'vincular_servicos_funcionario', return_value=[]))
            stack.enter_context(patch.object(barbearia, 'vincular_dias_funcionario'))
            stack.enter_context(patch.object(barbearia, 'registrar_registro'))
            stack.enter_context(patch('agenda_equipe.atualizar_acesso_funcionario', return_value=None))
            stack.enter_context(patch('agenda_equipe.enviar_convites', return_value=[]))
            response = self.client.post('/barbearia/personalizacao', data=data)
        return response, con, batch

    def test_salon_logo_and_gallery_uploads_share_transaction_and_ignore_forged_owner(self):
        response, con, batch = self.create()
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual([call.kwargs for call in batch.save.call_args_list],
                         [{'owner_id': 10, 'slot': 'logo'}, {'owner_id': 10, 'slot': 'gallery1'}])
        con.commit.assert_called_once()
        batch.commit.assert_called_once()
        batch.abort.assert_called_once()

    def test_salon_storage_failure_rolls_back_business_changes(self):
        response, con, batch = self.create(error=image_storage.ImageStorageError('Armazenamento indisponível.', 503))
        self.assertEqual(response.status_code, 503, response.json)
        con.commit.assert_not_called()
        con.rollback.assert_called_once()
        batch.commit.assert_not_called()
        batch.abort.assert_called_once()

    def test_salon_commit_failure_aborts_new_uploads_without_committing_batch(self):
        response, con, batch = self.create(commit_error=True)
        self.assertEqual(response.status_code, 500)
        con.rollback.assert_called_once()
        batch.commit.assert_not_called()
        batch.abort.assert_called_once()


if __name__ == '__main__':
    unittest.main()

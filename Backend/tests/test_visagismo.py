"""Behavioral visagismo tests: synthetic images, mocked AI, no live DB writes."""
import os
import base64
import copy
from datetime import datetime, timedelta
import io
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import zlib

import main
import database
import visagismo
import visagismo_ia as ia


def png_image():
    """A complete, synthetic RGB PNG made without optional test dependencies."""
    def chunk(kind, payload):
        return struct.pack('!I', len(payload)) + kind + payload + struct.pack('!I', zlib.crc32(kind + payload) & 0xffffffff)
    rows = b''.join(b'\0' + b'\x80\x90\xa0' * 32 for _ in range(32))
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 32, 32, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')


PNG = png_image()
CHARACTERISTICS = {
    'formato_rosto': 'oval', 'textura_cabelo': 'ondulado',
    'comprimento_cabelo': 'curto', 'densidade_cabelo': 'média',
    'linha_frontal': 'natural, visível', 'barba': 'curta, visível',
}
CATALOG = [
    {'id_corte': 11, 'nome': 'Corte curto', 'descricao': 'Laterais curtas e topo natural',
     'categoria': 'masculino', 'imagem_url': '/uploads/visagismo/cortes/ref.png', 'ativo': True, 'genero': 'masculino'},
    {'id_corte': 12, 'nome': 'Corte longo', 'descricao': 'Comprimento longo',
     'categoria': 'masculino', 'imagem_url': None, 'ativo': True, 'genero': 'masculino'},
]


class VisagismoBehavior(unittest.TestCase):
    def setUp(self):
        self.app = main.app
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.temp = tempfile.TemporaryDirectory(prefix='cortae-visagismo-tests-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        for name in ('fotos', 'cortes', 'resultados'):
            (self.folder / name).mkdir()
        self.photo = self.folder / 'fotos' / 'cliente_7.png'
        self.photo.write_bytes(PNG)
        config = patch.dict(self.app.config, {
            'IMAGE_STORAGE_PROVIDER': 'local',
            'OPENAI_API_KEY': 'test-placeholder-never-sent',
            'VISAGISMO_ANALYSIS_MODEL': 'test-analysis',
            'VISAGISMO_IMAGE_MODEL': 'gpt-image-2',
            'VISAGISMO_FOTOS_FOLDER': str(self.folder / 'fotos'),
            'VISAGISMO_CORTES_FOLDER': str(self.folder / 'cortes'),
            'VISAGISMO_RESULTADOS_FOLDER': str(self.folder / 'resultados'),
        })
        config.start()
        self.addCleanup(config.stop)
        reference_patch = patch.object(visagismo, 'find_image', return_value=None)
        reference_patch.start()
        self.addCleanup(reference_patch.stop)
        # Any accidental unmocked connection is an explicit test failure.
        block_db = patch.object(database, 'conectar_banco', side_effect=AssertionError('Live DB access forbidden by visagismo tests'))
        block_db.start()
        self.addCleanup(block_db.stop)
        # Image storage is covered independently; business tests never touch Drive.
        self.image_batch = MagicMock()
        self.image_batch.save.side_effect = lambda upload, area, **kwargs: SimpleNamespace(
            filename='a' * 32 + '.webp', content=PNG)
        image_patch = patch.object(visagismo, 'ImageBatch', return_value=self.image_batch)
        image_patch.start()
        self.addCleanup(image_patch.stop)
        def read_legacy(area, filename, legacy_folder=None, cursor=None):
            return (Path(legacy_folder) / filename).read_bytes()
        read_patch = patch.object(visagismo, 'read_image', side_effect=read_legacy)
        read_patch.start()
        self.addCleanup(read_patch.stop)
        self.client = self.app.test_client()
        self.provider = MagicMock()
        self.provider.images.edit.return_value = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(PNG).decode())])

    def stored_analysis(self, category='cabelo'):
        return {'versao_analise': 2, 'categoria': category, 'caracteristicas': copy.deepcopy(CHARACTERISTICS),
                'observacoes': 'O topo curto combina com o contorno oval visível.', 'cabelo_atual': 'Ondulado e curto',
                'recomendacoes': [{'id_corte': 11, 'nome': 'Barba curta' if category == 'barba' else 'Corte curto',
                    'motivo': 'O rosto oval e a textura ondulada favorecem o topo curto.',
                    'compativel_com_cabelo_existente': True}]}

    def raw_analysis(self):
        result = self.stored_analysis()
        result.pop('versao_analise')
        result.pop('categoria')
        result.update(status='ok', pessoa_visivel=True, rosto_visivel=True)
        return result

    def assert_analysis_error(self, value, status=502, catalog=None):
        with self.assertRaises(ia.ErroVisagismoIA) as error:
            ia.validar_analise(value, catalog or CATALOG)
        self.assertEqual(error.exception.status, status)

    def test_schema_ids_only_active_and_at_most_one(self):
        catalog = copy.deepcopy(CATALOG)
        catalog[1]['ativo'] = False
        schema = ia.esquema_analise(catalog)
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['recomendacoes']['maxItems'], 1)
        self.assertEqual(schema['properties']['recomendacoes']['items']['properties']['id_corte']['enum'], [11])
        self.assertEqual(set(schema['properties']['caracteristicas']['required']), set(CHARACTERISTICS))

    def test_valid_analysis_preserves_single_personalized_recommendation(self):
        result = ia.validar_analise(self.raw_analysis(), CATALOG)
        self.assertEqual(len(result['recomendacoes']), 1)
        self.assertEqual(result['recomendacoes'][0]['id_corte'], 11)
        self.assertEqual(result['caracteristicas'], CHARACTERISTICS)
        self.assertIn('oval', result['recomendacoes'][0]['motivo'])

    def test_analysis_photo_without_person_rejected(self):
        data = self.raw_analysis()
        data.update(status='foto_inadequada', pessoa_visivel=False, recomendacoes=[])
        self.assert_analysis_error(data, 422)

    def test_analysis_obscured_face_rejected(self):
        data = self.raw_analysis()
        data['rosto_visivel'] = False
        self.assert_analysis_error(data, 422)

    def test_analysis_no_viable_cut_rejected(self):
        data = self.raw_analysis()
        data.update(status='sem_corte_viavel', recomendacoes=[])
        self.assert_analysis_error(data, 422)

    def test_analysis_false_hair_compatibility_rejected(self):
        data = self.raw_analysis()
        data['recomendacoes'][0]['compativel_com_cabelo_existente'] = False
        self.assert_analysis_error(data, 422)

    def test_analysis_multiple_recommendations_rejected(self):
        data = self.raw_analysis()
        data['recomendacoes'].append(copy.deepcopy(data['recomendacoes'][0]))
        self.assert_analysis_error(data)

    def test_analysis_invented_id_rejected(self):
        data = self.raw_analysis()
        data['recomendacoes'][0]['id_corte'] = 999
        self.assert_analysis_error(data)

    def test_analysis_inactive_cut_rejected(self):
        catalog = copy.deepcopy(CATALOG)
        catalog[0]['ativo'] = False
        self.assert_analysis_error(self.raw_analysis(), catalog=catalog)

    def test_analysis_catalog_name_must_match_id(self):
        data = self.raw_analysis()
        data['recomendacoes'][0]['nome'] = 'Estilo inventado'
        self.assert_analysis_error(data)

    def test_analysis_boolean_or_string_id_rejected(self):
        for value in (True, '11', 11.0):
            with self.subTest(value=value):
                data = self.raw_analysis()
                data['recomendacoes'][0]['id_corte'] = value
                self.assert_analysis_error(data)

    def test_analysis_characteristics_incomplete_or_empty_rejected(self):
        for value in ({}, {**CHARACTERISTICS, 'barba': ''}, {**CHARACTERISTICS, 'raca': 'inventada'}):
            with self.subTest(value=value):
                data = self.raw_analysis()
                data['caracteristicas'] = value
                self.assert_analysis_error(data)

    def test_analysis_wrong_compatibility_type_rejected(self):
        data = self.raw_analysis()
        data['recomendacoes'][0]['compativel_com_cabelo_existente'] = 'false'
        self.assert_analysis_error(data)

    def test_analysis_short_reason_or_extra_provider_fields_rejected(self):
        data = self.raw_analysis()
        data['recomendacoes'][0]['motivo'] = 'Bonito'
        self.assert_analysis_error(data)
        data = self.raw_analysis()
        data['outro'] = 'não pertence ao contrato'
        self.assert_analysis_error(data)

    def test_image_mime_uses_bytes_not_filename(self):
        self.assertEqual(ia.mime_imagem(PNG), 'image/png')
        self.assertEqual(ia.mime_imagem(b'\xff\xd8\xff\xe0' + b'JPEG fixture'), 'image/jpeg')
        self.assertEqual(ia.mime_imagem(b'RIFF\x10\x00\x00\x00WEBPVP8 '), 'image/webp')
        with self.assertRaises(ValueError):
            ia.mime_imagem(b'not an image')

    def test_analysis_responses_requests_strict_schema_and_true_png_mime(self):
        mislabeled = self.folder / 'customer.jpg'
        mislabeled.write_bytes(PNG)
        self.provider.responses.create.return_value = SimpleNamespace(output_text=json.dumps(self.raw_analysis()))
        with patch.object(visagismo, 'OpenAI', return_value=self.provider):
            result = visagismo.analisar_com_ia(mislabeled.read_bytes(), CATALOG, 'cabelo')
        kwargs = self.provider.responses.create.call_args.kwargs
        self.assertEqual(kwargs['text']['format']['type'], 'json_schema')
        self.assertTrue(kwargs['text']['format']['strict'])
        image = next(item for item in kwargs['input'][0]['content'] if item['type'] == 'input_image')
        self.assertTrue(image['image_url'].startswith('data:image/png;base64,'))
        self.assertEqual(len(result['recomendacoes']), 1)

    def test_analysis_malformed_provider_json_rejected(self):
        self.provider.responses.create.return_value = SimpleNamespace(output_text='{broken')
        with patch.object(visagismo, 'OpenAI', return_value=self.provider), self.assertRaises(ia.ErroVisagismoIA) as error:
            visagismo.analisar_com_ia(self.photo.read_bytes(), CATALOG, 'cabelo')
        self.assertEqual(error.exception.status, 502)

    def test_analysis_webp_mime_is_not_labeled_jpeg(self):
        webp = self.folder / 'customer.webp'
        webp.write_bytes(b'RIFF\x10\x00\x00\x00WEBPVP8 ')
        self.provider.responses.create.return_value = SimpleNamespace(output_text=json.dumps(self.raw_analysis()))
        with patch.object(visagismo, 'OpenAI', return_value=self.provider):
            visagismo.analisar_com_ia(webp.read_bytes(), CATALOG, 'cabelo')
        content = self.provider.responses.create.call_args.kwargs['input'][0]['content']
        self.assertTrue(next(item['image_url'] for item in content if item['type'] == 'input_image').startswith('data:image/webp;base64,'))

    def test_analysis_provider_refusal_empty_output_is_treatable(self):
        self.provider.responses.create.return_value = SimpleNamespace(output_text='')
        with patch.object(visagismo, 'OpenAI', return_value=self.provider), self.assertRaises(ia.ErroVisagismoIA) as error:
            visagismo.analisar_com_ia(self.photo.read_bytes(), CATALOG, 'cabelo')
        self.assertEqual(error.exception.status, 502)

    def test_image2_snapshots_omit_fidelity_and_low_is_upgraded(self):
        for model in ('gpt-image-2', 'gpt-image-2-2026-10-01'):
            with self.subTest(model=model):
                kwargs = ia.parametros_edicao(model, 'low')
                self.assertNotIn('input_fidelity', kwargs)
                self.assertIn(kwargs['quality'], ('medium', 'high'))

    def test_supported_image1_models_use_high_fidelity(self):
        for model in ('gpt-image-1', 'gpt-image-1.5'):
            with self.subTest(model=model):
                self.assertEqual(ia.parametros_edicao(model)['input_fidelity'], 'high')

    def test_beard_prompt_explicitly_preserves_scalp_hair(self):
        prompt = ia.prompt_simulacao(CATALOG[0], 'barba', self.stored_analysis('barba'), referencia=True)
        self.assertIn('Edit ONLY existing facial hair', prompt)
        self.assertIn('Do NOT change scalp hair', prompt)
        self.assertIn('Image 1 is the CUSTOMER', prompt)
        self.assertIn('Image 2 is a CATALOG STYLE REFERENCE', prompt)
        self.assertIn('Never copy the reference person', prompt)

    def test_color_only_prompt_preserves_style_and_person(self):
        prompt = ia.prompt_simulacao(None, 'pintura', {'apenas_cor': True}, cor='#112233', alvo='cabelo')
        self.assertIn('Do NOT change any haircut', prompt)
        self.assertIn('Preserve the exact same person', prompt)
        self.assertIn('preserve all facial hair color', prompt)
        self.assertIn('Never recolor eyebrows or skin', prompt)

    def analysis_route(self, error=None, services=None, catalog=None):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        values = CATALOG if catalog is None else catalog
        cursor.fetchall.return_value = [(c['id_corte'], c['nome'], c['descricao'], c['categoria'], 'ref.png', 1, c['genero']) for c in values]
        cursor.fetchone.return_value = (91,)
        self.provider.responses.create.return_value = SimpleNamespace(output_text=json.dumps(self.raw_analysis()))
        patches = [patch.object(visagismo, 'obter_usuario_logado', return_value={'id_usuario': 7, 'tipo': 1}),
                   patch.object(visagismo, 'carregar_servicos', return_value=services or [{'id_servico': 100, 'nome': 'Corte de cabelo', 'duracao': 30, 'genero': 'masculino'}]),
                   patch.object(visagismo, 'conectar_banco', return_value=connection),
                   patch.object(visagismo, 'OpenAI', return_value=self.provider),
                   patch.object(visagismo, 'registrar_registro')]
        if error is not None:
            patches.append(patch.object(visagismo, 'analisar_com_ia', side_effect=error))
        for current in patches:
            current.start()
            self.addCleanup(current.stop)
        response = self.client.post('/visagismo/analisar', data={
            'id_barbearia': '8', 'ids_servicos': '100', 'imagem': (io.BytesIO(PNG), 'customer.png')}, content_type='multipart/form-data')
        return response, connection, cursor

    def test_analysis_route_one_recommendation_and_visible_characteristics(self):
        response, connection, _ = self.analysis_route()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['versao_analise'], 2)
        self.assertEqual(len(response.json['recomendacoes']), 1)
        self.assertEqual(response.json['recomendacoes'][0]['id_corte'], 11)
        self.assertEqual(response.json['caracteristicas'], CHARACTERISTICS)
        connection.commit.assert_called_once()

    def test_analysis_provider_failure_no_random_fallback_no_commit(self):
        response, connection, cursor = self.analysis_route(error=ia.ErroVisagismoIA('Provedor indisponível', 502))
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('recomendacoes', response.json)
        connection.commit.assert_not_called()
        self.assertFalse(any('INSERT INTO VISAGISMO_SESSAO' in call.args[0] for call in cursor.execute.call_args_list))

    def test_analysis_missing_ai_is_503_no_catalog_fallback(self):
        with patch.dict(self.app.config, OPENAI_API_KEY=''):
            response, connection, _ = self.analysis_route()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('recomendacoes', response.json)
        self.provider.responses.create.assert_not_called()
        connection.commit.assert_not_called()

    def test_analysis_rejected_photo_never_creates_session(self):
        response, connection, _ = self.analysis_route(error=ia.ErroVisagismoIA('Sem pessoa visível', 422))
        self.assertEqual(response.status_code, 422)
        connection.commit.assert_not_called()

    def test_beard_service_without_catalog_never_falls_back_to_hair(self):
        response, connection, cursor = self.analysis_route(catalog=[], services=[{
            'id_servico': 100, 'nome': 'Corte de barba', 'duracao': 30, 'genero': 'masculino'}])
        self.assertIn(response.status_code, (404, 422))
        self.assertEqual(cursor.fetchall.call_count, 1)
        self.provider.responses.create.assert_not_called()
        connection.commit.assert_not_called()

    def simulation(self, payload=None, category='cabelo', session=None, cut=None):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        if session is None:
            session = (self.photo.name, json.dumps(self.stored_analysis(category)), 8, '[100]')
        if cut is None:
            cut = (11, 'Corte curto', 'Laterais curtas e topo natural', 'masculino', 'ref.png', 1, 'masculino')
        cursor.fetchone.side_effect = [session, cut]
        services = [{'id_servico': 100, 'nome': 'Corte de cabelo', 'duracao': 30, 'genero': 'masculino'}]
        if category == 'barba':
            services[0]['nome'] = 'Corte de barba'
            cut = (11, 'Barba curta', 'Contorno curto natural', 'barba', 'ref.png', 1, 'masculino')
            cursor.fetchone.side_effect = [session, cut]
        elif category == 'pintura':
            services[0]['nome'] = 'Pintar cabelo'
        with patch.object(visagismo, 'obter_usuario_logado', return_value={'id_usuario': 7, 'tipo': 1}), \
                patch.object(visagismo, 'carregar_servicos', return_value=services), \
                patch.object(visagismo, 'conectar_banco', return_value=connection), \
                patch.object(visagismo, 'OpenAI', return_value=self.provider), \
                patch.object(visagismo, 'capturar_registro', return_value={}), \
                patch.object(visagismo, 'registrar_registro'):
            response = self.client.post('/visagismo/91/simular', json=payload or {'id_corte': 11})
        return response, connection, cursor

    def test_simulation_rejects_unrecommended_catalog_id(self):
        response, connection, _ = self.simulation({'id_corte': 12})
        self.assertEqual(response.status_code, 400)
        self.provider.images.edit.assert_not_called()
        connection.commit.assert_not_called()

    def test_simulation_two_images_order_subject_then_cut_reference(self):
        (self.folder / 'cortes' / 'ref.png').write_bytes(PNG)
        response, connection, _ = self.simulation()
        self.assertEqual(response.status_code, 200)
        images = self.provider.images.edit.call_args.kwargs['image']
        self.assertEqual(len(images), 2)
        self.assertIn('cliente', images[0][0])
        self.assertIn('ref', images[1][0])
        self.assertEqual(images[0][2], 'image/png')
        self.assertEqual(images[1][2], 'image/png')
        self.assertTrue(response.json['referencia_utilizada'])
        connection.commit.assert_called_once()

    def test_simulation_missing_reference_is_explicit_not_substitute_photo(self):
        response, _, _ = self.simulation()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['referencia_utilizada'])
        self.assertTrue(response.json.get('aviso'))
        self.assertEqual(len(self.provider.images.edit.call_args.kwargs['image']), 1)

    def test_simulation_corrupt_reference_handled_without_identity_substitution(self):
        (self.folder / 'cortes' / 'ref.png').write_bytes(b'not an image')
        response, _, _ = self.simulation()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json['referencia_utilizada'])
        self.assertEqual(len(self.provider.images.edit.call_args.kwargs['image']), 1)

    def test_simulation_image2_quality_medium_no_unsupported_fidelity(self):
        response, _, _ = self.simulation()
        self.assertEqual(response.status_code, 200)
        kwargs = self.provider.images.edit.call_args.kwargs
        self.assertEqual(kwargs['model'], 'gpt-image-2')
        self.assertIn(kwargs['quality'], ('medium', 'high'))
        self.assertNotIn('input_fidelity', kwargs)

    def test_simulation_no_session_does_not_call_provider(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        with patch.object(visagismo, 'obter_usuario_logado', return_value={'id_usuario': 7, 'tipo': 1}), \
                patch.object(visagismo, 'conectar_banco', return_value=connection), \
                patch.object(visagismo, 'OpenAI', return_value=self.provider):
            response = self.client.post('/visagismo/91/simular', json={'id_corte': 11})
        self.assertEqual(response.status_code, 404)
        self.provider.images.edit.assert_not_called()
        self.assertIn(7, connection.cursor.return_value.execute.call_args.args[1])

    def test_simulation_legacy_multiple_recommendations_requires_reanalysis(self):
        analysis = self.stored_analysis()
        analysis.pop('versao_analise')
        analysis['recomendacoes'].append({'id_corte': 12, 'motivo': 'Outra opção'})
        response, connection, _ = self.simulation(session=(self.photo.name, json.dumps(analysis), 8, '[100]'))
        self.assertEqual(response.status_code, 409)
        self.provider.images.edit.assert_not_called()
        connection.commit.assert_not_called()

    def test_simulation_malformed_provider_result_never_commits(self):
        self.provider.images.edit.return_value = SimpleNamespace(data=[])
        response, connection, _ = self.simulation()
        self.assertEqual(response.status_code, 502)
        connection.commit.assert_not_called()
        self.assertFalse(list((self.folder / 'resultados').iterdir()))

    def test_simulation_nonimage_base64_never_commits(self):
        self.provider.images.edit.return_value = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(b'not image').decode())])
        response, connection, _ = self.simulation()
        self.assertEqual(response.status_code, 502)
        connection.commit.assert_not_called()
        self.assertFalse(list((self.folder / 'resultados').iterdir()))

    def test_simulation_missing_customer_photo_is_treatable(self):
        self.photo.unlink()
        response, connection, _ = self.simulation()
        self.assertIn(response.status_code, (404, 409, 422))
        self.provider.images.edit.assert_not_called()
        connection.commit.assert_not_called()

    def test_simulation_inactive_recommended_cut_rejected(self):
        response, connection, _ = self.simulation(cut=(11, 'Corte curto', 'Descrição', 'masculino', 'ref.png', 0, 'masculino'))
        self.assertIn(response.status_code, (404, 409, 422))
        self.provider.images.edit.assert_not_called()
        connection.commit.assert_not_called()

    def test_simulation_provider_exception_does_not_write_result(self):
        self.provider.images.edit.side_effect = RuntimeError('simulated provider failure')
        response, connection, _ = self.simulation()
        self.assertEqual(response.status_code, 502)
        connection.commit.assert_not_called()
        self.assertFalse(list((self.folder / 'resultados').iterdir()))

    def test_simulation_beard_service_never_changes_scalp_hair(self):
        response, _, _ = self.simulation(category='barba')
        self.assertEqual(response.status_code, 200)
        prompt = self.provider.images.edit.call_args.kwargs['prompt']
        self.assertIn('Edit ONLY existing facial hair', prompt)
        self.assertIn('Do NOT change scalp hair', prompt)

    def test_simulation_color_only_does_not_change_cut(self):
        session = (self.photo.name, json.dumps({'versao_analise': 2, 'categoria': 'pintura', 'apenas_cor': True}), 8, '[100]')
        response, _, _ = self.simulation({'cor': '#112233', 'alvo': 'cabelo'}, category='pintura', session=session)
        self.assertEqual(response.status_code, 200)
        prompt = self.provider.images.edit.call_args.kwargs['prompt']
        self.assertIn('Do NOT change any haircut', prompt)
        self.assertIn('preserve all facial hair color', prompt)
        self.assertEqual(len(self.provider.images.edit.call_args.kwargs['image']), 1)

    def test_simulation_color_only_session_rejects_injected_cut(self):
        session = (self.photo.name, json.dumps({'versao_analise': 2, 'categoria': 'pintura', 'apenas_cor': True}), 8, '[100]')
        response, connection, _ = self.simulation({'id_corte': 11, 'cor': '#112233', 'alvo': 'cabelo'}, category='pintura', session=session)
        self.assertEqual(response.status_code, 400)
        self.provider.images.edit.assert_not_called()
        connection.commit.assert_not_called()

    def test_simulation_scope_rejects_beard_color_for_scalp_only_service(self):
        response, connection, _ = self.simulation({'id_corte': 11, 'cor': '#112233', 'alvo': 'barba'})
        self.assertEqual(response.status_code, 400)
        self.provider.images.edit.assert_not_called()
        connection.commit.assert_not_called()

    def test_simulation_result_is_saved_through_compressed_storage(self):
        response, connection, _ = self.simulation()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['imagem_url'].endswith('.webp'))
        upload = self.image_batch.save.call_args
        self.assertEqual(upload.args, (PNG, 'visagismo/resultados'))
        self.assertEqual(upload.kwargs['owner_id'], 7)
        self.image_batch.commit.assert_called_once()
        self.image_batch.abort.assert_not_called()
        self.assertFalse(list((self.folder / 'resultados').iterdir()))

    def test_simulation_subject_path_traversal_rejected(self):
        session = ('../outside.png', json.dumps(self.stored_analysis()), 8, '[100]')
        response, connection, _ = self.simulation(session=session)
        self.assertEqual(response.status_code, 409)
        self.provider.images.edit.assert_not_called()
        connection.commit.assert_not_called()

    def test_simulation_manual_cut_first_validated_against_customer_photo(self):
        self.provider.responses.create.return_value = SimpleNamespace(output_text=json.dumps(self.raw_analysis()))
        session = (self.photo.name, json.dumps({'categoria': 'cabelo', 'modo': 'manual'}), 8, '[100]')
        response, connection, _ = self.simulation(session=session)
        self.assertEqual(response.status_code, 200)
        self.provider.responses.create.assert_called_once()
        self.provider.images.edit.assert_called_once()
        schema = self.provider.responses.create.call_args.kwargs['text']['format']['schema']
        self.assertEqual(schema['properties']['recomendacoes']['items']['properties']['id_corte']['enum'], [11])
        connection.commit.assert_called_once()

    def test_simulation_manual_incompatible_cut_never_edits_photo(self):
        raw = self.raw_analysis()
        raw['recomendacoes'][0]['compativel_com_cabelo_existente'] = False
        self.provider.responses.create.return_value = SimpleNamespace(output_text=json.dumps(raw))
        session = (self.photo.name, json.dumps({'categoria': 'cabelo', 'modo': 'manual'}), 8, '[100]')
        response, connection, _ = self.simulation(session=session)
        self.assertEqual(response.status_code, 422)
        self.provider.images.edit.assert_not_called()
        connection.commit.assert_not_called()

    def test_edit_legacy_category_with_url_keeps_previous_file(self):
        old = self.folder / 'cortes' / 'previous.png'
        old.write_bytes(PNG)
        for category in ('masculino', 'feminino'):
            with self.subTest(category=category):
                cursor = MagicMock()
                cursor.fetchone.side_effect = [None, (old.name,)]
                connection = MagicMock()
                connection.cursor.return_value = cursor
                with patch.object(visagismo, 'obter_usuario_logado', return_value={'id_usuario': 7, 'tipo': 0}), \
                        patch.object(visagismo, 'conectar_banco', return_value=connection), \
                        patch.object(visagismo, 'validar_url_imagem', side_effect=lambda url: url), \
                        patch.object(visagismo, 'capturar_registro', return_value={}), \
                        patch.object(visagismo, 'registrar_registro') as audit:
                    response = self.client.put('/visagismo/cortes/11', json={
                        'nome': 'Corte existente', 'categoria': category, 'genero': category,
                        'imagem_url': 'https://example.org/style.jpg'})
                self.assertEqual(response.status_code, 200)
                connection.commit.assert_called_once()
                audit.assert_called_once()
                self.assertEqual(old.read_bytes(), PNG)

    def test_booking_keeps_external_catalog_reference_url(self):
        now = datetime(2026, 10, 10, 12)
        row = (1, 7, 8, None, now, now + timedelta(minutes=30), '[]', 11, None, 'pendente')
        cursor = MagicMock()
        cursor.fetchone.side_effect = [('Corte curto', 'https://example.org/style.jpg'), (None, None, None), None]
        cursor.fetchall.return_value = []
        with patch.object(visagismo, 'email_do_cliente', return_value={'nome': 'Cliente'}), \
                patch.object(visagismo, 'email_da_barbearia', return_value={'nome': 'Barbearia'}):
            result = visagismo.serializar_agendamento(cursor, row)
        self.assertEqual(result['corte_imagem_url'], 'https://example.org/style.jpg')


if __name__ == '__main__':
    unittest.main()

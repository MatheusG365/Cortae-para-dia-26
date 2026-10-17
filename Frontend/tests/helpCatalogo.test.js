import test from 'node:test';
import assert from 'node:assert/strict';
import { filtrarRotas, rotuloArea, rotuloOrigem, rotaVinculada, selecionarRota } from '../src/pages/HelpAdmin/helpCatalogo.js';

const rotas = [
    { id: 'help', origem: 'frontend', rota: '/help', metodos: ['PAGE'], titulo: 'Central técnica', arquivos: [{ caminho: 'Frontend/src/pages/HelpAdmin/HelpAdmin.jsx' }] },
    { id: 'agenda', origem: 'backend', rota: '/agendamento/<int:id>', metodos: ['PUT'], titulo: 'Alterar agendamento', acesso: 'Administrador', como_funciona: ['Valida o horário e a disponibilidade.'], entrada: ['Observação opcional'], arquivos: [{ caminho: 'Backend/agenda.py' }] },
    { id: 'lista', origem: 'backend', rota: '/agendamentos', metodos: ['GET'], titulo: 'Listar atendimentos', arquivos: [] },
];

test('busca normaliza acentos e combina termos em documentação e arquivos', () => {
    assert.deepEqual(filtrarRotas(rotas, { busca: 'observacao AGENDA.PY' }).map(rota => rota.id), ['agenda']);
    assert.deepEqual(filtrarRotas(rotas, { busca: 'horario administrador' }).map(rota => rota.id), ['agenda']);
    assert.equal(filtrarRotas(rotas, { busca: 'agenda inexistente' }).length, 0);
});

test('filtros de origem e método se combinam sem omitir rotas quando vazios', () => {
    assert.deepEqual(filtrarRotas(rotas, { origem: 'backend', metodo: 'GET' }).map(rota => rota.id), ['lista']);
    assert.deepEqual(filtrarRotas(rotas, { origem: 'frontend', metodo: 'PUT' }), []);
    assert.equal(filtrarRotas(rotas).length, 3);
    assert.equal(filtrarRotas(rotas, { busca: '  ' }).length, 3);
});

test('seleção aponta para resultado visível e documentação da própria central', () => {
    assert.equal(selecionarRota(rotas, 'agenda').id, 'agenda');
    assert.equal(selecionarRota(rotas, 'ausente').id, 'help');
    assert.equal(selecionarRota(rotas.slice(1), 'help').id, 'agenda');
    assert.equal(selecionarRota([], 'help'), null);
});

test('rotas sem metadados opcionais ainda podem ser buscadas pelo caminho', () => {
    assert.equal(filtrarRotas([{ id: 'x', rota: '/health' }], { busca: 'health' }).length, 1);
});

test('mobile pode ser filtrado por origem e área sem misturar site e API', () => {
    const mobile = [
        ...rotas,
        { id: 'mobile:/cliente/carrinho', origem: 'mobile', area: 'cliente', rota: '/cliente/carrinho', metodos: ['NAVEGAÇÃO'], titulo: 'Carrinho', arquivos: [{ caminho: 'Cortae_mobile-main/src/app/cliente/carrinho.tsx', linguagem: 'tsx' }] },
        { id: 'mobile:/barbearia/agenda', origem: 'mobile', area: 'barbearia', rota: '/barbearia/agenda', metodos: ['NAVEGAÇÃO'], titulo: 'Agenda profissional' },
    ];
    assert.equal(filtrarRotas(mobile, { origem: 'mobile' }).length, 2);
    assert.deepEqual(filtrarRotas(mobile, { area: 'cliente' }).map(rota => rota.id), ['mobile:/cliente/carrinho']);
    assert.equal(filtrarRotas(mobile, { origem: 'backend', area: 'cliente' }).length, 0);
    assert.equal(filtrarRotas(mobile, { metodo: 'NAVEGAÇÃO', area: 'barbearia' }).length, 1);
    assert.equal(filtrarRotas(mobile, { busca: 'mobile tsx carrinho' }).length, 1);
});

test('busca mobile abrange jornada, área e API relacionada mantendo os outros filtros', () => {
    const mobile = [{ id: 'mobile:/cliente/checkout', origem: 'mobile', area: 'cliente', rota: '/cliente/checkout', titulo: 'Finalizar pedido', metodos: ['NAVEGAÇÃO'], api_relacionada: [{ id: 'api:pedido', rota: '/marketplace/pedidos', titulo: 'Criar pedido', metodos: ['POST'] }] }];
    const fluxos = [{ id: 'comprar', titulo: 'Comprar na loja', etapas: ['Conferir o frete e o endereço de entrega.'], rotas: ['mobile:/cliente/checkout'] }];
    assert.equal(filtrarRotas(mobile, { busca: 'comprar entrega cliente', fluxos }).length, 1);
    assert.equal(filtrarRotas(mobile, { busca: 'marketplace/pedidos post' }).length, 1);
    assert.equal(filtrarRotas(mobile, { busca: 'entrega', origem: 'backend', fluxos }).length, 0);
    assert.equal(filtrarRotas(mobile, { busca: 'entrega' }).length, 0);
    assert.equal(filtrarRotas(mobile, { busca: 'criar pedido', metodo: 'POST' }).length, 0);
});

test('vínculos exigem ID exato e não apontam para documentação aleatória', () => {
    assert.equal(rotaVinculada(rotas, 'agenda').rota, '/agendamento/<int:id>');
    assert.equal(rotaVinculada(rotas, '/agendamento/<int:id>'), null);
    assert.equal(rotaVinculada(rotas, 'mobile:ausente'), null);
    assert.equal(rotaVinculada([], 'help'), null);
    assert.equal(selecionarRota([{ id: 'mobile:x', origem: 'mobile' }], 'mobile:x').id, 'mobile:x');
});

test('rótulos distinguem mobile, web, API e origens desconhecidas', () => {
    assert.equal(rotuloOrigem('mobile'), 'Mobile · aplicativo');
    assert.equal(rotuloOrigem('frontend', true), 'Página web');
    assert.equal(rotuloOrigem('backend', true), 'API');
    assert.equal(rotuloOrigem('desconhecida', true), 'Documentação');
    assert.equal(rotuloOrigem(undefined), 'Documentação');
    assert.equal(rotuloArea('publico'), 'Acesso e cadastro');
    assert.equal(rotuloArea('cliente'), 'Cliente');
    assert.equal(rotuloArea('barbearia'), 'Barbearia');
    assert.equal(rotuloArea(undefined), '');
});


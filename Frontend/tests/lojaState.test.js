import test from 'node:test';
import assert from 'node:assert/strict';
import { caminhoDaLoja, filtrosDoCatalogo, idLojaDoEstabelecimento, temaDaLoja } from '../src/pages/Marketplace/lojaState.js';

test('Loja individual não permite trocar de barbearia por parâmetro da URL', () => {
    const params = new URLSearchParams('id_barbearia=99&busca=shampoo&categoria=Cabelo&ordem=preco_asc&outro=1');
    assert.deepEqual(filtrosDoCatalogo(params, '17'), { busca: 'shampoo', categoria: 'Cabelo', ordem: 'preco_asc' });
    assert.deepEqual(filtrosDoCatalogo(params, null), { busca: 'shampoo', categoria: 'Cabelo', ordem: 'preco_asc', id_barbearia: '99' });
});
test('Estabelecimento usa alvo explícito e não troca a loja pela conta do cliente', () => {
    const cliente = { id_usuario: 7, tipo: 1, nome: 'Cliente' };
    const dono = { id_usuario: 17, tipo: 2, nome: 'Barbearia' };
    assert.equal(idLojaDoEstabelecimento('28', { personalizacao: { id_usuario: 17 } }, cliente), '28');
    assert.equal(idLojaDoEstabelecimento(null, null, cliente), null);
    assert.equal(idLojaDoEstabelecimento(null, { personalizacao: { id_usuario: 28 } }, cliente), '28');
    assert.equal(idLojaDoEstabelecimento(null, { personalizado: false }, dono), '17');
    for (const invalido of ['', 'abc', '0', '-1', '9007199254740993']) assert.equal(idLojaDoEstabelecimento(invalido, null, dono), null);
});
test('Links individuais preservam o ID da barbearia e não apontam para a loja geral', () => {
    assert.equal(caminhoDaLoja(17), '/estabelecimento?usuario=17#loja-barbearia');
    assert.notEqual(caminhoDaLoja(28), caminhoDaLoja(17));
});

test('Compatibilidade da loja mantém filtros válidos e o catálogo no estabelecimento', () => {
    assert.equal(caminhoDaLoja(17, new URLSearchParams('busca=creme&categoria=Cabelo&ordem=nome&destaque=promocoes&id_barbearia=99&usuario=99&x=1')),
        '/estabelecimento?usuario=17&busca=creme&categoria=Cabelo&ordem=nome&destaque=promocoes#loja-barbearia');
});
test('Cores da loja aceitam somente hex e preservam as cinco escolhas', () => {
    const tema = temaDaLoja({ cor_primaria:'#123',cor_secundaria:'#456789',cor_terciaria:'#ABCDEF',cor_texto_primario:'#222222',cor_texto_secundario:'#EEE' });
    assert.equal(tema['--cor-destaque'],'#123');
    assert.equal(tema['--cor-fundo-b'],'#456789');
    assert.equal(tema['--cor-fundo'],'#ABCDEF');
    assert.equal(tema['--cor-texto'],'#222222');
    assert.equal(tema['--cor-texto-2'],'#EEE');
    for (const invalida of ['red','url(http://example.invalid)','var(--global)',';color:red','#12345678',null]) {
        assert.equal(temaDaLoja({cor_primaria:invalida})['--cor-destaque'],'#FF9C08');
    }
});
test('Tema é um novo objeto por loja e botões mantêm contraste com a cor escolhida', () => {
    const a = temaDaLoja({cor_primaria:'#000000'});
    const b = temaDaLoja({cor_primaria:'#FFFFFF'});
    assert.equal(a['--loja-texto-acao'],'#FFFFFF');
    assert.equal(b['--loja-texto-acao'],'#000000');
    assert.equal(a['--cor-destaque'],'#000000');
    assert.notEqual(a,b);
});

test('Paletas válidas mantêm textos escolhidos; contraste insuficiente deriva texto sem trocar fundos e cores raw', () => {
    const azul = { cor_primaria:'#7BC8FF', cor_secundaria:'#11263D', cor_terciaria:'#F3F8FD',
        cor_texto_primario:'#152A40', cor_texto_secundario:'#F4F8FF' };
    const tema = temaDaLoja(azul);
    assert.equal(tema['--loja-texto-superficie-legivel'], '#F4F8FF');
    assert.equal(tema['--loja-texto-primario-legivel'], '#152A40');
    const baixoContraste = temaDaLoja({ ...azul, cor_secundaria:'#FAFAFA' });
    assert.equal(baixoContraste['--cor-fundo-b'], '#FAFAFA');
    assert.equal(baixoContraste['--cor-texto-2'], '#F4F8FF');
    assert.equal(baixoContraste['--loja-texto-superficie-legivel'], '#000000');
    assert.equal(temaDaLoja({cor_terciaria:'#000000',cor_texto_primario:'#111111'})['--loja-texto-primario-legivel'], '#FFFFFF');
});

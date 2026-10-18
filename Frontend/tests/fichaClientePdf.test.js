import test from 'node:test';
import assert from 'node:assert/strict';
import { gerarFichaClientePdf, nomeArquivoFichaCliente, prepararFichaClientePdf } from '../src/services/fichaClientePdf.js';

const dataGeracao = new Date(2026, 9, 18, 15, 30);
const ficha = () => ({
    cliente: { id_usuario: 123, nome: 'João da Silva', email: 'joao@example.com', telefone: '(11) 99999-9999', total_agendamentos: 2, atendimentos_realizados: 1, faltas: 1, ultima_visita: '2026-10-10' },
    observacoes: 'Cliente prefere atendimento pela manhã.',
    preferencias: 'Corte com tesoura.',
    agendamentos: [
        { id_agendamento: 1, inicio_em: '2026-10-10T14:30:00', funcionario_nome: 'José', status: 'realizado', valor_total: null, servicos: [{ nome: 'Corte' }, { nome: 'Barba' }] },
        { id_agendamento: 2, inicio_em: '2026-10-11T14:30:00', funcionario_nome: 'José', status: 'falta', valor_total: 0 },
    ],
    pagamentos: [
        { id_financeiro: 1, id_agendamento: 1, tipo: 'pix_pago', descricao: 'Pagamento do corte', valor: 45.5, data_pagamento: '2026-10-10T14:30:00' },
        { id_financeiro: 2, tipo: 'boleto_pendente', valor: null },
        { id_financeiro: 3, tipo: 'legado', valor: 0 },
    ],
});

test('preserva valores ausentes, zero, serviços, datas e confirmação financeira da ficha', () => {
    const dados = prepararFichaClientePdf(ficha());
    assert.equal(dados.nome, 'João da Silva');
    assert.match(dados.contato, /joao@example.com/);
    assert.match(dados.resumo[3][1], /10\/10\/2026/);
    assert.match(dados.atendimentos[0][0], /10\/10\/2026,? 14:30/);
    assert.equal(dados.atendimentos[0][1], 'José\nCorte, Barba');
    assert.equal(dados.atendimentos[0][3], 'Sem valor registrado');
    assert.match(dados.atendimentos[1][3], /R\$\s*0,00/);
    assert.match(dados.pagamentos[0][3], /R\$\s*45,50/);
    assert.equal(dados.pagamentos[0][4], 'Recebido');
    assert.equal(dados.pagamentos[1][4], 'Pendente');
    assert.equal(dados.pagamentos[2][4], 'Confirmação não informada');
    assert.equal(dados.pagamentos[1][1], 'Não informado');
});

test('gera PDF A4 válido e mantém edições atuais sem alterar o objeto da ficha', () => {
    const detalhe = ficha();
    detalhe.observacoes = 'EDICAO_ATUAL_AINDA_NAO_SALVA';
    const antes = structuredClone(detalhe);
    const { documento, nomeArquivo } = gerarFichaClientePdf(detalhe, { dataGeracao });
    const bytes = documento.output('arraybuffer');
    const pdf = Buffer.from(bytes).toString('latin1');
    assert.ok(bytes.byteLength > 1500);
    assert.ok(pdf.startsWith('%PDF-'));
    assert.match(pdf, /%%EOF/);
    assert.match(pdf, /EDICAO_ATUAL_AINDA_NAO_SALVA/);
    assert.ok(Math.abs(documento.internal.pageSize.getWidth() - 210) < 0.1);
    assert.ok(Math.abs(documento.internal.pageSize.getHeight() - 297) < 0.1);
    assert.equal(nomeArquivo, 'ficha-cliente-joao-da-silva-2026-10-18.pdf');
    assert.deepEqual(detalhe, antes);
});

test('pagina observações longas e históricos completos até a última linha', () => {
    const detalhe = ficha();
    detalhe.observacoes = `${'Observacao detalhada com varias palavras para quebra de linha.\n'.repeat(90)}FIM_OBSERVACOES`;
    detalhe.preferencias = `${'Preferencia extensa. '.repeat(260)}FIM_PREFERENCIAS`;
    detalhe.agendamentos = Array.from({ length: 110 }, (_, i) => ({ ...detalhe.agendamentos[0], funcionario_nome: `Profissional ${i}`, servico_nome: `Servico ${i}`, servicos: undefined }));
    detalhe.pagamentos = Array.from({ length: 100 }, (_, i) => ({ ...detalhe.pagamentos[0], descricao: i === 99 ? 'ULTIMO_LANCAMENTO' : `Pagamento ${i}` }));
    const { documento } = gerarFichaClientePdf(detalhe, { dataGeracao });
    assert.ok(documento.getNumberOfPages() > 8);
    const pdf = documento.output();
    assert.match(pdf, /FIM_OBSERVACOES/);
    assert.match(pdf, /FIM_PREFERENCIAS/);
    assert.match(pdf, /Profissional 109/);
    assert.match(pdf, /ULTIMO_LANCAMENTO/);
    for (let pagina = 1; pagina <= documento.getNumberOfPages(); pagina++) {
        const conteudo = documento.internal.pages[pagina].join('\n');
        assert.match(conteudo, /Ficha do cliente/);
        assert.match(conteudo, new RegExp(`${pagina} de ${documento.getNumberOfPages()}`));
    }
});

test('funciona sem históricos, contato, observações e campos opcionais', () => {
    const { documento } = gerarFichaClientePdf({ cliente: {} }, { dataGeracao });
    assert.ok(documento.getNumberOfPages() >= 1);
    assert.equal(prepararFichaClientePdf({ cliente: {} }).resumo[0][1], '0');
    assert.throws(() => gerarFichaClientePdf(null), /Abra uma ficha/);
    assert.throws(() => gerarFichaClientePdf(ficha(), { dataGeracao: new Date('invalida') }), /Data de emissão inválida/);
});

test('divide uma única linha de histórico maior que uma página sem perder o fim', () => {
    const detalhe = ficha();
    detalhe.agendamentos = [{ ...detalhe.agendamentos[0], servicos: [{ nome: `${'Servico extenso com detalhes. '.repeat(550)}FIM_SERVICO_EXTENSO` }] }];
    detalhe.pagamentos = [{ ...detalhe.pagamentos[0], descricao: `${'Pagamento com descricao extensa. '.repeat(550)}ULTIMOPAG` }];
    const { documento } = gerarFichaClientePdf(detalhe, { dataGeracao });
    assert.ok(documento.getNumberOfPages() > 4);
    const pdf = documento.output();
    assert.match(pdf, /FIM_SERVICO_EXTENSO/);
    assert.match(pdf, /ULTIMOPAG/);
});

test('nome de download neutraliza caminhos, caracteres de controle e nomes extensos', () => {
    assert.equal(nomeArquivoFichaCliente('../../João\\ da Silva: <teste>\u0000', dataGeracao), 'ficha-cliente-joao-da-silva-teste-2026-10-18.pdf');
    assert.equal(nomeArquivoFichaCliente('🚀 / \\ ', dataGeracao), 'ficha-cliente-cliente-2026-10-18.pdf');
    assert.ok(nomeArquivoFichaCliente('a'.repeat(500), dataGeracao).length < 110);
});

import { apiFetch, queryDaApi } from './api';

function querySePeriodo(periodo = {}, idBarbearia) {
    const params = new URLSearchParams();

    if (periodo.dataInicio) params.set('data_inicio', periodo.dataInicio);
    if (periodo.dataFim) params.set('data_fim', periodo.dataFim);
    if (idBarbearia && idBarbearia !== 'todas') params.set('id_barbearia', idBarbearia);

    return queryDaApi(params);
}

export const buscarSaldo = (idBarbearia) =>
    apiFetch(`/financeiro/saldo${querySePeriodo({}, idBarbearia)}`);

export const buscarResumo = (periodo, idBarbearia) =>
    apiFetch(`/financeiro/resumo${querySePeriodo(periodo, idBarbearia)}`);

export const buscarMovimentacoes = (periodo, idBarbearia) =>
    apiFetch(`/financeiro/movimentacoes${querySePeriodo(periodo, idBarbearia)}`);

export const buscarResumoGeral = (periodo) =>
    apiFetch(`/financeiro/geral/resumo${querySePeriodo(periodo)}`);

export const buscarMovimentacoesGerais = (periodo) =>
    apiFetch(`/financeiro/geral/movimentacoes${querySePeriodo(periodo)}`);

export const criarCobrancaPix = (valor) =>
    apiFetch('/financeiro/cobrancas/pix', {
        method: 'POST',
        body: JSON.stringify({ valor })
    });

export const consultarCobrancaPix = (idCobranca) =>
    apiFetch(`/financeiro/cobrancas/pix/${encodeURIComponent(idCobranca)}`);

export function estadoPagamento(cobranca) {
    if (cobranca.tipo === 'na_hora_pendente') return 'Pagar no local · pendente de confirmação da barbearia';
    if (cobranca.confirmado === true && cobranca.status === 1) return 'Recebido';
    if (cobranca.pendente === true || cobranca.status === 0) return 'Pendente';
    return 'Confirmação não informada';
}

const rotasPagamento = { pix: '/pagamentos/pix', boleto: '/pagamentos/boleto', cartao: '/pagamentos/cartao', na_hora: '/pagamentos/na-hora' };
export function rotaPagamentoAgendamento(metodo) {
    return Object.hasOwn(rotasPagamento, metodo) ? rotasPagamento[metodo] : null;
}

export function podeConfirmarRecebimento(resposta, agendamento) {
    const saldoDisponivel = typeof resposta?.quitado === 'boolean'
        ? resposta.quitado !== true && Number(resposta.saldo) > 0
        : resposta?.na_hora_confirmado !== true && !(resposta?.cobrancas || []).some((cobranca) => cobranca.confirmado === true || cobranca.status === 1);
    return resposta?.na_hora_pendente === true && saldoDisponivel
        && !['cancelado', 'faltou'].includes(agendamento.status) && agendamento.valor_total != null;
}

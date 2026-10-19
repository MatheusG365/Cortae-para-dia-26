export const CARTAO_INCERTO = 'O resultado precisa de conferência. Confira o recebimento no banco e atualize o status antes de qualquer nova cobrança.';
export function limiteParcelas(total) {
    const centavos = Math.round(Number(total) * 100);
    return Number.isSafeInteger(centavos) && centavos > 0 ? Math.min(15, centavos) : 0;
}
export function dadosCartao(campos, total, hoje = new Date()) {
    const numero = String(campos.numero_cartao || '').replace(/\s/g, '');
    const validade = String(campos.validade || '').trim();
    const cvv = String(campos.cvv || '');
    if (!/^\d{16}$/.test(numero)) throw new Error('Informe os 16 dígitos do cartão virtual Arkhé.');
    if (!/^(0[1-9]|1[0-2])\/\d{4}$/.test(validade)) throw new Error('Informe a validade no formato MM/YYYY.');
    const [mes, ano] = validade.split('/').map(Number);
    if (ano < hoje.getFullYear() || (ano === hoje.getFullYear() && mes < hoje.getMonth() + 1)) throw new Error('O cartão está vencido.');
    if (!/^\d{3}$/.test(cvv)) throw new Error('Informe o CVV com 3 dígitos.');
    if (!['CREDITO', 'DEBITO'].includes(campos.tipo)) throw new Error('Escolha crédito ou débito.');
    const parcelas = Number(campos.parcelas);
    if (!Number.isInteger(parcelas) || parcelas < 1 || parcelas > limiteParcelas(total) || (campos.tipo === 'DEBITO' && parcelas !== 1)) throw new Error('Cada parcela deve ter ao menos R$ 0,01; débito permite uma parcela.');
    return { numero_cartao: numero, validade, cvv, tipo: campos.tipo, parcelas };
}
export function cartaoEmConferencia(dados) {
    return [dados?.cartao_estado, dados?.pagamento?.cartao_estado, dados?.pagamento_status].some(estado => ['processando', 'incerto'].includes(estado));
}
export function erroCartaoIncerto(erro) {
    const dados = erro?.dados || erro?.data;
    if (dados?.cartao_estado === 'recusado') return false;
    return cartaoEmConferencia(dados) || !erro?.status || erro.status >= 500 || erro.status === 409
        || (erro.status >= 200 && erro.status < 300) || erro?.tipo === 'resposta';
}
export function podePagarAgendamento(dados, status) {
    return !['cancelado', 'faltou'].includes(status) && !cartaoEmConferencia(dados)
        && dados?.cartao_estado !== 'aprovado' && dados?.quitado === false && dados?.parcial !== true
        && Array.isArray(dados.cobrancas) && !dados.cobrancas.length && Number(dados.valor_recebido) === 0
        && limiteParcelas(dados.saldo) > 0 && Math.abs(Number(dados.saldo) - Number(dados.valor_total)) < 0.005;
}
export function podePagarPedido(pedido) {
    return pedido?.status === 'aguardando_pagamento' && ['nao_criado', 'recusado'].includes(pedido.pagamento_status)
        && !cartaoEmConferencia(pedido) && !pedido.pagamento?.id_cobranca && !pedido.pagamento?.aprovado;
}
export function reciboCartao(dados) {
    if (dados?.cartao_estado && dados.cartao_estado !== 'aprovado') return null;
    const item = dados?.cartao_resultado || dados?.pagamento || dados;
    if (item?.metodo !== 'cartao' || item.aprovado !== true || item.status !== 1
        || (item.cartao_estado && item.cartao_estado !== 'aprovado')) return null;
    return Object.fromEntries(['valor', 'valor_recebido', 'taxa', 'tipo', 'parcelas', 'final_cartao', 'id_compra', 'id_movimentacao', 'data_compra'].map(chave => [chave, item[chave]]));
}

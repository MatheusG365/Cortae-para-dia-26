import { formatarMoeda } from '../../services/formatacao.js';
export const moeda = (valor) => formatarMoeda(Number(valor) || 0);
export const dataHora = (valor) => valor ? new Date(String(valor).includes('T') ? valor : String(valor).replace(' ', 'T')).toLocaleString('pt-BR') : '—';
export const statusPedido = { aguardando_pagamento: 'Aguardando pagamento', pago: 'Pago', separando: 'Em preparação', pronto_retirada: 'Pronto para retirada', enviado: 'Enviado', entregue: 'Entregue', cancelado: 'Cancelado', expirado: 'Expirado', reembolsado: 'Reembolsado' };
export const statusPagamento = { nao_criado: 'Não iniciado', processando: 'Processando cobrança', pendente: 'Aguardando pagamento', pago: 'Confirmado', incerto: 'Precisa de conferência' };
export const statusEntrega = { nao_criada: 'Ainda não preparado', preparando: 'Preparando etiqueta', preparada: 'Etiqueta preparada', comprando: 'Compra em processamento', comprada: 'Etiqueta comprada', gerando: 'Gerando etiqueta', gerada: 'Etiqueta disponível', vinculada: 'Envio vinculado pela barbearia', enviado: 'Em transporte', entregue: 'Entregue', preparo_incerto: 'Preparo precisa de conferência', compra_incerta: 'Compra precisa de conferência', geracao_incerta: 'Geração precisa de conferência' };
export function urlFoto(valor) {
    if (typeof valor === 'string' && /^\/uploads\/marketplace\/[a-f0-9]{32}\.webp$/.test(valor)) return valor;
    try { const url = new URL(valor); return url.protocol === 'https:' && !url.username && !url.password ? url.href : ''; } catch { return ''; }
}
export function fotosValidas(texto) { return String(texto || '').split(/\n/).map(s => s.trim()).filter(Boolean).map(urlFoto); }
export function quantidadeValida(valor, limite = Infinity) { const n = Number(valor); return Number.isInteger(n) && n > 0 && n <= limite; }
export function agruparCarrinho(itens = []) {
    const grupos = new Map();
    for (const item of itens) {
        const key = String(item.id_barbearia);
        if (!grupos.has(key)) grupos.set(key, { id_barbearia: item.id_barbearia, barbearia: item.barbearia, itens: [] });
        grupos.get(key).itens.push(item);
    }
    return Array.from(grupos.values());
}
export function novoCheckoutId() { return crypto.randomUUID(); }
export function acoesEntrega(pedido, emitirEtiquetas = false) {
    if (!pedido || pedido.retirada || pedido.pagamento_status !== 'pago' || ['cancelado', 'entregue'].includes(pedido.status)) return [];
    const acompanhar = [...(pedido.entrega?.url_etiqueta ? ['ver'] : []), 'rastreio'];
    const acoes = ({ nao_criada: ['preparar'], preparada: ['comprar'], comprada: ['gerar'], gerada: acompanhar, vinculado: ['rastreio'], vinculada: ['rastreio'], enviado: acompanhar })[pedido.entrega?.status] || [];
    return emitirEtiquetas ? acoes : acoes.filter(acao => ['ver', 'rastreio'].includes(acao));
}
export function podeCriarPix(pedido) { return pedido?.status === 'aguardando_pagamento' && pedido?.pagamento_status === 'nao_criado'; }
export function pagamentoDoPedido(id, pedido, cache) {
    if (id == null || !pedido || String(pedido.id_pedido) !== String(id)) return null;
    return (cache?.id != null && String(cache.id) === String(id) ? cache.dados : null) || pedido.pagamento || null;
}

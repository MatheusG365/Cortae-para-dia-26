import { cupomNormalizado } from './comercialState.js';

export function estadoCupomCheckout({ cupom, resumo, carregando, erro, podeConferir }) {
    const codigo = cupomNormalizado(cupom);
    if (!codigo) return { tipo: 'vazio' };
    if (!podeConferir) return { tipo: 'dados', codigo };
    if (carregando) return { tipo: 'conferindo', codigo };
    if (erro) return { tipo: 'erro', codigo };
    const confirmado = cupomNormalizado(typeof resumo?.cupom === 'string' ? resumo.cupom : resumo?.cupom?.codigo);
    if (confirmado !== codigo) return { tipo: 'conferindo', codigo };
    const desconto = resumo?.desconto;
    if (typeof desconto !== 'number' || !Number.isFinite(desconto) || desconto <= 0) return { tipo: 'semDesconto', codigo };
    return { tipo: 'aplicado', codigo, desconto };
}

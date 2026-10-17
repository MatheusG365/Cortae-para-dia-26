import { dataLocal } from './agendaState.js';
import { formatarMoeda } from './formatacao.js';

export const dinheiro = (valor) => valor == null ? 'Sem valor registrado' : formatarMoeda(valor);
export function momento(valor) {
    if (!valor) return '—';
    const texto = String(valor); const somenteDia = /^\d{4}-\d{2}-\d{2}$/.test(texto);
    const data = new Date(somenteDia ? `${texto}T12:00:00` : texto.replace(' ', 'T'));
    if (Number.isNaN(data.getTime())) return '—';
    return somenteDia ? data.toLocaleDateString('pt-BR') : data.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}
export function servicosDoAtendimento(atendimento) {
    const nomes = atendimento.servicos_nomes;
    if (Array.isArray(nomes)) return nomes.join(', ');
    if (nomes) return nomes;
    if (Array.isArray(atendimento.servicos)) return atendimento.servicos.map((s) => s.nome).filter(Boolean).join(', ');
    return atendimento.servico_nome || 'Serviço histórico';
}
export function estadoFinanceiroHistorico(pagamento) {
    if (String(pagamento.tipo || '').endsWith('_pendente')) return 'Pendente';
    if (['na_hora', 'pix_pago', 'cartao_pago', 'boleto_pago'].includes(pagamento.tipo)) return 'Recebido';
    return 'Confirmação não informada';
}
export const identificador = (item) => item.id_funcionario ?? item.id_servico ?? item.id_usuario ?? item.id;
export function intervaloAgenda(data, modo) {
    const base = new Date(`${data}T12:00:00`);
    const inicio = new Date(base); const fim = new Date(base);
    if (modo === 'semana') { inicio.setDate(base.getDate() - (base.getDay() + 6) % 7); fim.setTime(inicio.getTime()); fim.setDate(inicio.getDate() + 6); }
    if (modo === 'mes') { inicio.setDate(1); fim.setMonth(base.getMonth() + 1, 0); }
    const dias = [];
    for (const atual = new Date(inicio); atual <= fim; atual.setDate(atual.getDate() + 1)) dias.push(dataLocal(atual));
    return { inicio: dataLocal(inicio), fim: dataLocal(fim), dias };
}
export function totalRecebimentos(pagamentos) {
    return pagamentos.reduce((total, item) => total + Math.round(Number(item.valor || 0) * 100), 0) / 100;
}
export function linkAgendamento(origem, salao, profissional) {
    const query = new URLSearchParams({ barbearia: String(salao) });
    if (profissional) query.set('funcionario', String(profissional));
    return `${origem}/selecionar-servicos?${query}`;
}

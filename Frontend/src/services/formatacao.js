// Os chamadores preservam seus rótulos para valores ausentes e sua normalização.
const moedaBRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

export const formatarMoeda = valor => moedaBRL.format(Number(valor));
export const dinheiroZero = valor => formatarMoeda(Number(valor || 0));

export function momentoCurto(valor) {
    const data = new Date(String(valor || '').replace(' ', 'T'));
    return Number.isNaN(data.getTime()) ? '-' : data.toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });
}

// Datas da agenda chegam em ISO; não convertemos o fuso do horário reservado.
export function dataAgendamento(iso) {
    if (!iso) return '-';
    const [data] = String(iso).split('T');
    const [ano, mes, dia] = data.split('-');
    return `${dia}/${mes}/${ano}`;
}

export function horaAgendamento(iso) {
    if (!iso) return '';
    const [, hora] = String(iso).split('T');
    return (hora || '').slice(0, 5);
}

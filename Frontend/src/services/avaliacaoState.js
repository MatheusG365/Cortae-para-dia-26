export function erroAvaliacao(nota, comentario) {
    if (!Number.isInteger(nota) || nota < 1 || nota > 5) return 'Escolha uma nota de 1 a 5 estrelas.';
    if (typeof comentario !== 'string' || comentario.length > 1000) return 'O comentário deve ter até 1.000 caracteres.';
    return '';
}

export function rotuloMedia(nota) {
    return nota == null ? 'Sem avaliações' : `${Number(nota).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 2 })} / 5`;
}

export function atualizarAvaliacao(agendamentos, id, resposta) {
    return agendamentos.map((item) => Number(item.id_agendamento ?? item.id) === Number(id)
        ? { ...item, avaliacao: resposta.avaliacao, pode_avaliar: resposta.pode_avaliar } : item);
}

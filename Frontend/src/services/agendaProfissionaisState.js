export function idsServicosAgendamento(valor) {
    return [...new Set(String(valor || '').split(',').map(id => id.trim()).filter(id => /^[1-9]\d*$/.test(id)))];
}

export function contextoProfissionais(idBarbearia, idsServicos) {
    return JSON.stringify([String(idBarbearia || ''), idsServicosAgendamento(idsServicos).sort((a, b) => Number(a) - Number(b))]);
}

export function profissionaisDaResposta(dados, idsServicos) {
    if (!Array.isArray(dados?.funcionarios)) throw new Error('O servidor não retornou a lista de profissionais. Tente novamente.');
    const selecionados = idsServicosAgendamento(idsServicos);
    return dados.funcionarios.filter(profissional => {
        if (!/^[1-9]\d*$/.test(String(profissional?.id_funcionario || ''))) return false;
        if (profissional.ativo === false || profissional.ativo === 0 || profissional.ativo === '0') return false;
        const servicos = Array.isArray(profissional.servicos) ? profissional.servicos.map(servico => String(servico?.id_servico ?? servico)) : [];
        return selecionados.every(id => servicos.includes(id));
    });
}

export function funcionarioValido(id, profissionais) {
    return profissionais.some(profissional => String(profissional.id_funcionario) === String(id)) ? String(id) : '';
}

export function corpoAgendamento(idBarbearia, idsServicos, idFuncionario = '') {
    return { id_barbearia: Number(idBarbearia), ids_servicos: idsServicosAgendamento(idsServicos), id_funcionario: idFuncionario ? Number(idFuncionario) : null };
}

export function rotaAgendaGestao(tipo, idBarbearia) {
    const params = new URLSearchParams({ aba: 'agenda' });
    if (Number(tipo) === 0 && idBarbearia) params.set('id_barbearia', idBarbearia);
    return `/gestao?${params}`;
}

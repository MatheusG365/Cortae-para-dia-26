import { somenteDigitos } from './cadastroState.js';
export function erroFuncionario(funcionario) {
    if (!funcionario.nome?.trim()) return '';
    const existente = Boolean(funcionario.id_funcionario);
    const email = String(funcionario.email || '').trim();
    if (email.length > 150) return `O e-mail de ${funcionario.nome} deve ter até 150 caracteres.`;
    const telefone = somenteDigitos(funcionario.telefone);
    if ((!existente || email) && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return `Informe um e-mail válido para ${funcionario.nome}.`;
    if ((!existente || email) && ![10, 11].includes(telefone.length)) return `Informe um telefone com DDD para ${funcionario.nome}.`;
    const percentual = Number(funcionario.comissao_percentual ?? 0);
    if (!Number.isFinite(percentual) || percentual < 0 || percentual > 100) return `A comissão de ${funcionario.nome} deve estar entre 0% e 100%.`;
    return '';
}

export function anexarFuncionario(formulario, funcionario, indice) {
    const prefixo = `funcionarios[${indice}]`;
    if (funcionario.id_funcionario) formulario.append(`${prefixo}[id_funcionario]`, funcionario.id_funcionario);
    for (const campo of ['nome', 'descricao', 'email', 'telefone']) formulario.append(`${prefixo}[${campo}]`, String(funcionario[campo] || '').trim());
    formulario.append(`${prefixo}[comissao_percentual]`, Number(funcionario.comissao_percentual ?? 0));
    formulario.append(`${prefixo}[dias]`, funcionario.dias.join(','));
    formulario.append(`${prefixo}[servicos]`, funcionario.servicos.join(','));
}

export function podeEntrarNaEspera(horario) {
    return Boolean(horario && !horario.disponivel && horario.lista_espera_disponivel === true);
}

export function podeFinalizarAtendimento(agendamento, agora = Date.now()) {
    const final = Date.parse(String(agendamento.fim_em || '').replace(' ', 'T'));
    return ['agendado', 'confirmado'].includes(agendamento.status) && Number.isFinite(final) && final <= agora;
}

export function dataLocal(valor = new Date()) {
    return `${valor.getFullYear()}-${String(valor.getMonth() + 1).padStart(2, '0')}-${String(valor.getDate()).padStart(2, '0')}`;
}

export function periodoDoMes(hoje = new Date()) {
    return { inicio: dataLocal(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), fim: dataLocal(hoje) };
}

export function rotuloStatusAgendamento(status) {
    const rotulos = { cancelado: 'Cancelado', concluido: 'Concluído', faltou: 'Cliente faltou' };
    return Object.hasOwn(rotulos, status) ? rotulos[status] : 'Agendado';
}

export function erroSenhaBarbeiro(senha, confirmarSenha) {
    if (senha !== confirmarSenha) return 'As senhas não coincidem.';
    if (new TextEncoder().encode(senha).length > 72) return 'A senha deve ter no máximo 72 bytes. Reduza os caracteres.';
    if (senha.length < 8 || !/[A-Z]/.test(senha) || !/[a-z]/.test(senha) || !/[0-9]/.test(senha) || !/[^A-Za-z0-9]/.test(senha)) return 'Use pelo menos 8 caracteres, com letra maiúscula, minúscula, número e caractere especial.';
    return '';
}

export const camposAutomaticosCep = Object.freeze(['logradouro', 'bairro', 'cidade', 'uf']);
export const normalizarCep = valor => String(valor || '').replace(/\D/g, '').slice(0, 8);
export function formatarCep(valor) {
    const cep = normalizarCep(valor);
    return cep.length > 5 ? `${cep.slice(0, 5)}-${cep.slice(5)}` : cep;
}
export function novoEndereco(usuario = {}) {
    return { nome: usuario.nome || '', email: usuario.email || '', telefone: usuario.telefone || '', documento: '', cep: '', logradouro: '', numero: '', complemento: '', bairro: '', cidade: '', uf: '' };
}
export function enderecoSalvo(dados = {}) {
    return Object.fromEntries(Object.keys(novoEndereco()).map(campo => [campo, campo === 'cep' ? formatarCep(dados[campo]) : String(dados[campo] || '')]));
}
export function mudarCep(endereco, valor) {
    const cep = formatarCep(valor);
    if (normalizarCep(endereco.cep) === normalizarCep(cep)) return { ...endereco, cep };
    return { ...endereco, cep, logradouro: '', bairro: '', cidade: '', uf: '', numero: '', complemento: '' };
}
// Número/complemento são do destinatário; ViaCEP pode retornar complemento postal.
export function aplicarResultadoCep(atual, resultado, cepConsultado, camposEditados = []) {
    if (normalizarCep(atual.cep) !== normalizarCep(cepConsultado)) return atual;
    const proximo = { ...atual };
    for (const campo of camposAutomaticosCep) {
        if (!camposEditados.includes(campo) && typeof resultado?.[campo] === 'string') proximo[campo] = resultado[campo];
    }
    return proximo;
}

// Busca apenas na documentação recebida; os arquivos são carregados separadamente.
function normalizar(valor) {
    return String(valor ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}

export function rotuloOrigem(origem, curto = false) {
    const nomes = {
        frontend: curto ? 'Página web' : 'Frontend · página web',
        backend: curto ? 'API' : 'Backend · API',
        mobile: curto ? 'Mobile' : 'Mobile · aplicativo',
    };
    return nomes[origem] || 'Documentação';
}

export function rotuloArea(area) {
    return { publico: 'Acesso e cadastro', cliente: 'Cliente', barbearia: 'Barbearia' }[area] || area || '';
}

export function filtrarRotas(rotas, { busca = '', origem = '', metodo = '', area = '', fluxos = [] } = {}) {
    const termos = normalizar(busca).trim().split(/\s+/).filter(Boolean);
    return rotas.filter(rota => {
        if (origem && rota.origem !== origem) return false;
        if (metodo && !rota.metodos?.includes(metodo)) return false;
        if (area && (rota.origem !== 'mobile' || rota.area !== area)) return false;
        const fluxosDaRota = fluxos.filter(fluxo => fluxo.rotas?.includes(rota.id));
        const texto = normalizar([
            rota.rota, rota.titulo, rota.endpoint, rota.descricao, rota.acesso,
            rota.origem, rotuloOrigem(rota.origem), rota.area, rotuloArea(rota.area),
            ...(rota.como_funciona || []), ...(rota.entrada || []), ...(rota.saida || []),
            ...(rota.metodos || []), ...(rota.observacoes || []),
            ...(rota.arquivos || []).flatMap(arquivo => [arquivo.caminho, arquivo.linguagem]),
            ...(rota.api_relacionada || []).flatMap(api => [api.rota, api.titulo, ...(api.metodos || [])]),
            ...fluxosDaRota.flatMap(fluxo => [fluxo.titulo, ...(fluxo.etapas || [])]),
        ].join(' '));
        return termos.every(termo => texto.includes(termo));
    });
}

// Os vínculos abrem somente documentos existentes, sem executar a rota descrita.
export function rotaVinculada(rotas, id) {
    return rotas.find(rota => rota.id === id) || null;
}

export function selecionarRota(rotas, id) {
    return rotaVinculada(rotas, id)
        || rotas.find(rota => rota.origem === 'frontend' && rota.rota === '/help')
        || rotas[0]
        || null;
}

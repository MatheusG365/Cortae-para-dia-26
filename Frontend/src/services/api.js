// O proxy local e a publicação usam a mesma origem, inclusive para uploads.
export const API_URL = (import.meta.env?.VITE_API_URL?.trim() || '/api').replace(/\/+$/, '');

export function urlDaApi(caminho) {
    if (!caminho) return '';
    if (/^(https?:|blob:|data:)/i.test(caminho)) return caminho;
    return `${API_URL}/${String(caminho).replace(/^\/+/, '')}`;
}

export function queryDaApi(filtros = {}) {
    const query = new URLSearchParams(filtros);
    return query.size ? `?${query}` : '';
}

function mensagemSegura(valor) {
    return typeof valor === 'string' && valor.trim() && !/<[^>]+>/.test(valor)
        ? valor.trim()
        : null;
}

function mensagemDosDados(dados) {
    return mensagemSegura(dados?.mensagem?.informacao)
        || mensagemSegura(dados?.erro?.informacao)
        || mensagemSegura(dados?.erro);
}

function criarErro(mensagem, tipo, status = 0, dados) {
    const erro = new Error(mensagem);
    erro.tipo = tipo;
    erro.status = status;
    erro.dados = dados;
    return erro;
}

export async function apiFetch(endpoint, options = {}, formato = 'json') {
    const headers = new Headers(options.headers);
    const formulario = options.body instanceof FormData;
    if (options.body != null && !formulario && !headers.has('Content-Type')) {
        headers.set('Content-Type', 'application/json');
    }
    if (!headers.has('Accept')) headers.set('Accept', formato === 'blob' ? '*/*' : 'application/json');

    let resposta;
    let texto;
    try {
        resposta = await fetch(urlDaApi(endpoint), {
            credentials: 'include',
            ...options,
            headers
        });
        if (resposta.ok && formato === 'blob') return await resposta.blob();
        texto = await resposta.text();
    } catch (erro) {
        if (erro.name === 'AbortError' || options.signal?.aborted) throw erro;
        throw criarErro('Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.', 'rede');
    }

    let dados;
    try {
        dados = texto.trim() ? JSON.parse(texto) : {};
    } catch {
        throw criarErro(
            resposta.ok ? 'O servidor retornou uma resposta inválida.' : 'Não foi possível concluir a operação.',
            resposta.ok ? 'resposta' : 'http',
            resposta.status
        );
    }

    if (!resposta.ok) {
        throw criarErro(mensagemDosDados(dados) || 'Não foi possível concluir a operação.', 'http', resposta.status, dados);
    }
    return dados;
}

export function mensagemDaApi(erro) {
    return mensagemDosDados(erro?.dados)
        || mensagemSegura(erro?.message)
        || 'Ocorreu um erro ao comunicar com o servidor.';
}

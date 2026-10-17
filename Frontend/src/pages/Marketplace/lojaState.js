export function idLojaDoEstabelecimento(alvo, dados, usuario) {
    const id = alvo != null ? alvo : dados?.personalizacao?.id_usuario ?? (Number(usuario?.tipo) === 2 ? usuario.id_usuario ?? usuario.id : null);
    return /^\d+$/.test(String(id)) && Number(id) > 0 && Number.isSafeInteger(Number(id)) ? String(Number(id)) : null;
}
export function filtrosDoCatalogo(params, idLoja) {
    const permitidos = idLoja != null ? ['busca', 'categoria', 'ordem', 'destaque'] : ['busca', 'categoria', 'ordem', 'destaque', 'id_barbearia'];
    return Object.fromEntries(permitidos.map(chave => [chave, params.get(chave)]).filter(([, valor]) => valor));
}
export function caminhoDaLoja(id, params = new URLSearchParams()) {
    const filtros = new URLSearchParams({ usuario: String(id), ...filtrosDoCatalogo(params, id) });
    return `/estabelecimento?${filtros}#loja-barbearia`;
}

export function temaDaLoja(personalizacao = {}) {
    personalizacao ||= {};
    const campos = {
        '--cor-destaque': ['cor_primaria', '#FF9C08'],
        '--cor-fundo': ['cor_terciaria', '#FFFFFF'],
        '--cor-fundo-b': ['cor_secundaria', '#000000'],
        '--cor-texto': ['cor_texto_primario', '#000000'],
        '--cor-texto-2': ['cor_texto_secundario', '#FFFFFF'],
    };
    const tema = Object.fromEntries(Object.entries(campos).map(([variavel, [campo, padrao]]) => [variavel,
        /^#(?:[0-9a-f]{3}|[0-9a-f]{6})$/i.test(personalizacao[campo] || '') ? personalizacao[campo] : padrao]));
    tema['--loja-texto-acao'] = textoLegivel(tema['--cor-destaque']);
    tema['--loja-texto-superficie-legivel'] = textoLegivel(tema['--cor-fundo-b'], tema['--cor-texto-2']);
    tema['--loja-texto-primario-legivel'] = textoLegivel(tema['--cor-fundo'], tema['--cor-texto']);
    return tema;
}

function luminanciaHex(cor) {
    const hex = cor.slice(1);
    const completo = hex.length === 3 ? [...hex].map(c => c + c).join('') : hex;
    const canais = [0, 2, 4].map(i => {
        const c = parseInt(completo.slice(i, i + 2), 16) / 255;
        return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4;
    });
    return canais[0] * .2126 + canais[1] * .7152 + canais[2] * .0722;
}

function textoLegivel(fundo, escolhido) {
    const luz = luminanciaHex(fundo);
    if (escolhido) {
        const texto = luminanciaHex(escolhido);
        const contraste = (Math.max(luz, texto) + .05) / (Math.min(luz, texto) + .05);
        if (contraste >= 4.5) return escolhido;
    }
    return (luz + .05) / .05 >= 1.05 / (luz + .05) ? '#000000' : '#FFFFFF';
}

export function normalizarTexto(texto) {
    return String(texto ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase().replace(/\s+/g, ' ').trim();
}

export function indiceSelecionado(opcoes, valor) {
    const encontrado = opcoes.findIndex(opcao => opcao.value === String(valor ?? ''));
    return encontrado >= 0 ? encontrado : opcoes.findIndex(opcao => !opcao.disabled);
}

export function moverOpcao(opcoes, atual, direcao) {
    if (!opcoes.some(opcao => !opcao.disabled)) return -1;
    if (direcao === 'inicio') return opcoes.findIndex(opcao => !opcao.disabled);
    if (direcao === 'fim') return opcoes.findLastIndex(opcao => !opcao.disabled);
    const passo = direcao === 'anterior' ? -1 : 1;
    let indice = atual < 0 ? (passo === 1 ? -1 : opcoes.length) : atual;
    for (let tentativa = 0; tentativa < opcoes.length; tentativa += 1) {
        indice = (indice + passo + opcoes.length) % opcoes.length;
        if (!opcoes[indice].disabled) return indice;
    }
    return -1;
}

export function buscarOpcao(opcoes, texto, atual = -1) {
    const busca = normalizarTexto(texto);
    if (!busca) return -1;
    for (let passo = 1; passo <= opcoes.length; passo += 1) {
        const indice = (Math.max(atual, -1) + passo) % opcoes.length;
        if (!opcoes[indice].disabled && normalizarTexto(opcoes[indice].label).startsWith(busca)) return indice;
    }
    return -1;
}

export function posicionarLista(rect, viewport, alturaDesejada = 300) {
    const margem = 8;
    const inicioX = viewport.left || 0;
    const inicioY = viewport.top || 0;
    const largura = Math.max(1, Math.min(Math.max(rect.width, 180), viewport.width - margem * 2));
    const abaixo = inicioY + viewport.height - rect.bottom - margem - 6;
    const acima = rect.top - inicioY - margem - 6;
    const invertido = abaixo < Math.min(alturaDesejada, 180) && acima > abaixo;
    const altura = Math.max(1, Math.min(alturaDesejada, Math.max(36, invertido ? acima : abaixo), viewport.height - margem * 2));
    return {
        left: Math.max(inicioX + margem, Math.min(rect.left, inicioX + viewport.width - largura - margem)),
        top: Math.max(inicioY + margem, Math.min(invertido ? rect.top - altura - 6 : rect.bottom + 6, inicioY + viewport.height - altura - margem)),
        width: largura,
        maxHeight: altura,
    };
}

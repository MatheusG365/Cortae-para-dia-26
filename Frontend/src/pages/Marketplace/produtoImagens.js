export const MAX_FOTOS_PRODUTO = 8;
export function validarFotosProduto(links, arquivos = []) {
    if (links.length + arquivos.length > MAX_FOTOS_PRODUTO) throw new Error('Cada produto pode ter até oito fotos.');
    for (const arquivo of arquivos) {
        if (!/^image\/(jpeg|png|webp|gif)$/i.test(arquivo.type || '')) throw new Error('Escolha fotos JPEG, PNG, WebP ou GIF estático.');
        if (!arquivo.size || arquivo.size > 10 * 1024 * 1024) throw new Error('Cada foto deve ter até 10 MB.');
    }
}
export function produtoRequest(method, dados, arquivos = []) {
    validarFotosProduto(dados.imagens || [], arquivos);
    if (!arquivos.length) return { method, body: JSON.stringify(dados) };
    const body = new FormData();
    body.append('dados', JSON.stringify(dados));
    arquivos.forEach(arquivo => body.append('imagens', arquivo, arquivo.name));
    return { method, body };
}

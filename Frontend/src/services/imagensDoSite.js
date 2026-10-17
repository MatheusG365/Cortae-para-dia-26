import { urlDaApi } from './api.js';

// Os nomes públicos são estáveis; o backend resolve os arquivos privados do Drive.
export function urlImagemDoSite(nome) {
    return urlDaApi(`/midia/site/${encodeURIComponent(nome)}`);
}

export function inicializarImagensDoSite(documento = document) {
    const fundos = {
        '--imagem-site-banner': 'banner.png',
        '--imagem-site-login': 'imagem_login.png',
        '--imagem-site-cadastro': 'cadastro.png',
    };
    for (const [variavel, nome] of Object.entries(fundos)) {
        documento.documentElement.style.setProperty(variavel, `url(${JSON.stringify(urlImagemDoSite(nome))})`);
    }
    const favicon = documento.querySelector('link[rel="icon"]');
    if (favicon) {
        favicon.type = 'image/webp';
        favicon.href = urlImagemDoSite('logosolo.png');
    }
}

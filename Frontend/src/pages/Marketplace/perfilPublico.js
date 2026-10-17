import { apiFetch } from '../../services/api.js';
import { idLojaDoEstabelecimento } from './lojaState.js';

export function carregarPerfilPublico(id, options = {}) {
    const alvo = idLojaDoEstabelecimento(id, null, null);
    if (!alvo) return Promise.reject(new Error('Barbearia inválida.'));
    // Vitrine e cores não precisam de sessão nem de endpoints de configuração.
    return apiFetch(`/marketplace/barbearias/${alvo}/perfil`, { ...options, credentials: 'omit' });
}

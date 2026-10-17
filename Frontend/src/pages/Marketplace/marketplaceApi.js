import { apiFetch, queryDaApi } from '../../services/api';
export function marketplace(rota, options = {}, filtros = {}) {
    const filtrosPresentes = Object.entries(filtros).filter(([, v]) => v !== '' && v != null);
    return apiFetch(`/marketplace${rota}${queryDaApi(filtrosPresentes)}`, options);
}
export const json = (method, body) => ({ method, body: JSON.stringify(body) });

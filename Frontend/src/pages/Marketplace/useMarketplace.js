import useRecurso from '../../services/useRecurso';
import { marketplace } from './marketplaceApi';
export default function useMarketplace(rota, filtros = {}) {
    return useRecurso(marketplace, rota, filtros);
}

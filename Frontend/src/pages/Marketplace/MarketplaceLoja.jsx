import { Navigate, useParams, useSearchParams } from 'react-router-dom';
import { caminhoDaLoja } from './lojaState';
export default function MarketplaceLoja() {
    const { id_barbearia } = useParams();
    const [params] = useSearchParams();
    return <Navigate replace to={caminhoDaLoja(id_barbearia, params)} />;
}

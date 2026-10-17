import { useCallback, useEffect, useState } from 'react';
import { mensagemDaApi } from './api';
import { useAuth } from '../contexts/useAuth';
import { identidadeDoUsuario } from '../contexts/authStorage';

const carregando = () => ({ dados: null, carregando: true, erro: '' });

// Compartilha somente consultas. Mutações e regras de pagamento continuam locais.
export default function useRecurso(requisicao, rota, filtros = {}) {
    const { usuario } = useAuth();
    const conta = identidadeDoUsuario(usuario);
    const chave = JSON.stringify(filtros);
    const [estado, setEstado] = useState(carregando);
    const [versao, setVersao] = useState(0);
    const identidade = JSON.stringify([conta, rota, chave, versao]);
    const recarregar = useCallback(() => setVersao(v => v + 1), [setVersao]);

    useEffect(() => {
        const controle = new AbortController();
        const publicar = novo => {
            if (!controle.signal.aborted) setEstado({ ...novo, identidade, requisicao });
        };
        queueMicrotask(() => publicar(carregando()));
        requisicao(rota, { signal: controle.signal }, JSON.parse(chave))
            .then(dados => publicar({ dados, carregando: false, erro: '' }))
            .catch(erro => publicar({ dados: null, carregando: false, erro: mensagemDaApi(erro) }));
        return () => controle.abort();
    }, [requisicao, rota, chave, identidade]);

    // Também invalida dados quando a função muda de estabelecimento/usuário.
    const atual = estado.identidade === identidade && estado.requisicao === requisicao ? estado : carregando();
    return { ...atual, recarregar };
}

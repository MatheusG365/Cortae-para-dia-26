import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/useAuth';
import { apiFetch, mensagemDaApi } from './api';

export default function useTermosUso({ cadastro = false, versaoEsperada = null } = {}) {
    const { usuario } = useAuth();
    const identidade = `${cadastro ? 'cadastro' : String(usuario?.id_usuario ?? usuario?.id ?? 'anonimo')}:${versaoEsperada || ''}`;
    const [estado, setEstado] = useState(null);
    const [marcado, setMarcado] = useState(null);
    const atual = estado?.identidade === identidade ? estado : null;
    const selecionado = marcado?.identidade === identidade && marcado?.versao === atual?.dados?.versao;
    useEffect(() => {
        const controller = new AbortController();
        apiFetch('/termos-uso', { signal: controller.signal })
            .then(async dados => {
                if (controller.signal.aborted) return;
                const rascunho = dados.aceite_habilitado === false || dados.estado_publicacao === 'rascunho';
                const aceite = cadastro || rascunho ? null : await apiFetch('/termos-uso/aceite', { signal: controller.signal });
                if (!controller.signal.aborted) setEstado({ identidade, dados, aceito: aceite?.aceito === true && aceite.versao_atual === dados.versao });
            })
            .catch(erro => { if (!controller.signal.aborted) setEstado({ identidade, erro: mensagemDaApi(erro) }); });
        return () => controller.abort();
    }, [identidade, cadastro]);
    const rascunho = atual?.dados?.aceite_habilitado === false || atual?.dados?.estado_publicacao === 'rascunho';
    const permitido = !!atual?.dados && !atual.erro && (rascunho || atual.aceito || selecionado);
    async function aceitar() {
        if (!permitido) throw new Error('Leia e aceite os Termos de Uso antes de continuar.');
        if (rascunho) return;
        if (!atual.aceito) {
            await apiFetch('/termos-uso/aceite', { method: 'POST', body: JSON.stringify({ versao: atual.dados.versao, aceito: true }) });
            setEstado({ ...atual, aceito: true });
        }
    }
    return { dados: atual?.dados, erro: atual?.erro, carregando: !atual, rascunho, aceito: !!atual?.aceito, marcado: !!selecionado, permitido, marcar: valor => setMarcado(valor ? { identidade, versao: atual?.dados?.versao } : null), aceitar };
}

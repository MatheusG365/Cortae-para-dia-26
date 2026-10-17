import { useEffect, useState } from 'react';
import { apiFetch, mensagemDaApi } from './api';
import { useAuth } from '../contexts/useAuth';

export default function useResumoOperacao(endpoint, corpo, habilitado = true) {
    const { usuario } = useAuth();
    const assinatura = JSON.stringify(corpo);
    const identidade = `${usuario?.id_usuario ?? usuario?.id ?? 'anonimo'}:${endpoint}:${assinatura}`;
    const [estado, setEstado] = useState(null);
    const [revisao, setRevisao] = useState(0);
    const atual = habilitado && estado?.identidade === identidade ? estado : null;
    useEffect(() => {
        if (!habilitado) return undefined;
        const controller = new AbortController();
        const timer = setTimeout(() => {
            apiFetch(endpoint, { method: 'POST', body: assinatura, signal: controller.signal })
                .then(dados => {
                    const resumo = dados?.resumo;
                    if (!resumo || !['valor_base', 'frete', 'taxa_valor', 'valor_total_cliente'].every(campo => typeof resumo[campo] === 'number' && Number.isFinite(resumo[campo]) && resumo[campo] >= 0) || !resumo.confirmacao_resumo) throw new Error('O servidor não confirmou os valores desta operação. Tente novamente.');
                    if (!controller.signal.aborted) setEstado({ identidade, resumo });
                })
                .catch(erro => { if (!controller.signal.aborted) setEstado({ identidade, erro: mensagemDaApi(erro) }); });
        }, 200);
        return () => { clearTimeout(timer); controller.abort(); };
    }, [endpoint, assinatura, identidade, habilitado, revisao]);
    return { resumo: atual?.resumo, erro: atual?.erro, carregando: habilitado && !atual, recarregar: () => { setEstado(null); setRevisao(a => a + 1); } };
}

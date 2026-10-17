import { useEffect, useState } from 'react';
import { apiFetch, mensagemDaApi } from '../../services/api';
import { estadoPagamento, podeConfirmarRecebimento } from '../../services/pagamentoState';
import { useAuth } from '../../contexts/useAuth';
import styles from './PagamentoAgendamento.module.css';
import { dinheiro } from '../../services/gestaoState';
import { dinheiroZero } from '../../services/formatacao';
import ResumoTaxa from '../ResumoTaxa/ResumoTaxa';

export default function PagamentoAgendamento({ agendamento, aoConfirmar }) {
    const { usuario } = useAuth();
    const permitido = [0, 1, 2].includes(Number(usuario?.tipo));
    const [resposta, setResposta] = useState(null);
    const [erro, setErro] = useState('');
    useEffect(() => {
        if (!permitido) return undefined;
        const controller = new AbortController();
        apiFetch(`/pagamentos/agendamento/${agendamento.id_agendamento}`, { signal: controller.signal })
            .then(setResposta).catch((falha) => { if (falha.name !== 'AbortError') setErro(mensagemDaApi(falha)); });
        return () => controller.abort();
    }, [agendamento.id_agendamento, permitido]);
    if (!permitido) return null;
    return <section className={styles.pagamento} aria-label="Pagamento deste agendamento">
        <ResumoTaxa resumo={resposta?.resumo || agendamento.resumo} servico gestor={[0, 2].includes(Number(usuario?.tipo))} />
        {erro ? <p role="status">Pagamento indisponível: {erro}</p> : !resposta ? <p role="status">Consultando pagamento…</p> : <>
            {typeof resposta.quitado === 'boolean' && <p><strong>{resposta.quitado ? 'Atendimento quitado' : resposta.parcial ? 'Pagamento parcial' : 'Pagamento pendente'}</strong> · Recebido: {dinheiro(resposta.valor_recebido)} · Saldo: {dinheiro(resposta.saldo)}</p>}
            {!resposta.cobrancas?.length && <p>Sem cobrança registrada.</p>}
            {(resposta.cobrancas || []).map((item) => <p key={item.id_financeiro}><strong>{estadoPagamento(item)}</strong> · {dinheiroZero(item.valor)}</p>)}
            {aoConfirmar && podeConfirmarRecebimento(resposta, agendamento) && <button type="button" onClick={() => aoConfirmar({ ...agendamento, valor_a_receber: resposta.saldo ?? agendamento.valor_total }, 'receber')}>{resposta.parcial ? `Confirmar saldo recebido em dinheiro (${dinheiro(resposta.saldo)})` : 'Confirmar dinheiro recebido'}</button>}
        </>}
    </section>;
}

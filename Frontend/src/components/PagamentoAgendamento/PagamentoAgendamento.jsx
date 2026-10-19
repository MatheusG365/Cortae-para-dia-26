import { useEffect, useRef, useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import { apiFetch, mensagemDaApi, urlDaApi } from '../../services/api';
import { estadoPagamento, podeConfirmarRecebimento } from '../../services/pagamentoState';
import { CARTAO_INCERTO, dadosCartao, cartaoEmConferencia, erroCartaoIncerto, podePagarAgendamento, reciboCartao } from '../../services/cartaoArkhe';
import { useAuth } from '../../contexts/useAuth';
import styles from './PagamentoAgendamento.module.css';
import { dinheiro } from '../../services/gestaoState';
import { dinheiroZero } from '../../services/formatacao';
import ResumoTaxa from '../ResumoTaxa/ResumoTaxa';
import CartaoArkhe, { ReciboCartao } from '../CartaoArkhe/CartaoArkhe';

export default function PagamentoAgendamento(props) {
    return <PagamentoAgendamentoAtual key={String(props.agendamento.id_agendamento)} {...props} />;
}

function PagamentoAgendamentoAtual({ agendamento, aoConfirmar }) {
    const { usuario } = useAuth();
    const permitido = [0, 1, 2].includes(Number(usuario?.tipo));
    const cliente = Number(usuario?.tipo) === 1;
    const [resposta, setResposta] = useState(null);
    const [pagamento, setPagamento] = useState(null);
    const [erro, setErro] = useState('');
    const [ocupado, setOcupado] = useState(false);
    const [conferencia, setConferencia] = useState(false);
    const trava = useRef(false);
    const endpoint = `/pagamentos/agendamento/${agendamento.id_agendamento}`;
    useEffect(() => {
        if (!permitido) return undefined;
        const controller = new AbortController();
        apiFetch(endpoint, { signal: controller.signal })
            .then(setResposta).catch(falha => { if (falha.name !== 'AbortError') setErro(mensagemDaApi(falha)); });
        return () => controller.abort();
    }, [endpoint, permitido]);
    async function atualizar() {
        const dados = await apiFetch(endpoint);
        setResposta(dados);
        if (['aprovado', 'recusado'].includes(dados.cartao_estado) || dados.cobrancas?.length || dados.quitado) setConferencia(false);
        return dados;
    }
    async function pagarCartao(campos) {
        if (trava.current) return;
        trava.current = true; setOcupado(true); setErro('');
        let enviado = false;
        try {
            const atual = await atualizar();
            if (conferencia || !podePagarAgendamento(atual, agendamento.status)) throw new Error('Já existe pagamento ou cobrança. Confira o status atualizado.');
            if (Math.abs(Number(atual.saldo) - Number(resposta.saldo)) > 0.005) throw new Error('O valor mudou. Confira o novo total antes de confirmar.');
            enviado = true;
            const dados = await apiFetch('/pagamentos/cartao', { method: 'POST', body: JSON.stringify({ id_agendamento: agendamento.id_agendamento, ...dadosCartao(campos, atual.saldo) }) });
            setPagamento(dados); setConferencia(!reciboCartao(dados));
            if (!reciboCartao(dados)) setErro(CARTAO_INCERTO);
        } catch (falha) {
            const incerto = enviado && erroCartaoIncerto(falha);
            if (incerto) setConferencia(true);
            setErro(incerto ? CARTAO_INCERTO : mensagemDaApi(falha));
        } finally {
            if (enviado) { try { await atualizar(); } catch { setErro('Não foi possível atualizar o status. Confira o banco antes de outra cobrança.'); } }
            trava.current = false; setOcupado(false);
        }
    }
    async function solicitar(metodo) {
        if (trava.current || conferencia) return;
        trava.current = true; setOcupado(true); setErro('');
        try {
            const atual = await atualizar();
            if (!podePagarAgendamento(atual, agendamento.status)) throw new Error('Já existe pagamento ou cobrança. Confira o status atualizado.');
            const dados = await apiFetch(`/pagamentos/${metodo}`, { method: 'POST', body: JSON.stringify({ id_agendamento: agendamento.id_agendamento }) });
            setPagamento(dados); await atualizar();
        } catch (falha) { setErro(mensagemDaApi(falha)); } finally { trava.current = false; setOcupado(false); }
    }
    const bloqueado = conferencia || cartaoEmConferencia(resposta);
    const podePagar = cliente && resposta && !bloqueado && !reciboCartao(pagamento) && podePagarAgendamento(resposta, agendamento.status);
    const codigo = pagamento?.codigo_pagamento || pagamento?.codigo_pix;
    const boleto = typeof pagamento?.url_boleto === 'string' && (/^https:\/\//i.test(pagamento.url_boleto) || /^\/(?!\/)/.test(pagamento.url_boleto)) ? urlDaApi(pagamento.url_boleto) : null;
    if (!permitido) return null;
    return <section className={styles.pagamento} aria-label="Pagamento deste agendamento">
        <ResumoTaxa resumo={resposta?.resumo || agendamento.resumo} servico gestor={[0, 2].includes(Number(usuario?.tipo))} />
        {erro && <p role="alert">{erro}</p>}
        {!resposta ? <p role="status">Consultando pagamento…</p> : <>
            {typeof resposta.quitado === 'boolean' && <p><strong>{resposta.quitado ? 'Atendimento quitado' : resposta.parcial ? 'Pagamento parcial' : 'Pagamento pendente'}</strong> · Recebido: {dinheiro(resposta.valor_recebido)} · Saldo: {dinheiro(resposta.saldo)}</p>}
            {!resposta.cobrancas?.length && <p>Sem cobrança registrada.</p>}
            {(resposta.cobrancas || []).map(item => <div key={item.id_financeiro}><p><strong>{estadoPagamento(item)}</strong> · {dinheiroZero(item.valor)}</p>{/^ARKHE:([^ ]+)/.test(item.descricao || '') && <button disabled={ocupado} onClick={async () => { try { const id = item.descricao.match(/^ARKHE:([^ ]+)/)[1]; setPagamento(await apiFetch(`/pagamentos/pix/${encodeURIComponent(id)}`)); await atualizar(); } catch (falha) { setErro(mensagemDaApi(falha)); } }}>Consultar cobrança existente</button>}</div>)}
            <ReciboCartao recibo={reciboCartao(resposta) || reciboCartao(pagamento)} />
            {bloqueado && <p role="status">{CARTAO_INCERTO}</p>}
            {podePagar && <><CartaoArkhe total={resposta.saldo} onSubmit={pagarCartao} disabled={ocupado} /><button disabled={ocupado} onClick={() => solicitar('pix')}>Gerar cobrança Pix</button><button disabled={ocupado} onClick={() => solicitar('boleto')}>Gerar boleto Arkhé</button><button disabled={ocupado} onClick={() => solicitar('na-hora')}>Pagar no estabelecimento</button></>}
            {codigo && <div><QRCodeSVG value={String(codigo)} size={180} /><label>Código de pagamento<textarea readOnly value={String(codigo)} /></label><p>Confira o recebedor no ambiente Arkhé.</p></div>}
            {boleto && <a href={boleto} target="_blank" rel="noreferrer">Abrir boleto Arkhé</a>}
            <button disabled={ocupado} onClick={() => atualizar().catch(falha => setErro(mensagemDaApi(falha)))}>Atualizar status do pagamento</button>
            {aoConfirmar && podeConfirmarRecebimento(resposta, agendamento) && <button type="button" onClick={() => aoConfirmar({ ...agendamento, valor_a_receber: resposta.saldo ?? agendamento.valor_total }, 'receber')}>{resposta.parcial ? `Confirmar saldo recebido em dinheiro (${dinheiro(resposta.saldo)})` : 'Confirmar dinheiro recebido'}</button>}
        </>}
    </section>;
}

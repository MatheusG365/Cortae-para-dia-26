import { Link } from 'react-router-dom';
import { dinheiroZero as dinheiro, momentoCurto as momento } from '../../services/formatacao';
import Select from '../../components/Select/Select';
import { useEffect, useState } from 'react';
import { apiFetch, mensagemDaApi } from '../../services/api';
import { dataLocal, periodoDoMes as periodoInicial, podeFinalizarAtendimento } from '../../services/agendaState';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import ModalConfirmacao from '../../components/ModalConfirmacao/ModalConfirmacao';
import useDialog from '../../components/useDialog';
import styles from './PainelBarbeiro.module.css';

import { AvaliacaoResumo } from '../../components/AvaliacaoAtendimento/AvaliacaoAtendimento';
import { rotuloMedia } from '../../services/avaliacaoState';

const statusNomes = { agendado: 'Agendado', confirmado: 'Confirmado', cancelado: 'Cancelado', concluido: 'Realizado', faltou: 'Cliente faltou', remarcado: 'Remarcado' };

export default function PainelBarbeiro() {
    const [filtro, setFiltro] = useState(periodoInicial);
    const [periodo, setPeriodo] = useState(periodoInicial);
    const [dados, setDados] = useState(null);
    const [carregando, setCarregando] = useState(true);
    const [recarregar, setRecarregar] = useState(0);
    const [mensagem, setMensagem] = useState(null);
    const [erro, setErro] = useState('');
    const [acao, setAcao] = useState(null);
    const [processando, setProcessando] = useState(false);
    const [novaData, setNovaData] = useState('');
    const [novoHorario, setNovoHorario] = useState('');
    const [horarios, setHorarios] = useState([]);
    const [consultando, setConsultando] = useState(false);
    const dialogo = useDialog(acao?.tipo === 'reagendar', () => !processando && setAcao(null), processando);
    useEffect(() => {
        let ativo = true;
        const controller = new AbortController();
        const carregar = async () => {
            await Promise.resolve();
            if (!ativo) return;
            setCarregando(true); setErro('');
            try {
                const resposta = await apiFetch(`/barbeiro/painel?inicio=${periodo.inicio}&fim=${periodo.fim}`, { signal: controller.signal });
                if (ativo) setDados(resposta);
            } catch (falha) { if (ativo) { setErro(mensagemDaApi(falha)); setDados(null); } }
            finally { if (ativo) setCarregando(false); }
        };
        carregar();
        return () => { ativo = false; controller.abort(); };
    }, [periodo, recarregar]);
    useEffect(() => {
        if (acao?.tipo !== 'reagendar' || !novaData) return undefined;
        let ativo = true;
        const carregar = async () => {
            await Promise.resolve();
            if (!ativo) return;
            setConsultando(true); setNovoHorario(''); setHorarios([]);
            try {
                const item = acao.agendamento;
                const servicos = Array.isArray(item.ids_servicos) ? item.ids_servicos.join(',') : item.ids_servicos;
                const resposta = await apiFetch(`/agendamentos/horarios?id_barbearia=${item.id_barbearia}&ids_servicos=${encodeURIComponent(servicos)}&id_funcionario=${item.id_funcionario}&data=${novaData}`);
                if (ativo) setHorarios((resposta.horarios || []).filter((horario) => horario.disponivel));
            } catch (falha) { if (ativo) setMensagem({ informacao: mensagemDaApi(falha), tipo: 'erro' }); }
            finally { if (ativo) setConsultando(false); }
        };
        carregar();
        return () => { ativo = false; };
    }, [acao, novaData]);
    const executar = async () => {
        if (!acao || processando) return;
        if (acao.tipo === 'reagendar' && (!novaData || !novoHorario)) return;
        setProcessando(true);
        try {
            const endpoint = acao.tipo === 'reagendar' ? 'reagendar' : acao.tipo === 'cancelar' ? 'cancelar' : 'status-atendimento';
            const body = acao.tipo === 'reagendar' ? { data: novaData, horario: novoHorario } : acao.tipo === 'cancelar' ? {} : { status: acao.tipo };
            const resposta = await apiFetch(`/agendamentos/${acao.agendamento.id_agendamento}/${endpoint}`, { method: 'PUT', body: JSON.stringify(body) });
            setAcao(null); setMensagem(resposta.mensagem || { informacao: 'Atendimento atualizado.', tipo: 'sucesso' }); setRecarregar((valor) => valor + 1);
        } catch (falha) { setMensagem({ informacao: mensagemDaApi(falha), tipo: 'erro' }); }
        finally { setProcessando(false); }
    };
    const estatisticas = dados?.estatisticas || {};
    const cards = [['realizados', 'Realizados'], ['cancelados', 'Cancelados'], ['remarcados', 'Agendamentos remarcados'], ['faltas', 'Faltas']];
    return <main className={styles.pagina}>
        <header><p className={styles.sobre}>MEU PAINEL</p><h1>{dados?.funcionario?.nome || 'Painel do barbeiro'}</h1><p>Acompanhe seus próprios atendimentos e comissões.</p><Link to="/gestao?aba=metas">Acompanhar minhas metas →</Link></header>
        {mensagem && <MensagemCard mensagem={mensagem} fechar={() => setMensagem(null)} />}
        <form className={styles.filtro} onSubmit={(evento) => { evento.preventDefault(); if (filtro.inicio > filtro.fim) { setErro('A data inicial deve ser anterior à data final.'); return; } setPeriodo({ ...filtro }); }}>
            <label>De<input type="date" required value={filtro.inicio} onChange={(evento) => setFiltro((atual) => ({ ...atual, inicio: evento.target.value }))} /></label>
            <label>Até<input type="date" required value={filtro.fim} onChange={(evento) => setFiltro((atual) => ({ ...atual, fim: evento.target.value }))} /></label>
            <button type="submit" disabled={carregando}>Aplicar período</button><button type="button" disabled={carregando} onClick={() => setRecarregar((valor) => valor + 1)}>Atualizar</button>
        </form>
        {erro && <p role="alert" className={styles.erro}>{erro}</p>}
        {carregando && <p role="status">Carregando seu painel…</p>}
        {!carregando && dados && <>
            <section className={styles.cards} aria-label="Estatísticas dos meus atendimentos">{cards.map(([campo, titulo]) => <article key={campo}><span>{titulo}</span><strong>{estatisticas[campo] ?? '-'}</strong></article>)}</section>
            <section className={styles.avaliacoes} aria-label="Avaliações dos meus atendimentos"><div><h2>Como meus clientes avaliam o atendimento</h2><p>Notas dos seus atendimentos realizados no período consultado.</p></div><div><strong>{rotuloMedia(dados.resumo_avaliacoes?.media_nota)}</strong><span>{dados.resumo_avaliacoes?.total_avaliacoes ?? 0} avaliação(ões)</span></div></section>
            <section className={styles.financeiro} aria-label="Valores do período">
                <article><h2>Atendimentos realizados</h2><strong>{dinheiro(estatisticas.valor_arrecadado)}</strong><p>Valor bruto dos serviços realizados. Não representa necessariamente dinheiro recebido.</p></article>
                <article><h2>Valor recebido</h2><strong>{dinheiro(estatisticas.valor_recebido)}</strong><p>Pagamentos confirmados no período.</p></article>
                <article><h2>Comissão calculada</h2><strong>{dinheiro(estatisticas.comissao_total)}</strong><p>Regra configurada: {dados.funcionario?.comissao_tipo === 'fixa' ? `${dinheiro(dados.funcionario?.comissao_valor)} por atendimento` : `${dados.funcionario?.comissao_valor ?? dados.funcionario?.comissao_percentual ?? 0}%`}. O cálculo não confirma um repasse bancário.</p></article>
            </section>
            {estatisticas.valores_historicos_ausentes > 0 && <p role="status">{estatisticas.valores_historicos_ausentes} atendimento(s) antigo(s) não têm valor registrado e estão fora do total financeiro. A barbearia precisa informar esses valores.</p>}
            <section className={styles.secao}><h2>Meus agendamentos</h2><div className={styles.agenda}>{(dados.agendamentos || []).map((item) => <article key={item.id_agendamento}>
                <div><h3>{item.cliente_nome || 'Cliente'}</h3><p>{momento(item.inicio_em)} até {momento(item.fim_em)}</p><p>{(item.servicos_nomes || []).join(' + ')}</p>{item.corte_nome && <p><strong>Corte: </strong>{item.corte_nome}</p>}<p>{statusNomes[item.status] || item.status} · {item.valor_total == null ? 'Valor não registrado' : dinheiro(item.valor_total)}</p>{item.valor_historico_disponivel === false && <p>A barbearia precisa registrar o valor antes de concluir este atendimento.</p>}<AvaliacaoResumo avaliacao={item.avaliacao} /></div>
                <div className={styles.acoes}>{podeFinalizarAtendimento(item) && <><button type="button" disabled={item.valor_total == null || item.valor_historico_disponivel === false} onClick={() => setAcao({ tipo: 'concluido', agendamento: item })}>Marcar realizado</button><button type="button" onClick={() => setAcao({ tipo: 'faltou', agendamento: item })}>Registrar falta</button></>}
                    {item.permite_cancelar === true && <button type="button" onClick={() => setAcao({ tipo: 'cancelar', agendamento: item })}>Cancelar</button>}
                    {item.permite_reagendar === true && <button type="button" onClick={() => { setNovaData(''); setNovoHorario(''); setHorarios([]); setAcao({ tipo: 'reagendar', agendamento: item }); }}>Remarcar</button>}
                </div>
            </article>)}</div>{!dados.agendamentos?.length && <p>Nenhum atendimento neste período.</p>}</section>
            <section className={styles.secao}><h2>Minhas comissões</h2><div className={styles.agenda}>{(dados.comissoes || []).map((item, indice) => <article key={item.id_agendamento || indice}><div><h3>{item.cliente_nome || `Atendimento ${item.id_agendamento || ''}`}</h3><p>{momento(item.registrado_em || item.inicio_em || item.data)}</p><p>Base: {dinheiro(item.valor_base ?? item.valor_total)} · {item.tipo === 'fixa' ? `Fixa de ${dinheiro(item.valor_configurado)}` : `${item.percentual ?? item.comissao_percentual ?? 0}%`}</p><strong>{dinheiro(item.valor_comissao ?? item.comissao)}</strong></div></article>)}</div>{!dados.comissoes?.length && <p>Nenhuma comissão calculada neste período.</p>}</section>
        </>}
        <ModalConfirmacao aberto={Boolean(acao && acao.tipo !== 'reagendar')} titulo={acao?.tipo === 'cancelar' ? 'Cancelar atendimento' : 'Atualizar atendimento'} mensagem={`Confirmar ${acao?.tipo === 'concluido' ? 'atendimento realizado' : acao?.tipo === 'faltou' ? 'falta do cliente' : 'cancelamento'} de ${acao?.agendamento?.cliente_nome || 'cliente'}?`} processando={processando} perigo={acao?.tipo !== 'concluido'} aoConfirmar={executar} aoCancelar={() => setAcao(null)} />
        {acao?.tipo === 'reagendar' && <div className={styles.overlay}><section ref={dialogo} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Remarcar atendimento" className={styles.modal}>
            <h2>Remarcar atendimento</h2>{acao.agendamento.corte_nome && <p><strong>Corte: </strong>{acao.agendamento.corte_nome}</p>}<label>Nova data<input type="date" min={dataLocal()} value={novaData} onChange={(evento) => setNovaData(evento.target.value)} disabled={processando} /></label>
            <label>Horário disponível<Select value={novoHorario} onChange={(evento) => setNovoHorario(evento.target.value)} disabled={processando || consultando}><option value="">{consultando ? 'Consultando horários…' : 'Selecione'}</option>{horarios.map((item) => <option key={item.horario} value={item.horario}>{item.horario} até {item.fim}</option>)}</Select></label>
            <div className={styles.acoes}><button type="button" disabled={processando} onClick={() => setAcao(null)}>Voltar</button><button type="button" disabled={processando || consultando || !novoHorario} onClick={executar}>{processando ? 'Salvando…' : 'Confirmar remarcação'}</button></div>
        </section></div>}
    </main>;
}

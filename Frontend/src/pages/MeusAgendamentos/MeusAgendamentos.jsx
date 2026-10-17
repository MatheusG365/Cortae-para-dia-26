import { dataAgendamento as formatarData, horaAgendamento as formatarHora } from '../../services/formatacao';
import { dataLocal as dataAtualLocal, rotuloStatusAgendamento } from '../../services/agendaState';
import { useEffect, useRef, useState } from 'react';

import {
    FiCalendar,
    FiClock,
    FiX,
    FiInfo
} from 'react-icons/fi';

import estilo from './MeusAgendamento.module.css';
import { urlDaApi, apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import ListaEspera from '../../components/ListaEspera/ListaEspera';
import PagamentoAgendamento from '../../components/PagamentoAgendamento/PagamentoAgendamento';

import AvaliacaoAtendimento, { AvaliacaoResumo } from '../../components/AvaliacaoAtendimento/AvaliacaoAtendimento';
import { atualizarAvaliacao } from '../../services/avaliacaoState';

const STATUS_FINALIZADOS = ['Cancelado', 'Concluído', 'Cliente faltou'];


// =====================================================
// FORMATAÇÃO (API -> tela)
// =====================================================




function paraCard(agendamento) {
    return {
        ...agendamento,
        id: agendamento.id_agendamento,
        barbearia: agendamento.barbearia_nome,
        servico: (agendamento.servicos_nomes || []).join(' + ') || '-',
        data: formatarData(agendamento.inicio_em),
        horario: `${formatarHora(agendamento.inicio_em)} - ${formatarHora(agendamento.fim_em)}`,
        valor: Number(agendamento.resumo?.valor_total_cliente ?? agendamento.valor_total ?? 0),
        status: rotuloStatusAgendamento(agendamento.status),
        imagem: '',
    };
}


// =====================================================
// COMPONENTE: ABAS
// =====================================================

function AbasAgendamento({ abaAtiva, alterarAba }) {

    return (
        <div className={estilo.abas}>

            <button
                className={abaAtiva === 'proximos' ? estilo.abaAtiva : ''}
                onClick={() => alterarAba('proximos')}
            >
                Próximos
            </button>

            <button
                className={abaAtiva === 'historico' ? estilo.abaAtiva : ''}
                onClick={() => alterarAba('historico')}
            >
                Histórico
            </button>

        </div>
    );
}


// =====================================================
// COMPONENTE: CARD DE AGENDAMENTO
// =====================================================

function CardAgendamento({
                             agendamento,
                             cancelarAgendamento,
                             reagendarAgendamento,
                             abrirDetalhes,
                             avaliarAtendimento
                         }) {

    const [imagemCarregada, setImagemCarregada] = useState(false);

    const statusConfirmado = agendamento.status === 'Agendado';
    const statusCancelado = agendamento.status === 'Cancelado';

    return (
        <article className={estilo.cardAgendamento}>

            {/* IMAGEM DA BARBEARIA */}

            <div className={estilo.imagemContainer}>

                {!imagemCarregada && agendamento.imagem && (
                    <div className={estilo.placeholderImagem}></div>
                )}

                {agendamento.imagem ? (
                    <img
                        src={agendamento.imagem}
                        alt={`Interior da ${agendamento.barbearia}`}
                        className={imagemCarregada ? estilo.imagemVisivel : ''}
                        onLoad={() => setImagemCarregada(true)}
                    />
                ) : (
                    <div className={estilo.placeholderImagem}></div>
                )}

            </div>


            {/* INFORMAÇÕES */}

            <div className={estilo.informacoes}>

                <h2>{agendamento.barbearia}</h2>

                <p className={estilo.servico}>
                    {agendamento.servico}
                </p>

                {agendamento.funcionario_nome && <p className={estilo.servico}>Profissional: {agendamento.funcionario_nome}</p>}
                <div className={estilo.detalhesData}>

                    <span>
                        <FiCalendar />
                        {agendamento.data}
                    </span>

                    <span>
                        <FiClock />
                        {agendamento.horario}
                    </span>

                </div>
                <AvaliacaoResumo avaliacao={agendamento.avaliacao} />

            </div>


            {/* VALOR E AÇÕES */}

            <div className={estilo.acoesAgendamento}>

                <div className={estilo.valorStatus}>

                    <strong>
                        R$ {agendamento.valor.toFixed(2).replace('.', ',')}
                    </strong>

                    <span
                        className={`
                            ${estilo.status}
                            ${statusConfirmado ? estilo.concluido : ''}
                            ${statusCancelado ? estilo.cancelado : ''}
                        `}
                    >
                        {agendamento.status}
                    </span>

                </div>

                <div className={estilo.pagamentoCard}>
                    <PagamentoAgendamento agendamento={agendamento} />
                </div>

                <div className={estilo.botoesCard}>
                    {agendamento.pode_avaliar === true && <button type="button" className={estilo.botaoAvaliar} onClick={(evento) => avaliarAtendimento(agendamento, evento.currentTarget)}>{agendamento.avaliacao ? 'Editar avaliação' : 'Avaliar atendimento'}</button>}

                    <button
                        className={estilo.botaoDetalhes}
                        onClick={(evento) => abrirDetalhes(agendamento, evento.currentTarget)}
                    >
                        Ver Detalhes
                    </button>

                    {statusConfirmado && (
                        <>
                            <button
                                className={estilo.botaoDetalhes}
                                onClick={() => reagendarAgendamento(agendamento)}
                            >
                                Reagendar
                            </button>

                            <button
                                className={estilo.botaoCancelar}
                                onClick={() => cancelarAgendamento(agendamento.id)}
                            >
                                Cancelar
                            </button>
                        </>
                    )}

                </div>

            </div>

        </article>
    );
}


// =====================================================
// COMPONENTE: MODAL DE DETALHES
// =====================================================

function ModalDetalhes({ agendamento, fechar, avaliarAtendimento }) {

    if (!agendamento) return null;

    return (
        <div
            className={estilo.overlay}
            onClick={fechar}
        >

            <div
                className={estilo.modal}
                onClick={(e) => e.stopPropagation()}
            >

                <button
                    className={estilo.fecharModal}
                    onClick={fechar}
                    aria-label="Fechar detalhes"
                >
                    <FiX />
                </button>

                <FiInfo className={estilo.iconeModal} />

                <h2>Detalhes do Agendamento</h2>

                {(agendamento.corte_imagem_url || agendamento.visagismo_foto_url) && (
                    <div className={estilo.imagensModal}>
                        {agendamento.corte_imagem_url && (
                            <figure>
                                <img src={urlDaApi(agendamento.corte_imagem_url)} alt={agendamento.corte_nome || 'Corte escolhido'} />
                                <figcaption>Corte escolhido</figcaption>
                            </figure>
                        )}
                        {agendamento.visagismo_foto_url && (
                            <figure>
                                <img src={urlDaApi(agendamento.visagismo_foto_url)} alt="Foto do visagismo" />
                                <figcaption>Sua foto no visagismo</figcaption>
                            </figure>
                        )}
                    </div>
                )}

                <div className={estilo.linhaModal}>
                    <span>Barbearia</span>
                    <strong>{agendamento.barbearia}</strong>
                </div>

                <div className={estilo.linhaModal}>
                    <span>Serviço</span>
                    <strong>{agendamento.servico}</strong>
                </div>

                {agendamento.corte_nome && (
                    <div className={estilo.linhaModal}>
                        <span>Corte</span>
                        <strong>{agendamento.corte_nome}</strong>
                    </div>
                )}

                <div className={estilo.linhaModal}>
                    <span>Data</span>
                    <strong>{agendamento.data}</strong>
                </div>

                <div className={estilo.linhaModal}>
                    <span>Horário</span>
                    <strong>{agendamento.horario}</strong>
                </div>

                <div className={estilo.linhaModal}>
                    <span>Valor</span>
                    <strong>
                        R$ {agendamento.valor.toFixed(2).replace('.', ',')}
                    </strong>
                </div>

                <AvaliacaoResumo avaliacao={agendamento.avaliacao} />
                {agendamento.pode_avaliar === true && <button type="button" className={estilo.botaoFechar} onClick={() => avaliarAtendimento(agendamento)}>{agendamento.avaliacao ? 'Editar avaliação' : 'Avaliar atendimento'}</button>}
                <button
                    className={estilo.botaoFechar}
                    onClick={fechar}
                >
                    Fechar
                </button>

            </div>

        </div>
    );
}


// =====================================================
// PÁGINA PRINCIPAL
// =====================================================

function MeusAgendamentos() {

    const [abaAtiva, setAbaAtiva] = useState('proximos');

    const [agendamentos, setAgendamentos] = useState([]);
    const [revisaoPagamentos, setRevisaoPagamentos] = useState(0);

    const [carregando, setCarregando] = useState(true);

    const [erro, setErro] = useState('');

    const [mensagem, setMensagem] = useState(null);

    const [agendamentoSelecionado, setAgendamentoSelecionado] =
        useState(null);

    const [reagendando, setReagendando] = useState(null);

    const [cancelando, setCancelando] = useState(null);
    const [avaliando, setAvaliando] = useState(null);
    const focoDetalhes = useRef(null);
    const focoAvaliacao = useRef(null);
    const abrirAvaliacao = (item, botao) => { focoAvaliacao.current = agendamentoSelecionado ? focoDetalhes.current : botao; setAgendamentoSelecionado(null); setAvaliando(item); };

    const [novaData, setNovaData] = useState('');

    const [novoHorario, setNovoHorario] = useState('');

    const [dataMinima] = useState(dataAtualLocal);

    const [horariosReagendamento, setHorariosReagendamento] = useState([]);

    const [carregandoHorariosReagendamento, setCarregandoHorariosReagendamento] = useState(false);

    const [erroHorariosReagendamento, setErroHorariosReagendamento] = useState('');

    const [processando, setProcessando] = useState(false);


    async function carregar() {
        setCarregando(true);
        setErro('');
        try {
            const dados = await apiFetch('/agendamentos');
            setAgendamentos((dados.agendamentos || []).map(paraCard));
            setRevisaoPagamentos((revisao) => revisao + 1);
        } catch (error) {
            setErro(mensagemDaApi(error));
            setAgendamentos([]);
        } finally {
            setCarregando(false);
        }
    }

    useEffect(() => {
        queueMicrotask(carregar);
    }, []);


    // =================================================
    // CANCELAR AGENDAMENTO (avisa a barbearia por e-mail)
    // =================================================

    function cancelarAgendamento(id) {

        // Abre o modal de confirmação (substitui o window.confirm nativo)
        const agendamento = agendamentos.find((item) => item.id === id);

        setCancelando(agendamento || { id });

        setMensagem(null);

    }


    async function confirmarCancelamento() {

        if (!cancelando) return;

        setProcessando(true);

        try {
            const resposta = await apiFetch(`/agendamentos/${cancelando.id}/cancelar`, { method: 'PUT', body: '{}' });
            setMensagem(resposta.mensagem || { informacao: 'Agendamento cancelado.', tipo: 'sucesso' });
            setCancelando(null);
            await carregar();
        } catch (error) {
            setMensagem({ informacao: mensagemDaApi(error), tipo: 'erro' });
            setCancelando(null);
        } finally {
            setProcessando(false);
        }
    }


    // =================================================
    // REAGENDAR (avisa a barbearia por e-mail)
    // =================================================

    function abrirReagendar(agendamento) {
        const [data] = String(agendamento.inicio_em || '').split('T');
        const hoje = dataAtualLocal();
        setReagendando(agendamento);
        setNovaData(data && data >= hoje ? data : hoje);
        setNovoHorario(formatarHora(agendamento.inicio_em));
        setHorariosReagendamento([]);
        setErroHorariosReagendamento('');
        setMensagem(null);
    }

    useEffect(() => {
        let ativo = true;

        async function carregarHorariosReagendamento() {
            if (!reagendando || !novaData) return;
            const idsServicos = (reagendando.servicos || []).join(',');
            if (!reagendando.id_barbearia || !idsServicos) {
                setErroHorariosReagendamento('Não foi possível identificar os serviços deste agendamento.');
                return;
            }

            setCarregandoHorariosReagendamento(true);
            setErroHorariosReagendamento('');
            try {
                const funcionario = reagendando.id_funcionario
                    ? `&id_funcionario=${encodeURIComponent(reagendando.id_funcionario)}`
                    : '';
                const resposta = await apiFetch(
                    `/agendamentos/horarios?id_barbearia=${encodeURIComponent(reagendando.id_barbearia)}&ids_servicos=${encodeURIComponent(idsServicos)}&data=${encodeURIComponent(novaData)}${funcionario}`
                );
                if (!ativo) return;
                const disponiveis = (resposta.horarios || []).filter((horario) => horario.disponivel);
                setHorariosReagendamento(disponiveis);
                setNovoHorario((atual) => disponiveis.some((horario) => horario.horario === atual) ? atual : '');
            } catch (error) {
                if (ativo) {
                    setHorariosReagendamento([]);
                    setNovoHorario('');
                    setErroHorariosReagendamento(mensagemDaApi(error));
                }
            } finally {
                if (ativo) setCarregandoHorariosReagendamento(false);
            }
        }

        carregarHorariosReagendamento();
        return () => { ativo = false; };
    }, [reagendando, novaData]);

    async function confirmarReagendar() {
        if (!reagendando) return;
        if (!novaData || !novoHorario) {
            setMensagem({ informacao: 'Informe a nova data e o novo horário.', tipo: 'erro' });
            return;
        }
        setProcessando(true);
        try {
            const resposta = await apiFetch(`/agendamentos/${reagendando.id}/reagendar`, {
                method: 'PUT',
                body: JSON.stringify({ data: novaData, horario: novoHorario })
            });
            setMensagem(resposta.mensagem || { informacao: 'Agendamento reagendado.', tipo: 'sucesso' });
            setReagendando(null);
            await carregar();
        } catch (error) {
            setMensagem({ informacao: mensagemDaApi(error), tipo: 'erro' });
        } finally {
            setProcessando(false);
        }
    }


    // =================================================
    // ABRIR DETALHES
    // =================================================

    function abrirDetalhes(agendamento, botao) {
        focoDetalhes.current = botao;

        setAgendamentoSelecionado(agendamento);

    }


    // =================================================
    // LISTA ATUAL
    // =================================================

    const listaAtual = abaAtiva === 'proximos'
        ? agendamentos.filter((item) => !STATUS_FINALIZADOS.includes(item.status))
        : agendamentos.filter((item) => STATUS_FINALIZADOS.includes(item.status));


    return (

        <div className={estilo.pagina}>



            <main className={estilo.conteudo}>

                {/* TÍTULO */}

                <h1 className={estilo.titulo}>
                    Meus Agendamentos
                </h1>
                <ListaEspera />


                {/* ABAS */}

                <AbasAgendamento
                    abaAtiva={abaAtiva}
                    alterarAba={setAbaAtiva}
                />


                {erro && (
                    <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />
                )}

                {mensagem && (
                    <MensagemCard mensagem={mensagem} fechar={() => setMensagem(null)} />
                )}


                {/* CARDS */}

                <section className={estilo.listaAgendamentos}>

                    {carregando ? (

                        <p>Carregando agendamentos…</p>

                    ) : listaAtual.length > 0 ? (

                        listaAtual.map((agendamento) => (

                            <CardAgendamento
                                key={`${agendamento.id}:${revisaoPagamentos}`}
                                agendamento={agendamento}
                                cancelarAgendamento={cancelarAgendamento}
                                reagendarAgendamento={abrirReagendar}
                                abrirDetalhes={abrirDetalhes}
                                avaliarAtendimento={abrirAvaliacao}
                            />

                        ))

                    ) : (

                        <div className={estilo.semAgendamentos}>

                            <FiCalendar />

                            <h2>
                                Nenhum agendamento encontrado
                            </h2>

                            <p>
                                Seus agendamentos aparecerão aqui.
                            </p>

                        </div>

                    )}

                </section>

            </main>




            {/* MODAL */}

            <ModalDetalhes
                agendamento={agendamentoSelecionado}
                fechar={() => setAgendamentoSelecionado(null)}
                avaliarAtendimento={abrirAvaliacao}
            />

            {avaliando && <AvaliacaoAtendimento key={avaliando.id} agendamento={avaliando} focoAoFechar={focoAvaliacao} aoFechar={() => setAvaliando(null)} aoSalvar={(resposta) => {
                setAgendamentos((itens) => atualizarAvaliacao(itens, avaliando.id, resposta));
                setAvaliando(null);
                setMensagem({ informacao: 'Avaliação salva. Obrigado por compartilhar sua experiência.', tipo: 'sucesso' });
            }} />}

            {reagendando && (
                <div className={estilo.overlay} onClick={() => setReagendando(null)}>
                    <div className={estilo.modal} onClick={(e) => e.stopPropagation()}>
                        <h2>Reagendar</h2>
                        <p>A barbearia será avisada por e-mail.</p>
                        <label>Nova data<input type="date" min={dataMinima} value={novaData} onChange={(e) => setNovaData(e.target.value)} /></label>
                        <div className={estilo.horariosReagendamento}>
                            <strong>Horários disponíveis</strong>
                            {carregandoHorariosReagendamento && <p>Consultando horários…</p>}
                            {erroHorariosReagendamento && <p className={estilo.erroHorario}>{erroHorariosReagendamento}</p>}
                            {!carregandoHorariosReagendamento && !erroHorariosReagendamento && (
                                horariosReagendamento.length ? (
                                    <div className={estilo.gradeHorarios}>
                                        {horariosReagendamento.map((horario) => (
                                            <button type="button" key={horario.horario}
                                                className={novoHorario === horario.horario ? estilo.horarioSelecionado : ''}
                                                onClick={() => setNovoHorario(horario.horario)}>
                                                {horario.horario}
                                                {horario.fim && <small>até {horario.fim}</small>}
                                            </button>
                                        ))}
                                    </div>
                                ) : <p>Nenhum horário disponível nesta data.</p>
                            )}
                        </div>
                        <div className={estilo.modalAcoes}>
                            <button type="button" onClick={() => setReagendando(null)}>Voltar</button>
                            <button type="button" disabled={processando || !novoHorario} onClick={confirmarReagendar}>
                                {processando ? 'Enviando…' : 'Confirmar'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {cancelando && (
                <div className={estilo.overlay} onClick={() => !processando && setCancelando(null)}>
                    <div className={estilo.modal} onClick={(e) => e.stopPropagation()}>
                        <h2>Cancelar agendamento</h2>
                        <p>Deseja realmente cancelar este agendamento? A barbearia será avisada por e-mail.</p>
                        <div className={estilo.resumoCancelamento}>
                            <strong>{cancelando.barbearia}</strong>
                            <span>{cancelando.servico}</span>
                            <span>{cancelando.data} · {cancelando.horario}</span>
                        </div>
                        <div className={estilo.modalAcoes}>
                            <button type="button" disabled={processando} onClick={() => setCancelando(null)}>Voltar</button>
                            <button type="button" className={estilo.botaoConfirmarCancelamento} disabled={processando} onClick={confirmarCancelamento}>
                                {processando ? 'Cancelando…' : 'Confirmar cancelamento'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

        </div>

    );
}

export default MeusAgendamentos;


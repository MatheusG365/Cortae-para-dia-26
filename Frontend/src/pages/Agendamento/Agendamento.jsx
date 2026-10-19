import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import styles from './Agendamento.module.css';
import { dataLocal as isoData, podeEntrarNaEspera } from '../../services/agendaState';
import { dinheiro } from '../../services/gestaoState';
import { dadosEscolhaCorte, rotuloEscolhaCorte } from '../../services/escolhaCorte';
import useTermosUso from '../../services/useTermosUso';
import TermosAceite from '../../components/TermosAceite/TermosAceite';
import ResumoTaxa from '../../components/ResumoTaxa/ResumoTaxa';
import Select from '../../components/Select/Select';
import useResumoOperacao from '../../services/useResumoOperacao';
import PagamentoAgendamento from '../../components/PagamentoAgendamento/PagamentoAgendamento';
import { useAuth } from '../../contexts/useAuth';
import { contextoProfissionais, profissionaisDaResposta, funcionarioValido, corpoAgendamento, rotaAgendaGestao, idsServicosAgendamento } from '../../services/agendaProfissionaisState';

const nomesSemana = ['DOM', 'SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB'];
const nomesMes = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
const HORARIOS_POR_PAGINA = 12;

function Agendamento() {
    const [params] = useSearchParams();
    const { usuario } = useAuth();
    const tipo = Number(usuario?.tipo);
    if ([0, 2, 3].includes(tipo)) return <main className={styles.agendamentoPage}>
        <section className={styles.encaminhamentoGestao}>
            <h1>{tipo === 3 ? 'Sua agenda profissional' : 'Agendar para um cliente'}</h1>
            <p>{tipo === 3 ? 'Consulte os atendimentos da sua agenda na área de gestão.' : 'Escolha o cliente na agenda de gestão para registrar o atendimento com os dados corretos.'}</p>
            <Link className={styles.btnConfirmarModal} to={rotaAgendaGestao(tipo, params.get('barbearia'))}>{tipo === 3 ? 'ABRIR MINHA AGENDA' : 'AGENDAR PARA UM CLIENTE'}</Link>
        </section>
    </main>;
    const chave = JSON.stringify([usuario?.id_usuario ?? usuario?.id, contextoProfissionais(params.get('barbearia'), params.get('servicos')), params.get('funcionario') || params.get('id_funcionario'), params.get('corte'), params.get('visagismo'), params.get('escolha_corte')]);
    return <AgendamentoCliente key={chave} />;
}

function AgendamentoCliente() {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const idBarbearia = params.get('barbearia');
    const idsServicos = idsServicosAgendamento(params.get('servicos')).join(',');
    const idCorte = params.get('corte');
    const idVisagismo = params.get('visagismo');
    const escolhaCorte = params.get('escolha_corte') || (idCorte ? 'catalogo' : null);
    const [inicioSemana, setInicioSemana] = useState(() => {
        const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
        const solicitada = new Date(`${params.get('data') || ''}T00:00:00`);
        return !Number.isNaN(solicitada.getTime()) && solicitada >= hoje ? solicitada : hoje;
    });
    const [diaSelecionado, setDiaSelecionado] = useState(0);
    const [consultaHorarios, setConsultaHorarios] = useState(null);
    const [paginaHorarios, setPaginaHorarios] = useState(1);
    const [selecaoHorario, setSelecaoHorario] = useState(null);
    const [selecaoEspera, setSelecaoEspera] = useState(null);
    const [entrandoEspera, setEntrandoEspera] = useState(false);
    const [profissionais, setProfissionais] = useState([]);
    const [profissionaisCarregados, setProfissionaisCarregados] = useState(false);
    const [erroProfissionais, setErroProfissionais] = useState('');
    const [revisaoProfissionais, setRevisaoProfissionais] = useState(0);
    const [diasAbertos, setDiasAbertos] = useState(null);
    const [idFuncionario, setIdFuncionario] = useState(params.get('funcionario') || params.get('id_funcionario') || '');
    const [ocupado, setCarregando] = useState(false);
    const [erro, setErro] = useState('');
    const [sucesso, setSucesso] = useState('');
    const [idAgendamento, setIdAgendamento] = useState(null);
    const [valorTotal, setValorTotal] = useState(null);
    const [modalResumo, setModalResumo] = useState(false); // confirmação do horário
    const [modalPagamento, setModalPagamento] = useState(null); // null | 'metodos' | 'detalhe'
    const [recarregar, setRecarregar] = useState(0); // força recarregar horários (ex.: após cancelar)
    const [resumoAgendamento, setResumoAgendamento] = useState(null);
    const [modalCancelar, setModalCancelar] = useState(false); // confirmação de cancelamento

    const dias = useMemo(() => Array.from({ length: 7 }, (_, indice) => {
        const data = new Date(inicioSemana);
        data.setHours(0, 0, 0, 0);
        data.setDate(data.getDate() + indice);
        const chave = ['domingo', 'segunda', 'terca', 'quarta', 'quinta', 'sexta', 'sabado'][data.getDay()];
        return {
            data,
            iso: isoData(data),
            semana: nomesSemana[data.getDay()],
            numero: String(data.getDate()).padStart(2, '0'),
            mes: nomesMes[data.getMonth()],
            chave,
            aberto: !Array.isArray(diasAbertos) || diasAbertos.includes(chave)
        };
    }), [inicioSemana, diasAbertos]);
    const diaAtual = dias[diaSelecionado] || dias[0];
    const dataSelecionada = diaAtual?.iso;
    const diaAberto = diaAtual?.aberto;
    const contextoEspera = JSON.stringify([idBarbearia, idsServicos, dataSelecionada, idFuncionario, idCorte, idVisagismo, escolhaCorte, recarregar, revisaoProfissionais]);
    const horarioEspera = selecaoEspera?.contexto === contextoEspera ? selecaoEspera.horario : null;
    const contextoDisponibilidade = JSON.stringify([idBarbearia, idsServicos, dataSelecionada, idFuncionario, recarregar, revisaoProfissionais]);
    const consultaAtual = profissionaisCarregados && consultaHorarios?.contexto === contextoDisponibilidade ? consultaHorarios : null;
    const horarios = consultaAtual?.horarios || [];
    const duracao = consultaAtual?.duracao ?? null;
    const orcamento = consultaAtual?.orcamento ?? null;
    const consultandoHorarios = profissionaisCarregados && diaAberto && !consultaAtual;
    const carregando = ocupado || consultandoHorarios;
    const horarioSelecionado = selecaoHorario?.contexto === contextoDisponibilidade ? selecaoHorario.horario : null;
    const setHorarioSelecionado = horario => setSelecaoHorario(horario ? { contexto: contextoDisponibilidade, horario } : null);
    const resumoAberto = modalResumo === contextoDisponibilidade;
    const previa = useResumoOperacao('/agendamentos/resumo', corpoAgendamento(idBarbearia, idsServicos, idFuncionario), resumoAberto && orcamento?.valor_total != null);
    const termos = useTermosUso({ versaoEsperada: previa.resumo?.termos_versao });


    useEffect(() => {
        if (!idBarbearia || !idsServicos) return undefined;
        const controller = new AbortController();
        apiFetch(`/barbearias/${encodeURIComponent(idBarbearia)}/funcionarios?servicos=${encodeURIComponent(idsServicos)}`, { signal: controller.signal })
            .then(dados => {
                if (controller.signal.aborted) return;
                const lista = profissionaisDaResposta(dados, idsServicos);
                setProfissionais(lista);
                setIdFuncionario(atual => funcionarioValido(atual, lista));
                setDiasAbertos(Array.isArray(dados.dias_abertos) ? dados.dias_abertos : null);
                setErroProfissionais('');
                setProfissionaisCarregados(true);
            })
            .catch(error => { if (!controller.signal.aborted) setErroProfissionais(mensagemDaApi(error)); });
        return () => controller.abort();
    }, [idBarbearia, idsServicos, revisaoProfissionais]);

    useEffect(() => {
        if (!idBarbearia || !idsServicos || !dataSelecionada || !profissionaisCarregados || diaAberto === false) return undefined;
        const controller = new AbortController();
        const query = new URLSearchParams({ id_barbearia: idBarbearia, ids_servicos: idsServicos, data: dataSelecionada });
        if (idFuncionario) query.set('id_funcionario', idFuncionario);
        apiFetch(`/agendamentos/horarios?${query}`, { signal: controller.signal })
            .then(dados => {
                if (controller.signal.aborted) return;
                setConsultaHorarios({
                    contexto: contextoDisponibilidade,
                    horarios: dados.horarios || [],
                    duracao: dados.duracao_minutos,
                    orcamento: { valor_total: dados.valor_total, servicos: dados.servicos || [], generos_servico: dados.generos_servico || (dados.servicos || []).map(servico => servico.genero).filter(Boolean) }
                });
            })
            .catch(error => {
                if (!controller.signal.aborted) setConsultaHorarios({ contexto: contextoDisponibilidade, erro: mensagemDaApi(error) });
            });
        return () => controller.abort();
    }, [idBarbearia, idsServicos, dataSelecionada, idFuncionario, diaAberto, profissionaisCarregados, contextoDisponibilidade]);

    const trocarProfissional = id => {
        setIdFuncionario(id);
        setSelecaoHorario(null);
        setSelecaoEspera(null);
        setModalResumo(false);
        setPaginaHorarios(1);
        setErro('');
    };
    const tentarProfissionais = () => {
        setProfissionaisCarregados(false);
        setErroProfissionais('');
        setSelecaoHorario(null);
        setSelecaoEspera(null);
        setModalResumo(false);
        setRevisaoProfissionais(valor => valor + 1);
    };

    const mudarSemana = (direcao) => {
        const proxima = new Date(inicioSemana);
        proxima.setDate(proxima.getDate() + (direcao * 7));
        const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
        if (proxima >= hoje) {
            setInicioSemana(proxima); setDiaSelecionado(0);
            setSelecaoHorario(null); setSelecaoEspera(null); setModalResumo(false); setPaginaHorarios(1);
        }
    };

    const trocarDia = indice => {
        setDiaSelecionado(indice);
        setSelecaoHorario(null); setSelecaoEspera(null); setModalResumo(false); setPaginaHorarios(1);
    };

    const abrirResumo = () => {
        if (!horarioSelecionado) { setErro('Selecione um horário disponível.'); return; }
        if (orcamento?.valor_total == null) { setErro('Aguarde a consulta do valor antes de confirmar.'); return; }
        setErro('');
        setModalResumo(contextoDisponibilidade);
    };
    const entrarNaEspera = async () => {
        if (!horarioEspera || entrandoEspera) return;
        const item = horarios.find((horario) => horario.horario === horarioEspera);
        if (!podeEntrarNaEspera(item)) return;
        setEntrandoEspera(true); setErro('');
        try {
            const dados = await apiFetch('/agendamentos/lista-espera', { method: 'POST', body: JSON.stringify({
                ...corpoAgendamento(idBarbearia, idsServicos, idFuncionario), data: dataSelecionada,
                horario: horarioEspera,
                ...dadosEscolhaCorte({ escolhaCorte, idCorte, idVisagismo })
            }) });
            setSucesso(dados.mensagem?.informacao || 'Você entrou na lista de espera. Avisaremos por e-mail quando o horário for liberado. O aviso não reserva o horário.');
            setSelecaoEspera(null);
        } catch (falha) { setErro(mensagemDaApi(falha)); }
        finally { setEntrandoEspera(false); }
    };

    const horarioResumo = horarios.find((item) => item.horario === horarioSelecionado) || null;
    const totalPaginasHorarios = Math.max(1, Math.ceil(horarios.length / HORARIOS_POR_PAGINA));
    const paginaHorariosSegura = Math.min(paginaHorarios, totalPaginasHorarios);
    const horariosDaPagina = horarios.slice(
        (paginaHorariosSegura - 1) * HORARIOS_POR_PAGINA,
        paginaHorariosSegura * HORARIOS_POR_PAGINA
    );

    const nomeProfissional = idFuncionario
        ? (profissionais.find((p) => String(p.id_funcionario) === String(idFuncionario))?.nome || 'Profissional selecionado')
        : 'Sem profissional definido';
    const descricaoEscolhaCorte = rotuloEscolhaCorte(escolhaCorte, orcamento?.generos_servico || []);

    const voltarParaBarbearia = () => {
        // Voltar para a barbearia não é cancelamento: a reserva permanece ativa.
        navigate(`/estabelecimento?usuario=${encodeURIComponent(idBarbearia)}`);
    };

    const confirmarAgendamento = async () => {
        if (!horarioSelecionado) { setErro('Selecione um horário disponível.'); return; }
        if (!previa.resumo) { setErro('Aguarde a confirmação dos valores antes de continuar.'); return; }
        setCarregando(true); setErro('');
        try {
            await termos.aceitar();
            const dados = await apiFetch('/agendamentos', {
                method: 'POST',
                body: JSON.stringify({
                    ...corpoAgendamento(idBarbearia, idsServicos, idFuncionario),
                    data: diaAtual.iso, horario: horarioSelecionado, confirmacao_resumo: previa.resumo.confirmacao_resumo,
                    ...dadosEscolhaCorte({ escolhaCorte, idCorte, idVisagismo })
                })
            });
            setSucesso(dados.mensagem?.informacao || 'Agendamento realizado!');
            setIdAgendamento(dados.agendamento?.id_agendamento || null);
            setValorTotal(dados.agendamento?.resumo?.valor_total_cliente ?? dados.agendamento?.valor_total ?? null);
            setResumoAgendamento(dados.agendamento?.resumo ?? null);
            // Fecha o resumo e abre o modal de pagamento
            setModalResumo(false);
            setModalPagamento('metodos');
        } catch (error) { if (error.status === 409) previa.recarregar(); setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    // Fechar o pagamento apenas fecha o modal. O cancelamento precisa ser uma
    // ação explícita no botão "Cancelar agendamento".
    const sairDoPagamento = () => {
        setModalPagamento(null);
        setModalResumo(false);
    };

    const cancelarAgendamentoCliente = async () => {
        if (!idAgendamento) return;
        setModalCancelar(true);
    };

    const confirmarCancelamento = async () => {
        if (!idAgendamento) return;
        setModalCancelar(false);
        setCarregando(true); setErro('');
        try {
            const resposta = await apiFetch(`/agendamentos/${idAgendamento}/cancelar`, { method: 'PUT', body: '{}' });
            setSucesso(resposta.mensagem?.informacao || 'Agendamento cancelado.');
            setIdAgendamento(null);
            setModalPagamento(null);
            setModalResumo(false);
            setHorarioSelecionado(null);
            setRecarregar((n) => n + 1);
        } catch (error) { if (error.status === 409) previa.recarregar(); setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    if (!idBarbearia || !idsServicos) {
        return <main className={styles.agendamentoPage}><p>Escolha os serviços no estabelecimento antes de agendar.</p>
            <button className={styles.btnConfirmar} onClick={() => navigate('/barbearias-disponiveis')}>VER BARBEARIAS</button></main>;
    }

    return (
        <main className={styles.agendamentoPage}>
            <section className={styles.agendamentoHeader}>
                <h1>{diaAtual.data.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' })}</h1>
            </section>
            <section className={styles.profSecao} aria-label="Profissional do atendimento">
                <h2 className={styles.profTitulo}>Profissional do atendimento</h2>
                {!profissionaisCarregados && !erroProfissionais && <p className={styles.profAviso} role="status">Consultando profissionais que atendem todos os serviços selecionados…</p>}
                {erroProfissionais && <div className={styles.profAviso} role="alert"><p>Não foi possível consultar os profissionais: {erroProfissionais}</p><button type="button" className={styles.btnVoltarPagina} onClick={tentarProfissionais}>TENTAR NOVAMENTE</button></div>}
                {profissionaisCarregados && <>
                    {!profissionais.length && <p className={styles.profAviso} role="status">Não há profissional cadastrado para estes serviços. Você pode reservar um horário livre da barbearia, sem profissional definido.</p>}
                    <label className={styles.profRotulo} htmlFor="profissional-atendimento">Escolha quem realizará o atendimento</label>
                    <Select id="profissional-atendimento" className={styles.profSelect} value={idFuncionario} onChange={event => trocarProfissional(event.target.value)} disabled={ocupado}>
                        <option value="">Sem profissional definido</option>
                        {profissionais.map(prof => <option key={prof.id_funcionario} value={String(prof.id_funcionario)}>{prof.nome}</option>)}
                    </Select>
                    <p className={styles.profAviso}>{idFuncionario ? 'Os preços e horários correspondem ao profissional selecionado.' : 'Serão consultados os preços base dos serviços e os horários livres da barbearia. O profissional será definido depois.'}</p>
                </>}
            </section>
            <section className={styles.seletorDias}>
                <button type="button" className={styles.navegacaoDia} onClick={() => mudarSemana(-1)} aria-label="Semana anterior">‹</button>
                <div className={styles.diasContainer}>
                    {dias.map((dia, index) => <button type="button" key={dia.iso}
                        disabled={!dia.aberto}
                        className={`${styles.diaCard} ${dia.aberto && diaSelecionado === index ? styles.diaAtivo : ''}`}
                        onClick={() => dia.aberto && trocarDia(index)}
                        style={!dia.aberto ? {
                            background: '#f3f3f3',
                            border: '2px dashed #999',
                            color: '#999',
                            cursor: 'not-allowed',
                            opacity: 0.7
                        } : undefined}>
                        <span className={styles.diaSemana}>{dia.semana}</span><strong className={styles.diaNumero}>{dia.numero}</strong><span className={styles.diaMes}>{dia.mes}</span>
                    </button>)}
                </div>
                <button type="button" className={styles.navegacaoDia} onClick={() => mudarSemana(1)} aria-label="Próxima semana">›</button>
            </section>
            <section className={styles.horariosSection}>
                <h2>Horários para <strong>{diaAtual.data.toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })}</strong>{diaAtual.aberto && duracao ? ` · ${duracao} min` : ''}</h2>
                {(idCorte || escolhaCorte) && <div className={styles.resumoLista} aria-label="Escolha do corte"><div className={styles.resumoLinha}><span>Corte</span><strong>{descricaoEscolhaCorte}</strong></div></div>}
                {!carregando && orcamento?.valor_total != null && <div className={styles.resumoLista} aria-label="Preço dos serviços selecionados">{orcamento.servicos.map((servico) => <div className={styles.resumoLinha} key={servico.id_servico}><span>{servico.nome}</span><strong>{dinheiro(servico.preco)}</strong></div>)}<div className={styles.resumoLinha}><span>Total com {nomeProfissional}</span><strong>{dinheiro(orcamento.valor_total)}</strong></div></div>}
                {!diaAtual.aberto && <p style={{ color: '#999', fontWeight: 800 }}>A barbearia não abre neste dia.</p>}
                {consultaAtual?.erro && <div role="alert"><p>{consultaAtual.erro}</p><button type="button" className={styles.btnVoltarPagina} onClick={() => setRecarregar(valor => valor + 1)}>TENTAR CONSULTAR HORÁRIOS NOVAMENTE</button></div>}
                {erro && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />}
                {sucesso && <MensagemCard mensagem={{ informacao: sucesso, tipo: 'sucesso' }} fechar={() => setSucesso('')} />}
                <div className={styles.horariosGrid}>
                    {carregando && <p>Consultando disponibilidade…</p>}
                    {!carregando && profissionaisCarregados && diaAberto && !consultaAtual?.erro && !horarios.length && <p>Nenhum horário neste dia. Tente outra data.</p>}
                    {!carregando && horariosDaPagina.map((item) => {
                        const ocupado = !item.disponivel;
                        const esperaDisponivel = podeEntrarNaEspera(item);
                        const selecionado = horarioSelecionado === item.horario || horarioEspera === item.horario;
                        return <button type="button" key={item.horario} disabled={(ocupado && !esperaDisponivel) || entrandoEspera}
                            aria-pressed={selecionado}
                            onClick={() => {
                                if (ocupado) { setHorarioSelecionado(null); setSelecaoEspera({ horario: item.horario, contexto: contextoEspera }); }
                                else { setSelecaoEspera(null); setHorarioSelecionado(item.horario); }
                            }}
                            title={item.fim ? `Início ${item.horario}, término ${item.fim}` : item.horario}
                            className={`${styles.horarioCard} ${ocupado ? styles.horarioOcupado : ''} ${selecionado ? styles.horarioSelecionado : ''}`}>
                            <span className={styles.horarioInicio}>{item.horario}</span>
                            {item.fim && <span className={styles.horarioFim}>até {item.fim}</span>}
                            <span className={styles.horarioStatus}>{ocupado ? esperaDisponivel ? 'Ocupado · lista de espera' : 'Ocupado' : `Disponível${duracao ? ` · ${duracao} min` : ''}`}</span>
                            {selecionado && <span className={styles.checkHorario}>✓</span>}
                        </button>;
                    })}
                </div>
                {!carregando && totalPaginasHorarios > 1 && (
                    <nav className={styles.paginacaoHorarios} aria-label="Paginação de horários">
                        <button type="button" disabled={paginaHorariosSegura === 1}
                            onClick={() => setPaginaHorarios(paginaHorariosSegura - 1)} aria-label="Página anterior de horários">‹</button>
                        {Array.from({ length: totalPaginasHorarios }, (_, indice) => indice + 1).map((pagina) => (
                            <button type="button" key={pagina} onClick={() => setPaginaHorarios(pagina)}
                                className={pagina === paginaHorariosSegura ? styles.paginaHorarioAtiva : ''}
                                aria-current={pagina === paginaHorariosSegura ? 'page' : undefined}>{pagina}</button>
                        ))}
                        <button type="button" disabled={paginaHorariosSegura === totalPaginasHorarios}
                            onClick={() => setPaginaHorarios(paginaHorariosSegura + 1)} aria-label="Próxima página de horários">›</button>
                    </nav>
                )}
                {horarioEspera && <section className={styles.esperaAviso} aria-label="Entrar na lista de espera">
                    <h3>Aguardar {horarioEspera}</h3><p>Receba um e-mail se o horário ficar livre. Você precisará confirmar um novo agendamento; a inscrição não faz uma reserva.</p>
                    <button type="button" className={styles.btnConfirmarModal} disabled={carregando || entrandoEspera} onClick={entrarNaEspera}>{entrandoEspera ? 'INSCREVENDO…' : 'ENTRAR NA LISTA DE ESPERA'}</button>
                </section>}
                {!sucesso && <div className={styles.modalAcoes} style={{ justifyContent: 'center' }}>
                    <button type="button" className={styles.btnVoltarPagina} onClick={voltarParaBarbearia}>
                        VOLTAR À BARBEARIA
                    </button>
                    <button type="button" className={styles.btnConfirmarModal} disabled={!horarioSelecionado || carregando || orcamento?.valor_total == null} onClick={abrirResumo}>
                        {carregando ? 'AGUARDE…' : 'CONFIRMAR SELEÇÃO'}
                    </button>
                </div>}
                {sucesso && idAgendamento && !modalPagamento && <div className={styles.modalAcoes} style={{ justifyContent: 'center' }}>
                    <button type="button" className={styles.btnConfirmarModal} onClick={() => setModalPagamento('metodos')}>
                        CONTINUAR PARA O PAGAMENTO
                    </button>
                    <button type="button" className={styles.btnCancelar} disabled={carregando} onClick={cancelarAgendamentoCliente}>
                        CANCELAR AGENDAMENTO
                    </button>
                </div>}
            </section>

            {resumoAberto && (
                <div className={styles.overlay} onClick={() => !carregando && setModalResumo(false)} role="dialog" aria-modal="true" aria-label="Confirmar agendamento">
                    <section className={styles.modal} onClick={(e) => e.stopPropagation()}>
                        <h2>Confirmar agendamento</h2>
                        <p>Confira os detalhes antes de confirmar.</p>
                        <div className={styles.resumoLista}>
                            <div className={styles.resumoLinha}><span>Data</span><strong>{diaAtual.data.toLocaleDateString('pt-BR', { weekday: 'long', day: '2-digit', month: 'long' })}</strong></div>
                            <div className={styles.resumoLinha}><span>Horário</span><strong>{horarioSelecionado}{horarioResumo?.fim ? ` - ${horarioResumo.fim}` : ''}</strong></div>
                            {duracao && <div className={styles.resumoLinha}><span>Duração</span><strong>{duracao} min</strong></div>}
                            <div className={styles.resumoLinha}><span>Profissional</span><strong>{nomeProfissional}</strong></div>
                            {(idCorte || escolhaCorte) && <div className={styles.resumoLinha}><span>Corte</span><strong>{descricaoEscolhaCorte}</strong></div>}
                            
                        </div>
                        <ResumoTaxa resumo={previa.resumo} servico />{previa.carregando && <p role="status">Conferindo valores…</p>}{previa.erro && <div role="alert"><p>{previa.erro}</p><button type="button" className={styles.btnVoltarPagina} onClick={previa.recarregar}>CONFERIR VALORES NOVAMENTE</button></div>}<TermosAceite termos={termos} disabled={carregando} />
                        {termos.erro && <button type="button" className={styles.btnVoltarPagina} disabled={carregando || previa.carregando} onClick={() => { previa.recarregar(); termos.recarregar(); }}>ATUALIZAR VALORES E TERMOS</button>}
                        <div className={styles.modalAcoes}>
                            <button type="button" className={styles.btnVoltar} disabled={carregando} onClick={() => {
                                setModalResumo(false);
                            }}>VOLTAR</button>
                            <button type="button" className={styles.btnConfirmarModal} disabled={carregando || !termos.permitido || !previa.resumo} onClick={confirmarAgendamento}>
                                {carregando ? 'AGUARDE…' : 'CONFIRMAR AGENDAMENTO'}
                            </button>
                        </div>
                    </section>
                </div>
            )}

            {modalPagamento && idAgendamento && (
                <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Pagamento do agendamento">
                    <section className={styles.modal}>
                        <h2>Pagamento do atendimento</h2>
                        <PagamentoAgendamento key={idAgendamento} agendamento={{ id_agendamento: idAgendamento, status: 'agendado', valor_total: valorTotal, resumo: resumoAgendamento }} />
                        <div className={styles.modalAcoes}>
                            <button type="button" className={styles.btnVoltar} onClick={sairDoPagamento}>FECHAR</button>
                            <button type="button" className={styles.btnConfirmarModal} onClick={voltarParaBarbearia}>VOLTAR À BARBEARIA</button>
                        </div>
                    </section>
                </div>
            )}

            {modalCancelar && (
                <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Confirmar cancelamento" onClick={() => !carregando && setModalCancelar(false)}>
                    <section className={styles.modal} onClick={(e) => e.stopPropagation()}>
                        <h2>Cancelar agendamento</h2>
                        <p>Tem certeza que deseja cancelar este agendamento? O horário será liberado.</p>
                        <div className={styles.modalAcoes}>
                            <button type="button" className={styles.btnVoltar} disabled={carregando} onClick={() => setModalCancelar(false)}>
                                VOLTAR
                            </button>
                            <button type="button" className={styles.btnCancelar} disabled={carregando} onClick={confirmarCancelamento}>
                                {carregando ? 'CANCELANDO…' : 'CONFIRMAR CANCELAMENTO'}
                            </button>
                        </div>
                    </section>
                </div>
            )}
        </main>
    );
}

export default Agendamento;

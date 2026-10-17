import { rotaPagamentoAgendamento } from '../../services/pagamentoState';
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import styles from './Agendamento.module.css';
import { FiCreditCard, FiFileText, FiDollarSign, FiBriefcase } from 'react-icons/fi';
import { QRCodeSVG } from 'qrcode.react';
import { dataLocal as isoData, podeEntrarNaEspera } from '../../services/agendaState';
import { dinheiro } from '../../services/gestaoState';
import { dadosEscolhaCorte, rotuloEscolhaCorte } from '../../services/escolhaCorte';
import useTermosUso from '../../services/useTermosUso';
import TermosAceite from '../../components/TermosAceite/TermosAceite';
import ResumoTaxa from '../../components/ResumoTaxa/ResumoTaxa';
import useResumoOperacao from '../../services/useResumoOperacao';

const nomesSemana = ['DOM', 'SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SÁB'];
const nomesMes = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
const HORARIOS_POR_PAGINA = 12;

function Agendamento() {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const idBarbearia = params.get('barbearia');
    const idsServicos = params.get('servicos') || '';
    const idCorte = params.get('corte');
    const idVisagismo = params.get('visagismo');
    const escolhaCorte = params.get('escolha_corte') || (idCorte ? 'catalogo' : null);
    const [inicioSemana, setInicioSemana] = useState(() => {
        const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
        const solicitada = new Date(`${params.get('data') || ''}T00:00:00`);
        return !Number.isNaN(solicitada.getTime()) && solicitada >= hoje ? solicitada : hoje;
    });
    const [diaSelecionado, setDiaSelecionado] = useState(0);
    const [horarios, setHorarios] = useState([]);
    const [paginaHorarios, setPaginaHorarios] = useState(1);
    const [horarioSelecionado, setHorarioSelecionado] = useState(null);
    const [selecaoEspera, setSelecaoEspera] = useState(null);
    const [entrandoEspera, setEntrandoEspera] = useState(false);
    const [duracao, setDuracao] = useState(null);
    const [profissionais, setProfissionais] = useState([]);
    const [profissionaisCarregados, setProfissionaisCarregados] = useState(false);
    const [diasAbertos, setDiasAbertos] = useState(null);
    const [idFuncionario, setIdFuncionario] = useState(params.get('funcionario') || params.get('id_funcionario') || '');
    const [carregando, setCarregando] = useState(false);
    const [erro, setErro] = useState('');
    const [sucesso, setSucesso] = useState('');
    const [idAgendamento, setIdAgendamento] = useState(null);
    const [valorTotal, setValorTotal] = useState(null);
    const [orcamento, setOrcamento] = useState(null);
    const [pagamento, setPagamento] = useState(null);
    const [verificando, setVerificando] = useState(false);
    const [copiado, setCopiado] = useState(false);
    const [metodoPagamento, setMetodoPagamento] = useState(null); // 'pix', 'boleto', 'cartao', 'na_hora'
    const [modalResumo, setModalResumo] = useState(false); // confirmação do horário
    const [modalPagamento, setModalPagamento] = useState(null); // null | 'metodos' | 'detalhe'
    const [recarregar, setRecarregar] = useState(0); // força recarregar horários (ex.: após cancelar)
    const previa = useResumoOperacao('/agendamentos/resumo', { id_barbearia: Number(idBarbearia), id_funcionario: idFuncionario ? Number(idFuncionario) : null, ids_servicos: idsServicos.split(',') }, modalResumo && orcamento?.valor_total != null);
    const termos = useTermosUso({ versaoEsperada: previa.resumo?.termos_versao });
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
    const contextoEspera = JSON.stringify([idBarbearia, idsServicos, dataSelecionada, idFuncionario, idCorte, idVisagismo, escolhaCorte]);
    const horarioEspera = selecaoEspera?.contexto === contextoEspera ? selecaoEspera.horario : null;

    useEffect(() => {
        let ativo = true;
        const carregarProfissionais = async () => {
            await Promise.resolve();
            if (!ativo || !idBarbearia) return;
            try {
                const dados = await apiFetch(`/barbearias/${encodeURIComponent(idBarbearia)}/funcionarios?servicos=${encodeURIComponent(idsServicos)}`);
                if (ativo) {
                    setProfissionais(dados.funcionarios || []);
                    if (dados.funcionarios?.length === 1) setIdFuncionario((atual) => atual || String(dados.funcionarios[0].id_funcionario));
                    setDiasAbertos(Array.isArray(dados.dias_abertos) ? dados.dias_abertos : null);
                }
            } catch {
                if (ativo) setProfissionais([]);
            } finally {
                if (ativo) setProfissionaisCarregados(true);
            }
        };
        carregarProfissionais();
        return () => { ativo = false; };
    }, [idBarbearia, idsServicos]);

    useEffect(() => {
        let ativo = true;
        const carregarHorarios = async () => {
            // A primeira pausa evita uma atualização síncrona durante o efeito.
            await Promise.resolve();
            if (!ativo || !idBarbearia || !idsServicos || !dataSelecionada || !profissionaisCarregados) return;
            setSelecaoEspera(null);
            setOrcamento(null);
            if (profissionais.length > 0 && !idFuncionario) {
                setHorarios([]); setHorarioSelecionado(null); setCarregando(false); return;
            }
            if (diaAberto === false) {
                setHorarios([]);
                setHorarioSelecionado(null);
                setPaginaHorarios(1);
                setCarregando(false);
                return;
            }
            setCarregando(true); setErro(''); setHorarioSelecionado(null); setPaginaHorarios(1);
            try {
                const params = `id_barbearia=${encodeURIComponent(idBarbearia)}&ids_servicos=${encodeURIComponent(idsServicos)}&data=${dataSelecionada}${idFuncionario ? `&id_funcionario=${encodeURIComponent(idFuncionario)}` : ''}`;
                const dados = await apiFetch(`/agendamentos/horarios?${params}`);
                if (ativo) {
                    setHorarios(dados.horarios || []);
                    setDuracao(dados.duracao_minutos);
                    setOrcamento({ valor_total: dados.valor_total, servicos: dados.servicos || [], generos_servico: dados.generos_servico || (dados.servicos || []).map((servico) => servico.genero).filter(Boolean) });
                }
            } catch (error) {
                if (ativo) setErro(mensagemDaApi(error));
            } finally {
                if (ativo) setCarregando(false);
            }
        };
        carregarHorarios();
        return () => { ativo = false; };
    }, [idBarbearia, idsServicos, dataSelecionada, idFuncionario, recarregar, diaAberto, profissionaisCarregados, profissionais.length]);

    const mudarSemana = (direcao) => {
        const proxima = new Date(inicioSemana);
        proxima.setDate(proxima.getDate() + (direcao * 7));
        const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
        if (proxima >= hoje) { setInicioSemana(proxima); setDiaSelecionado(0); }
    };

    const abrirResumo = () => {
        if (!horarioSelecionado) { setErro('Selecione um horário disponível.'); return; }
        if (orcamento?.valor_total == null) { setErro('Aguarde a consulta do valor antes de confirmar.'); return; }
        setErro('');
        setModalResumo(true);
    };
    const entrarNaEspera = async () => {
        if (!horarioEspera || entrandoEspera) return;
        const item = horarios.find((horario) => horario.horario === horarioEspera);
        if (!podeEntrarNaEspera(item)) return;
        setEntrandoEspera(true); setErro('');
        try {
            const dados = await apiFetch('/agendamentos/lista-espera', { method: 'POST', body: JSON.stringify({
                id_barbearia: Number(idBarbearia), ids_servicos: idsServicos.split(','), data: dataSelecionada,
                horario: horarioEspera, id_funcionario: idFuncionario ? Number(idFuncionario) : null,
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
        : 'Sem preferência';
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
                    id_barbearia: Number(idBarbearia), ids_servicos: idsServicos.split(','),
                    data: diaAtual.iso, horario: horarioSelecionado, confirmacao_resumo: previa.resumo.confirmacao_resumo,
                    ...dadosEscolhaCorte({ escolhaCorte, idCorte, idVisagismo }),
                    id_funcionario: idFuncionario ? Number(idFuncionario) : null
                })
            });
            setSucesso(dados.mensagem?.informacao || 'Agendamento realizado!');
            setIdAgendamento(dados.agendamento?.id_agendamento || null);
            setValorTotal(dados.agendamento?.resumo?.valor_total_cliente ?? dados.agendamento?.valor_total ?? null);
            setResumoAgendamento(dados.agendamento?.resumo ?? null);
            setPagamento(null);
            setMetodoPagamento(null);
            // Fecha o resumo e abre o modal de pagamento
            setModalResumo(false);
            setModalPagamento('metodos');
        } catch (error) { if (error.status === 409) previa.recarregar(); setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    const verificarPagamento = async () => {
        if (!pagamento?.id_cobranca) return;
        setVerificando(true);
        try {
            const dados = await apiFetch(`/pagamentos/pix/${pagamento.id_cobranca}`);
            if (dados.pago) {
                setPagamento((atual) => ({ ...atual, status: 1 }));
                setSucesso('Pagamento confirmado! Redirecionando para a página da barbearia…');
                window.setTimeout(() => navigate(`/estabelecimento?usuario=${encodeURIComponent(idBarbearia)}`), 2500);
            } else {
                setErro('Pagamento ainda pendente. Conclua no app e tente de novo.');
            }
        } catch (error) { if (error.status === 409) previa.recarregar(); setErro(mensagemDaApi(error)); }
        finally { setVerificando(false); }
    };

    useEffect(() => {
        if (!pagamento?.id_cobranca || pagamento.status === 1) return undefined;
        const intervalo = window.setInterval(() => { verificarPagamento(); }, 15000);
        return () => window.clearInterval(intervalo);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pagamento]);

    const copiarCodigo = async () => {
        if (!pagamento?.codigo_pagamento) return;
        try {
            await navigator.clipboard.writeText(pagamento.codigo_pagamento);
            setCopiado(true);
            window.setTimeout(() => setCopiado(false), 2000);
        } catch { setErro('Não foi possível copiar. Selecione o código manualmente.'); }
    };

    const selecionarMetodoPagamento = (metodo) => {
        setMetodoPagamento(metodo);
        setModalPagamento('detalhe');
        solicitarPagamento(metodo);
    };

    const solicitarPagamento = async (metodo) => {
        const rota = rotaPagamentoAgendamento(metodo);
        if (!idAgendamento || !rota) return;
        setCarregando(true); setErro('');
        try {
            const dados = await apiFetch(rota, {
                method: 'POST', body: JSON.stringify({ id_agendamento: idAgendamento })
            });
            setPagamento({ ...dados, metodo });
        } catch (error) { if (error.status === 409) previa.recarregar(); setErro(mensagemDaApi(error)); }
        finally { setCarregando(false); }
    };

    // Fechar o pagamento apenas fecha o modal. O cancelamento precisa ser uma
    // ação explícita no botão "Cancelar agendamento".
    const sairDoPagamento = () => {
        setModalPagamento(null);
        setModalResumo(false);
    };

    const voltarSelecaoPagamento = () => {
        setMetodoPagamento(null);
        setPagamento(null);
        setModalPagamento('metodos');
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
            setPagamento(null);
            setMetodoPagamento(null);
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
            {profissionais.length > 0 && (
                <section className={styles.profSecao} aria-label="Escolha o profissional">
                    <h2 className={styles.profTitulo}>Com quem você quer cortar?</h2>
                    <div className={styles.profLista} role="radiogroup" aria-label="Profissionais">
                        {profissionais.map((prof) => {
                            const ativo = String(idFuncionario) === String(prof.id_funcionario);
                            const inicial = String(prof.nome || '?').trim().charAt(0).toUpperCase();
                            return <button type="button" key={prof.id_funcionario} role="radio" aria-checked={ativo}
                                className={`${styles.profCard} ${ativo ? styles.profAtivo : ''}`}
                                onClick={() => setIdFuncionario(String(prof.id_funcionario))}>
                                <span className={styles.profAvatar} aria-hidden="true">{inicial}</span>
                                <span className={styles.profNome}>{prof.nome}</span>
                                {ativo && <span className={styles.checkHorario}>✓</span>}
                            </button>;
                        })}
                    </div>
                </section>
            )}
            <section className={styles.seletorDias}>
                <button type="button" className={styles.navegacaoDia} onClick={() => mudarSemana(-1)} aria-label="Semana anterior">‹</button>
                <div className={styles.diasContainer}>
                    {dias.map((dia, index) => <button type="button" key={dia.iso}
                        disabled={!dia.aberto}
                        className={`${styles.diaCard} ${dia.aberto && diaSelecionado === index ? styles.diaAtivo : ''}`}
                        onClick={() => dia.aberto && setDiaSelecionado(index)}
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
                {erro && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />}
                {sucesso && <MensagemCard mensagem={{ informacao: sucesso, tipo: 'sucesso' }} fechar={() => setSucesso('')} />}
                <div className={styles.horariosGrid}>
                    {carregando && <p>Consultando disponibilidade…</p>}
                    {!carregando && !horarios.length && <p>{profissionais.length > 0 && !idFuncionario ? 'Selecione um profissional para consultar horários e preços.' : 'Nenhum horário neste dia. Tente outra data.'}</p>}
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
                    <button type="button" className={styles.btnConfirmarModal} onClick={() => setModalPagamento(metodoPagamento ? 'detalhe' : 'metodos')}>
                        CONTINUAR PARA O PAGAMENTO
                    </button>
                    <button type="button" className={styles.btnCancelar} disabled={carregando} onClick={cancelarAgendamentoCliente}>
                        CANCELAR AGENDAMENTO
                    </button>
                </div>}
            </section>

            {modalResumo && (
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
                        <ResumoTaxa resumo={previa.resumo} servico />{previa.carregando && <p role="status">Conferindo valores…</p>}{previa.erro && <p role="alert">{previa.erro}</p>}<TermosAceite termos={termos} disabled={carregando} />
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
                <div className={styles.overlay} role="dialog" aria-modal="true" aria-label="Pagamento do agendamento"
                    onClick={() => { if (pagamento?.status !== 1) sairDoPagamento(); }}>
                    <section className={styles.modal} onClick={(e) => e.stopPropagation()}>
                        {modalPagamento === 'metodos' && (
                            <>
                                <h2>Como deseja pagar?</h2><ResumoTaxa resumo={resumoAgendamento} servico />
                                <p>{valorTotal != null ? <>Total de <strong>R$ {Number(valorTotal).toFixed(2).replace('.', ',')}</strong>.</> : 'Escolha a forma de pagamento.'} Seu agendamento continua reservado até que você ou a barbearia o cancele.</p>
                                <div className={styles.opcoesPagamento}>
                                    <button type="button" className={styles.opcaoPagamento} onClick={() => selecionarMetodoPagamento('pix')} disabled={carregando}>
                                        <FiDollarSign />
                                        <span>PIX</span>
                                        <small>Pagamento instantâneo via QR Code</small>
                                    </button>
                                    <button type="button" className={styles.opcaoPagamento} onClick={() => selecionarMetodoPagamento('boleto')} disabled={carregando}>
                                        <FiFileText />
                                        <span>Boleto</span>
                                        <small>Pague em qualquer banco ou lotérica</small>
                                    </button>
                                    <button type="button" className={styles.opcaoPagamento} onClick={() => selecionarMetodoPagamento('cartao')} disabled={carregando}>
                                        <FiCreditCard />
                                        <span>Cartão</span>
                                        <small>Débito ou crédito</small>
                                    </button>
                                    <button type="button" className={styles.opcaoPagamento} onClick={() => selecionarMetodoPagamento('na_hora')} disabled={carregando}>
                                        <FiBriefcase />
                                        <span>Pagar no local</span>
                                        <small>Dinheiro ou cartão na barbearia</small>
                                    </button>
                                </div>
                                <div className={styles.modalAcoes}>
                                    <button type="button" className={styles.btnVoltar} onClick={sairDoPagamento}>VOLTAR</button>
                                    <button type="button" className={styles.btnCancelar} disabled={carregando} onClick={cancelarAgendamentoCliente}>
                                        CANCELAR AGENDAMENTO
                                    </button>
                                </div>
                            </>
                        )}
                        {modalPagamento === 'detalhe' && (
                            <>
                                {pagamento?.metodo === 'pix' && (
                                    <>
                                        <h2>Pix gerado · R$ {Number(pagamento.valor || 0).toFixed(2).replace('.', ',')}</h2>
                                        {pagamento.status === 1
                                            ? <p className={styles.confirmado}>✓ Pagamento confirmado! Voltando para a barbearia…</p>
                                            : <>
                                                <p>Use o código abaixo no app da sua conta. Verificamos automaticamente a cada 15 segundos.</p>
                                                <div className={styles.qrCode}>
                                                    <QRCodeSVG value={pagamento.codigo_pagamento} size={200} />
                                                </div>
                                                <p className={styles.codigoPix}><strong>{pagamento.codigo_pagamento}</strong></p>
                                                <div className={styles.modalAcoes}>
                                                    <button type="button" className={styles.btnVoltar} onClick={voltarSelecaoPagamento}>VOLTAR</button>
                                                    <button type="button" className={styles.btnCancelar} disabled={carregando} onClick={cancelarAgendamentoCliente}>
                                                        CANCELAR AGENDAMENTO
                                                    </button>
                                                    <button type="button" className={styles.btnConfirmarModal} onClick={copiarCodigo}>
                                                        {copiado ? 'CÓDIGO COPIADO!' : 'COPIAR CÓDIGO PIX'}
                                                    </button>
                                                    <button type="button" className={styles.btnConfirmarModal} disabled={verificando} onClick={verificarPagamento}>
                                                        {verificando ? 'VERIFICANDO…' : 'JÁ PAGUEI, VERIFICAR'}
                                                    </button>
                                                </div>
                                            </>}
                                    </>
                                )}
                                {pagamento?.metodo === 'boleto' && (
                                    <>
                                        <h2>Boleto gerado · R$ {Number(pagamento.valor || 0).toFixed(2).replace('.', ',')}</h2>
                                        <p>Salve o PDF ou copie o código de barras para pagar. Depois volte para a barbearia.</p>
                                        <div className={styles.modalAcoes}>
                                            <button type="button" className={styles.btnVoltar} onClick={voltarSelecaoPagamento}>VOLTAR</button>
                                            <button type="button" className={styles.btnCancelar} disabled={carregando} onClick={cancelarAgendamentoCliente}>
                                                CANCELAR AGENDAMENTO
                                            </button>
                                            <button type="button" className={styles.btnConfirmarModal} onClick={() => window.open(pagamento.url_boleto, '_blank')}>
                                                BAIXAR BOLETO
                                            </button>
                                            <button type="button" className={styles.btnConfirmarModal} onClick={voltarParaBarbearia}>
                                                VOLTAR À BARBEARIA
                                            </button>
                                        </div>
                                    </>
                                )}
                                {pagamento?.metodo === 'cartao' && (
                                    <>
                                        <h2>Pagamento com Cartão · R$ {Number(pagamento.valor || 0).toFixed(2).replace('.', ',')}</h2>
                                        <p>Conclua no checkout seguro e depois volte para a barbearia.</p>
                                        <div className={styles.modalAcoes}>
                                            <button type="button" className={styles.btnVoltar} onClick={voltarSelecaoPagamento}>VOLTAR</button>
                                            <button type="button" className={styles.btnCancelar} disabled={carregando} onClick={cancelarAgendamentoCliente}>
                                                CANCELAR AGENDAMENTO
                                            </button>
                                            {pagamento.url_checkout && <a href={pagamento.url_checkout} target="_blank" rel="noreferrer" className={styles.btnConfirmarModal}>IR PARA O CHECKOUT</a>}
                                            <button type="button" className={styles.btnConfirmarModal} onClick={voltarParaBarbearia}>
                                                VOLTAR À BARBEARIA
                                            </button>
                                        </div>
                                    </>
                                )}
                                {pagamento?.metodo === 'na_hora' && (
                                    <>
                                        <h2>Pagar no local</h2>
                                        <p>Seu agendamento está reservado. Pague diretamente na barbearia.</p>
                                        <p><strong>Pendente de confirmação da barbearia.</strong> A escolha deste método não confirma que o pagamento foi recebido.</p>
                                        <div className={styles.modalAcoes}>
                                            <button type="button" className={styles.btnConfirmarModal} onClick={voltarParaBarbearia}>
                                                VOLTAR À BARBEARIA
                                            </button>
                                        </div>
                                    </>
                                )}
                                {!pagamento && carregando && <p>Gerando pagamento…</p>}
                            </>
                        )}
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

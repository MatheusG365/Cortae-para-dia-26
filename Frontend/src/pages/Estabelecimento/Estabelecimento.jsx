import { somenteDigitos } from '../../services/cadastroState';
import { dinheiroZero as formatarPreco } from '../../services/formatacao';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
    FiMapPin,
    FiClock,
    FiPhone,
    FiMail,
    FiInstagram,
    FiCalendar,
    FiUser,
    FiBarChart2
} from 'react-icons/fi';
import CardServico from '../../components/CardServico/CardServico';
import styles from './Estabelecimento.module.css';
import CarrosselImagens from "../../components/CarrosselImagens/CarrosselImagens.jsx";
import { urlDaApi, apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import { useAuth } from '../../contexts/useAuth';
import LojaBarbeariaPreview from '../Marketplace/LojaBarbeariaPreview';
import { idLojaDoEstabelecimento, temaDaLoja } from '../Marketplace/lojaState';
import { carregarPerfilPublico } from '../Marketplace/perfilPublico';
import RequireAuth from '../../components/RequireAuth/RequireAuth';

export default function Estabelecimento() {
    const [searchParams] = useSearchParams();
    const { usuario } = useAuth();
    const alvo = searchParams.has('usuario') ? searchParams.get('usuario') : null;
    const conteudo = <EstabelecimentoConteudo key={`${alvo ?? 'propria'}:${usuario?.id_usuario ?? usuario?.id ?? ''}:${usuario?.tipo ?? ''}`} idUsuarioAlvo={alvo} usuario={usuario || {}} />;
    return alvo == null ? <RequireAuth>{conteudo}</RequireAuth> : conteudo;
}
function EstabelecimentoConteudo({ idUsuarioAlvo, usuario }) {
    const navigate = useNavigate();
    const sufixoUsuario = idUsuarioAlvo != null ? `?id_usuario=${encodeURIComponent(idUsuarioAlvo)}` : '';
    const [categoria, setCategoria] = useState('Serviços');
    const [dados, setDados] = useState(null);
    const [servicos, setServicos] = useState([]);
    const [erro, setErro] = useState('');
    const [profissionalSelecionado, setProfissionalSelecionado] = useState(null);
    const [modalServicosAberto, setModalServicosAberto] = useState(false);
    const idLoja = idLojaDoEstabelecimento(idUsuarioAlvo, dados, usuario);

    useEffect(() => {
        const controller = new AbortController();
        async function carregar() {
            try {
                const [personalizacao, servicosDaApi] = idUsuarioAlvo != null
                    ? await carregarPerfilPublico(idUsuarioAlvo, { signal: controller.signal }).then(perfil => [perfil, perfil])
                    : await Promise.all([
                        apiFetch(`/barbearia/personalizacao${sufixoUsuario}`, { signal: controller.signal }), apiFetch(`/barbearia/servicos${sufixoUsuario}`, { signal: controller.signal }),
                    ]);
                if (controller.signal.aborted) return;
                setDados(personalizacao);
                setServicos(servicosDaApi.servicos || []);
            } catch (error) { if (!controller.signal.aborted) setErro(mensagemDaApi(error)); }
        }
        carregar();
        return () => controller.abort();
    }, [sufixoUsuario, idUsuarioAlvo]);

    useEffect(() => {
        if (dados && window.location.hash === '#loja-barbearia') {
            document.getElementById('loja-barbearia')?.scrollIntoView({ block: 'start' });
        }
    }, [dados]);

    if (erro) return <main className={styles.container}><div className={styles.conteudo}><MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} /><LojaBarbeariaPreview idLoja={idLoja} /></div></main>;
    if (!dados) return <main className={styles.container}><p>Carregando estabelecimento…</p></main>;
    if (!dados.personalizado) return (
        <main className={styles.container}>
            <div className={styles.conteudo}>
            <div className={styles.naoPersonalizada}>
                <div className={styles.iconeNaoPersonalizada}>
                    <FiBarChart2 size={48} />
                </div>
                <h2>Esta barbearia ainda não foi personalizada</h2>
                <p>O estabelecimento ainda não configurou suas informações, serviços e horários.</p>
                <p>Volte mais tarde ou entre em contato com a barbearia para mais detalhes.</p>
            </div>
            <LojaBarbeariaPreview idLoja={idLoja} />
            </div>
        </main>
    );

    const personalizacao = dados.personalizacao;
    const profissionais = dados.funcionarios || [];
    // A logo aparece só no card da barbearia (lista); aqui o carrossel
    // mostra as fotos do estabelecimento, com a logo como fallback.
    const fotosBarbearia = (dados.fotos || []).map((foto) => urlDaApi(foto.url));
    const imagensBarbearia = fotosBarbearia.length
        ? fotosBarbearia
        : (dados.logo ? [urlDaApi(dados.logo)] : []);
    const nomeBarbearia = dados.nome_barbearia || (Number(usuario?.tipo) === 2 && String(usuario?.id_usuario ?? usuario?.id) === idLoja ? usuario?.nome : null) || 'Barbearia';
    const formatarDuracao = (duracao) => duracao ? `${duracao} MIN` : '--';
    const isBarbeariaOwner = Number(usuario?.tipo) === 2 && String(usuario?.id_usuario ?? usuario?.id) === idLoja;
    const servicosDoProfissional = profissionalSelecionado
        ? servicos.filter((servico) =>
            profissionalSelecionado.servicos?.includes(servico.id_servico)
        )
        : [];
    const diasDoProfissional = profissionalSelecionado
        ? (dados.dias_servico || []).filter((dia) =>
            profissionalSelecionado.dias?.includes(dia.id_dia)
        )
        : [];
    const telefoneWhatsApp = somenteDigitos(personalizacao.contato_telefone);
    const instagram = String(personalizacao.instagram || '').replace(/^@/, '');
    const iniciarAgendamento = () => {
        navigate(`/selecionar-servicos?barbearia=${encodeURIComponent(idUsuarioAlvo || dados.personalizacao.id_usuario)}`);
    };
    const irParaFinanceiro = () => {
        navigate(`/financeiro`);
    };

    return (
        <main className={styles.container} style={temaDaLoja(personalizacao)}>
            <section className={styles.conteudo}>
                <div className={styles.apresentacao}>
                    <div className={styles.informacoes}>
                        <span className={styles.selo}>
                            PREMIUM EXPERIENCE
                        </span>

                        <h1>{nomeBarbearia}</h1>

                        <p>
                            {personalizacao.historia || 'Conheça nossa barbearia e nossos serviços.'}
                        </p>

                        <button
                            id="btn-agendar-topo"
                            className={styles.botaoAgendar}
                            onClick={iniciarAgendamento}
                        >
                            Agendar Agora
                        </button>
                        {idLoja && <a className={styles.botaoLoja} href="#loja-barbearia">Visitar loja da barbearia</a>}
                    </div>

                    <div className={styles.imagemContainer}>
                        {imagensBarbearia.length ? <CarrosselImagens imagens={imagensBarbearia} /> : <div />}
                    </div>
                </div>

                <div className={styles.areaPrincipal}>
                    <section className={styles.servicos}>
                        <div className={styles.tituloSecao}>
                            <span></span>
                            <h2>Nossos Serviços</h2>
                        </div>

                        <div className={styles.abas}>
                            {idLoja && <a href="#loja-barbearia">Loja</a>}
                            <button
                                id="btn-aba-servicos"
                                className={
                                    categoria === 'Serviços'
                                        ? styles.abaAtiva
                                        : ''
                                }
                                onClick={() => setCategoria('Serviços')}
                            >
                                Serviços
                            </button>

                            <button
                                id="btn-aba-profissionais"
                                className={
                                    categoria === 'Profissionais'
                                        ? styles.abaAtiva
                                        : ''
                                }
                                onClick={() =>
                                    setCategoria('Profissionais')
                                }
                            >
                                Profissionais
                            </button>
                        </div>

                        {categoria === 'Serviços' && (
                            <div className={styles.listaServicos}>
                                {servicos.slice(0, 5).map((servico) => (
                                    <CardServico
                                        key={servico.id_servico}
                                        nome={servico.nome}
                                        tempo={formatarDuracao(servico.duracao)}
                                        preco={formatarPreco(servico.preco)}
                                    />
                                ))}
                                {servicos.length > 5 && (
                                    <button type="button" className={styles.verMaisServicos} onClick={() => setModalServicosAberto(true)}>
                                        Ver mais {servicos.length - 5} serviço(s)
                                    </button>
                                )}
                            </div>
                        )}

                        {categoria === 'Profissionais' && (
                            <div className={styles.listaProfissionais}>
                                {profissionais.map((profissional) => (
                                    <button
                                        type="button"
                                        className={styles.profissional}
                                        key={profissional.id_funcionario}
                                        onClick={() => setProfissionalSelecionado(profissional)}
                                    >
                                        <div className={styles.iconeProfissional}>
                                            <FiUser />
                                        </div>

                                        <div>
                                            <h3>{profissional.nome}</h3>
                                            <span>
                                                {profissional.descricao || 'Barbeiro'}
                                            </span>
                                        </div>
                                    </button>
                                ))}
                            </div>
                        )}
                    </section>

                    <aside className={styles.lateral}>
                        <div className={styles.cardInformacoes}>
                            <div className={styles.bloco}>
                                <div className={styles.tituloCard}>
                                    <FiMapPin />
                                    <span>LOCALIZAÇÃO</span>
                                </div>

                                <p>
                                    {personalizacao.localizacao || 'Localização não informada'}
                                </p>
                            </div>

                            <div className={styles.bloco}>
                                <div className={styles.tituloCard}>
                                    <FiClock />
                                    <span>
                                        HORÁRIO DE ATENDIMENTO
                                    </span>
                                </div>

                                <div className={styles.horarios}>{(dados.dias_servico || []).map((dia) => {
                                    const hhmm = (h) => (h ? String(h).slice(0, 5) : '');
                                    const manha = dia.entrada_manha && dia.saida_manha
                                        ? `${hhmm(dia.entrada_manha)} - ${hhmm(dia.saida_manha)}`
                                        : '';
                                    const tarde = dia.entrada_tarde && dia.saida_tarde
                                        ? `${hhmm(dia.entrada_tarde)} - ${hhmm(dia.saida_tarde)}`
                                        : '';
                                    const texto = [manha, tarde].filter(Boolean).join(' | ');
                                    return <div key={dia.id_dia} className={styles.linhaHorario}><span className={styles.diaNome}>{dia.dia}</span><strong className={styles.diaHorario}>{texto}</strong></div>;
                                })}</div>
                            </div>

                            <div className={styles.bloco}>
                                <div className={styles.tituloCard}>
                                    <FiPhone />
                                    <span>CONTATO</span>
                                </div>

                                {telefoneWhatsApp ? <a className={styles.telefone} href={`https://wa.me/55${telefoneWhatsApp}`} target="_blank" rel="noreferrer"><FiPhone /><span>{personalizacao.contato_telefone}</span></a> : <div className={styles.telefone}><FiPhone /><span>Telefone não informado</span></div>}
                                {personalizacao.contato_email && <a className={styles.telefone} href={`mailto:${personalizacao.contato_email}`}><FiMail /><span>{personalizacao.contato_email}</span></a>}
                                {instagram && <a className={styles.telefone} href={`https://instagram.com/${instagram}`} target="_blank" rel="noreferrer"><FiInstagram /><span>{personalizacao.instagram}</span></a>}
                            </div>
                        </div>

                                            {isBarbeariaOwner && (
                        <button
                            className={styles.botaoFinanceiro}
                            onClick={irParaFinanceiro}
                        >
                            <FiBarChart2 />
                            FINANCEIRO
                        </button>
                    )}

<button
                            id="btn-agendar-lateral"
                            className={styles.botaoAgendarGrande}
                            onClick={iniciarAgendamento}
                        >
                            <FiCalendar />
                            AGENDAR AGORA
                        </button>
                    </aside>
                </div>
                <LojaBarbeariaPreview idLoja={idLoja} />
            </section>

            {profissionalSelecionado && (
                <div
                    className={styles.modalFundo}
                    onClick={() => setProfissionalSelecionado(null)}
                >
                    <div
                        className={styles.modal}
                        onClick={(event) => event.stopPropagation()}
                    >
                        <button
                            type="button"
                            className={styles.fecharModal}
                            onClick={() => setProfissionalSelecionado(null)}
                        >
                            ×
                        </button>

                        <div className={styles.modalIcone}>
                            <FiUser />
                        </div>

                        <h2>{profissionalSelecionado.nome}</h2>
                        <p className={styles.modalDescricao}>
                            {profissionalSelecionado.descricao || 'Profissional da barbearia'}
                        </p>

                        <div className={styles.modalBloco}>
                            <h3>Serviços</h3>
                            {servicosDoProfissional.length ? (
                                <div className={styles.modalLista}>
                                    {servicosDoProfissional.map((servico) => (
                                        <div className={styles.modalItem} key={servico.id_servico}>
                                            <span>{servico.nome}</span>
                                            <strong>{formatarPreco(servico.preco)}</strong>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p>Nenhum serviço informado.</p>
                            )}
                        </div>

                        <div className={styles.modalBloco}>
                            <h3>Atendimento</h3>
                            {diasDoProfissional.length ? (
                                <div className={styles.modalLista}>
                                    {diasDoProfissional.map((dia) => {
                                        const hhmm = (h) => (h ? String(h).slice(0, 5) : '');
                                        const manha = dia.entrada_manha && dia.saida_manha
                                            ? `${hhmm(dia.entrada_manha)} - ${hhmm(dia.saida_manha)}`
                                            : '';
                                        const tarde = dia.entrada_tarde && dia.saida_tarde
                                            ? `${hhmm(dia.entrada_tarde)} - ${hhmm(dia.saida_tarde)}`
                                            : '';
                                        const texto = [manha, tarde].filter(Boolean).join(' | ');
                                        return (
                                            <div className={styles.modalItem} key={dia.id_dia}>
                                                <span>{dia.dia}</span>
                                                <strong>{texto}</strong>
                                            </div>
                                        );
                                    })}
                                </div>
                            ) : (
                                <p>Nenhum horário informado.</p>
                            )}
                        </div>
                    </div>
                </div>
            )}
            {modalServicosAberto && (
                <div className={styles.modalFundo} onClick={() => setModalServicosAberto(false)}>
                    <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
                        <button type="button" className={styles.fecharModal} onClick={() => setModalServicosAberto(false)}>×</button>
                        <h2>Todos os serviços</h2>
                        <div className={styles.modalLista}>
                            {servicos.map((servico) => (
                                <div key={servico.id_servico} className={styles.modalItem}>
                                    <span>{servico.nome}</span>
                                    <strong>{formatarPreco(servico.preco)}</strong>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </main>
    );
}



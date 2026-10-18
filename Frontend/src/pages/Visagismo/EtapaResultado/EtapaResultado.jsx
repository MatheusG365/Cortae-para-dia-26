import { FiArrowLeft, FiCheck, FiImage, FiClock, FiScissors, FiX } from 'react-icons/fi';
import { useState } from 'react';
import MensagemCard from '../../../components/MensagemCard/MensagemCard';
import useDialog from '../../../components/useDialog';
import { permiteEscolhaNoAtendimento, rotuloEscolhaCorte } from '../../../services/escolhaCorte';
import { CAMPOS_CARACTERISTICAS, textoCaracteristica } from '../visagismoState';
import styles from './EtapaResultado.module.css';

const CATEGORIAS_COR = [
    { id: 'pintar_cabelos', nome: 'Pintar Cabelo', cores: ['#ff6b35', '#f7c59f', '#efa00b', '#d62828', '#003049', '#219ebc', '#8ecae6', '#023047', '#6f1d1b', '#bb9457', '#432818', '#99582a', '#ffe6a7', '#7f5539', '#b08968', '#ddb892', '#e6ccb2', '#ede0d4'] },
    { id: 'pintar_barba', nome: 'Pintar Barba', cores: ['#2c1810', '#4a3728', '#6b4423', '#8b5a2b', '#1a1a1a', '#3d3d3d', '#5c5c5c', '#7a7a7a'] }
];

function ImagemVisagismo({ url, descricao, indisponivel = 'Referência não disponível' }) {
    const [urlComErro, setUrlComErro] = useState(null);
    if (!url || urlComErro === url) {
        return <div className={styles.semImagem}><FiImage aria-hidden="true" /><span>{indisponivel}</span></div>;
    }
    return <img src={url} alt={descricao} onError={() => setUrlComErro(url)} />;
}

const generoDoCorte = (genero) => ({ masculino: 'Masculino', feminino: 'Feminino', unissex: 'Unissex' }[genero] || genero || 'Não informado');
const categoriaDoCorte = (categoria) => categoria ? String(categoria).replaceAll('_', ' ') : 'Não informada';

function EtapaResultado({ imagem, corteSelecionado, cortes = [], observacoes, caracteristicas = {}, cabeloAtual,
    modoPulado, apenasCor = false, imagemResultado, avisoSimulacao, carregando, erro, fecharErro,
    selecionarCorte, voltarEtapa, confirmarSelecao, refazerSimulacao, corSelecionada, setCorSelecionada,
    categoriaCor, setCategoriaCor, temPintar, pintarCabelo, pintarBarba, botaoSimular,
    escolhaCorte = 'catalogo', generosServicos = [], selecionarEscolhaNoAtendimento }) {
    const [pagina, setPagina] = useState(1);
    const [filtroGenero, setFiltroGenero] = useState('todos');
    const [corteDetalhes, setCorteDetalhes] = useState(null);
    const dialogoDetalhes = useDialog(Boolean(corteDetalhes), () => setCorteDetalhes(null), carregando);
    const permiteEspecial = permiteEscolhaNoAtendimento({ modoPulado, temPintar, apenasCor });
    const recomendacao = !modoPulado && !apenasCor;
    const corteRecomendado = recomendacao ? cortes[0] : null;
    const generosDisponiveis = new Set(cortes.map((corte) => corte.genero));
    const cortesFiltrados = cortes.filter((corte) => filtroGenero === 'todos' || corte.genero === filtroGenero);
    const totalPaginas = Math.max(1, Math.ceil(cortesFiltrados.length / 6));
    const paginaSegura = Math.min(Math.max(1, pagina), totalPaginas);
    const cortesPagina = cortesFiltrados.slice((paginaSegura - 1) * 6, paginaSegura * 6);
    const categoriasCorVisiveis = CATEGORIAS_COR.filter((categoria) => {
        if (!pintarCabelo && !pintarBarba) return true;
        return categoria.id === 'pintar_cabelos' ? pintarCabelo : pintarBarba;
    });
    const categoriaAtiva = categoriaCor || categoriasCorVisiveis[0]?.id;
    const mudarFiltro = (genero) => { setFiltroGenero(genero); setPagina(1); };
    const escolhaEspecial = permiteEspecial && ['na_hora', 'profissional'].includes(escolhaCorte);
    const selecaoIncompleta = (!apenasCor && !corteSelecionado?.id_corte && !escolhaEspecial) || (temPintar && !corSelecionada);

    return (
        <section className={styles.etapa}>
            <div className={styles.topo}>
                <button type="button" className={styles.botaoVoltar} onClick={voltarEtapa} disabled={carregando}>
                    <FiArrowLeft /> VOLTAR
                </button>
            </div>
            <div className={styles.cabecalho}>
                <h1>{apenasCor ? 'Teste a cor escolhida' : recomendacao ? 'Seu corte recomendado' : 'Como deseja escolher o corte?'}</h1>
                <p>{apenasCor ? 'Escolha uma cor para simular na foto enviada.' : recomendacao
                    ? 'Um corte cadastrado, escolhido a partir das características observadas na sua foto.'
                    : 'Escolha no catálogo ou deixe a decisão para o atendimento.'}</p>
            </div>

            {permiteEspecial && <section className={styles.escolhasAtendimento} aria-label="Escolher durante o atendimento">
                {['na_hora', 'profissional'].map((escolha) => {
                    const selecionada = escolhaCorte === escolha;
                    const Icone = escolha === 'na_hora' ? FiClock : FiScissors;
                    return <button key={escolha} type="button" aria-pressed={selecionada} disabled={carregando}
                        className={`${styles.escolhaAtendimento} ${selecionada ? styles.escolhaAtiva : ''}`}
                        onClick={() => selecionarEscolhaNoAtendimento(escolha)}>
                        <span className={styles.iconeEscolha}><Icone aria-hidden="true" /></span>
                        <span><strong>{rotuloEscolhaCorte(escolha, generosServicos)}</strong><small>{escolha === 'na_hora' ? 'Decida o corte quando chegar ao estabelecimento.' : 'Converse com quem vai atender você e deixe a escolha com esse profissional.'}</small></span>
                        {selecionada && <FiCheck aria-label="Selecionado" />}
                    </button>;
                })}
            </section>}
            {escolhaEspecial && <p className={styles.resumoEscolha} role="status"><FiCheck aria-hidden="true" /> Escolha para o atendimento: <strong>{rotuloEscolhaCorte(escolhaCorte, generosServicos)}</strong></p>}

            <div className={`${styles.resultado} ${recomendacao ? styles.comparacao : ''} ${recomendacao && (!imagem || !corteRecomendado) ? styles.comparacaoUnica : ''}`}>
                {imagem && <figure className={`${styles.cardCorte} ${styles.fotoPessoa}`}>
                    <div className={styles.imagemCorte}>
                        <ImagemVisagismo url={imagem} descricao="Foto enviada para o visagismo" indisponivel="Foto não disponível" />
                    </div>
                    <figcaption className={styles.infoCorte}>
                        <span className={styles.rotuloFoto}>Foto enviada</span>
                        <h2>Sua foto</h2>
                        <p>Imagem usada para a análise e a simulação.</p>
                    </figcaption>
                </figure>}
                {recomendacao && corteRecomendado && <article className={`${styles.cardCorte} ${styles.recomendacao}`}>
                    <div className={styles.imagemCorte}>
                        <ImagemVisagismo url={corteRecomendado.imagem_url} descricao={`Referência do catálogo: ${corteRecomendado.nome}`} />
                    </div>
                    <div className={styles.infoCorte}>
                        <span className={styles.selecao}><FiCheck aria-hidden="true" /> Corte selecionado</span>
                        <h2>{corteRecomendado.nome}</h2>
                        <p>Referência do catálogo · #{corteRecomendado.id_corte}</p>
                        <p className={styles.descricaoResumida}>{corteRecomendado.descricao || 'Veja os detalhes deste corte.'}</p>
                    </div>
                    <div className={styles.acoesCard}>
                        <button type="button" className={styles.botaoDetalhes} disabled={carregando} onClick={() => setCorteDetalhes(corteRecomendado)}>Ver mais<span className={styles.somenteLeitor}> sobre {corteRecomendado.nome}</span></button>
                    </div>
                </article>}
                {!recomendacao && !apenasCor && <div className={styles.catalogoCortes}>
                    <div className={styles.tituloCatalogo}><h2>Cortes do catálogo</h2><p>Veja as referências e os detalhes antes de escolher.</p></div>
                    {['masculino', 'feminino'].some((genero) => generosDisponiveis.has(genero)) && <div className={styles.filtrosGenero} role="group" aria-label="Filtrar catálogo por gênero">
                        <span>Mostrar:</span>
                        {['todos', 'masculino', 'feminino'].filter((genero) => genero === 'todos' || generosDisponiveis.has(genero)).map((genero) =>
                            <button key={genero} type="button" disabled={carregando} aria-pressed={filtroGenero === genero}
                                className={filtroGenero === genero ? styles.filtroGeneroAtivo : ''} onClick={() => mudarFiltro(genero)}>
                                {{ todos: 'Todos', masculino: 'Masculino', feminino: 'Feminino' }[genero]}
                            </button>)}
                    </div>}
                    <div className={styles.cortes}>
                        {cortesPagina.map((corte) => {
                            const selecionado = escolhaCorte === 'catalogo' && String(corteSelecionado?.id_corte) === String(corte.id_corte);
                            return <article key={corte.id_corte} className={`${styles.cardCorte} ${selecionado ? styles.selecionado : ''}`}>
                                <div className={styles.imagemCorte}>
                                    <ImagemVisagismo url={corte.imagem_url} descricao={`Referência do catálogo: ${corte.nome}`} />
                                    {selecionado && <span className={styles.check}><FiCheck aria-hidden="true" /></span>}
                                </div>
                                <div className={styles.infoCorte}><h3>{corte.nome}</h3><span className={styles.generoCorte}>{generoDoCorte(corte.genero)}</span><p className={styles.descricaoResumida}>{corte.descricao || 'Veja os detalhes deste corte.'}</p></div>
                                <div className={styles.acoesCard}>
                                    <button type="button" className={styles.botaoDetalhes} disabled={carregando} onClick={() => setCorteDetalhes(corte)}>Ver mais<span className={styles.somenteLeitor}> sobre {corte.nome}</span></button>
                                    <button type="button" className={styles.botaoEscolher} disabled={carregando} aria-pressed={selecionado} onClick={() => selecionarCorte(corte)}>{selecionado ? 'Selecionado' : 'Escolher'}<span className={styles.somenteLeitor}> {corte.nome}</span></button>
                                </div>
                            </article>;
                        })}
                    </div>
                    {!cortesPagina.length && <p className={styles.semCortes}>{cortes.length ? 'Não há cortes disponíveis neste filtro.' : 'Este serviço ainda não tem cortes no catálogo. Você pode escolher durante o atendimento.'}</p>}
                    {totalPaginas > 1 && <nav className={styles.paginacao} aria-label="Paginação do catálogo">
                        <button type="button" disabled={carregando || paginaSegura === 1} onClick={() => setPagina(paginaSegura - 1)}>Anterior</button>
                        <span>Página {paginaSegura} de {totalPaginas}</span>
                        <button type="button" disabled={carregando || paginaSegura === totalPaginas} onClick={() => setPagina(paginaSegura + 1)}>Próxima</button>
                    </nav>}
                </div>}
            </div>

            {recomendacao && <div className={styles.detalhesAnalise}>
                <section className={styles.blocoAnalise} aria-label="Características observadas">
                    <h2>Características observadas</h2>
                    <dl className={styles.caracteristicas}>
                        {CAMPOS_CARACTERISTICAS.map(([campo, nome]) => <div key={campo}>
                            <dt>{nome}</dt><dd>{textoCaracteristica(caracteristicas[campo])}</dd>
                        </div>)}
                    </dl>
                    <h3>Cabelo atual</h3><p>{cabeloAtual || 'Não informado na análise'}</p>
                    {observacoes && <p className={styles.observacoes}>{observacoes}</p>}
                </section>
                <section className={styles.blocoAnalise} aria-label="Por que este corte">
                    <h2>Por que este corte</h2>
                    <p>{corteRecomendado?.motivo || 'O motivo não foi informado na análise.'}</p>
                </section>
            </div>}

            {imagemResultado && <figure className={styles.simulacao}>
                <h2>Simulação gerada</h2>
                <ImagemVisagismo url={imagemResultado} descricao={corteSelecionado ? `Simulação de ${corteSelecionado.nome}` : 'Simulação da cor escolhida'} indisponivel="Simulação não disponível" />
                {avisoSimulacao && <figcaption>{avisoSimulacao}</figcaption>}
            </figure>}
            {erro && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={fecharErro} focoAoFechar={botaoSimular} />}

            {temPintar && <section className={styles.secaoCor} aria-label="Escolha da cor">
                <h2>Escolha a cor</h2>
                <p>{pintarCabelo && pintarBarba ? 'A cor será aplicada ao cabelo e à barba.' : pintarBarba ? 'A cor será aplicada à barba.' : 'A cor será aplicada ao cabelo.'}</p>
                <div className={styles.categoriasCor}>
                    {categoriasCorVisiveis.map((categoria) => <button key={categoria.id} type="button" disabled={carregando}
                        className={`${styles.categoriaCor} ${categoriaAtiva === categoria.id ? styles.categoriaCorAtiva : ''}`}
                        aria-pressed={categoriaAtiva === categoria.id} onClick={() => setCategoriaCor(categoria.id)}>{categoria.nome}</button>)}
                </div>
                <div className={styles.cores} role="group" aria-label="Cores disponíveis">
                    {categoriasCorVisiveis.find((categoria) => categoria.id === categoriaAtiva)?.cores.map((cor) => <button
                        key={cor} type="button" disabled={carregando} aria-label={`Cor ${cor}`} aria-pressed={corSelecionada === cor}
                        className={`${styles.cor} ${corSelecionada === cor ? styles.corSelecionada : ''}`}
                        style={{ backgroundColor: cor }} onClick={() => setCorSelecionada(cor)} title={cor} />)}
                </div>
            </section>}
            <div className={styles.acoes}>
                <button type="button" className={styles.botaoVoltarAnalise} onClick={voltarEtapa} disabled={carregando}>Trocar foto ou analisar novamente</button>
                {imagemResultado && <button type="button" className={styles.botaoRefazer} disabled={carregando} onClick={refazerSimulacao}>Refazer simulação</button>}
                <button ref={botaoSimular} type="button" className={styles.botaoConfirmar} disabled={carregando || selecaoIncompleta} onClick={confirmarSelecao}>
                    {carregando ? 'Gerando simulação…' : imagemResultado || (modoPulado && !temPintar) ? 'Ir para agendamento' : apenasCor ? 'Gerar simulação de cor' : 'Gerar simulação'}
                </button>
            </div>
            {corteDetalhes && <div className={styles.overlayDetalhes} onClick={() => !carregando && setCorteDetalhes(null)}>
                <section ref={dialogoDetalhes} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="titulo-detalhes-corte"
                    className={styles.modalDetalhes} onClick={(evento) => evento.stopPropagation()}>
                    <header><div><span className={styles.sobreTitulo}>Detalhes do corte</span><h2 id="titulo-detalhes-corte">{corteDetalhes.nome}</h2></div><button type="button" className={styles.fecharDetalhes} aria-label="Fechar detalhes do corte" disabled={carregando} onClick={() => setCorteDetalhes(null)}><FiX aria-hidden="true" /></button></header>
                    <div className={styles.conteudoDetalhes}>
                        <div className={styles.fotoDetalhes}><ImagemVisagismo url={corteDetalhes.imagem_url} descricao={`Referência do catálogo: ${corteDetalhes.nome}`} /></div>
                        <div><dl className={styles.dadosCorte}><div><dt>Categoria</dt><dd>{categoriaDoCorte(corteDetalhes.categoria)}</dd></div><div><dt>Gênero</dt><dd>{generoDoCorte(corteDetalhes.genero)}</dd></div></dl><h3>Descrição</h3><p className={styles.descricaoCompleta}>{corteDetalhes.descricao || 'Descrição não informada no catálogo.'}</p></div>
                    </div>
                    <footer><button type="button" className={styles.botaoDetalhes} disabled={carregando} onClick={() => setCorteDetalhes(null)}>Fechar</button>{!recomendacao && !apenasCor && <button type="button" className={styles.botaoEscolher} disabled={carregando} onClick={() => { selecionarCorte(corteDetalhes); setCorteDetalhes(null); }}>Escolher este corte</button>}</footer>
                </section>
            </div>}
        </section>
    );
}
export default EtapaResultado;

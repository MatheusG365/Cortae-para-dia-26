import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import EtapaImagem from './EtapaImagem/EtapaImagem';
import EtapaResultado from './EtapaResultado/EtapaResultado';
import { urlDaApi, apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import useDialog from '../../components/useDialog';
import { assinaturaSimulacao, erroDaSelecao, normalizarAnalise, normalizarCatalogo, validarFotoSalva } from './visagismoState';
import { dadosEscolhaCorte, permiteEscolhaNoAtendimento } from '../../services/escolhaCorte';
import styles from './Visagismo.module.css';

function FluxoVisagismo() {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const idBarbearia = params.get('barbearia');
    const idsServicos = params.get('servicos') || '';
    const apenasCor = params.get('pular_analise') === 'true';
    const pintarCabelo = params.get('pintar_cabelo') === 'true';
    const pintarBarba = params.get('pintar_barba') === 'true';
    const temPintar = params.get('tem_pintar') === 'true' || pintarCabelo || pintarBarba;
    const alvoCor = pintarCabelo && pintarBarba ? 'ambos' : pintarBarba ? 'barba' : 'cabelo';
    const categoriaInicial = pintarBarba && !pintarCabelo ? 'pintar_barba' : 'pintar_cabelos';
    const [etapa, setEtapa] = useState(1);
    const [imagem, setImagem] = useState(null);
    const [arquivo, setArquivo] = useState(null);
    const [cortes, setCortes] = useState([]);
    const [selecaoCorte, setSelecaoCorte] = useState({ escolha: 'catalogo', corte: null });
    const corteSelecionado = selecaoCorte.corte;
    const escolhaCorte = selecaoCorte.escolha;
    const [generosServicos, setGenerosServicos] = useState([]);
    const [idVisagismo, setIdVisagismo] = useState(null);
    const [observacoes, setObservacoes] = useState('');
    const [caracteristicas, setCaracteristicas] = useState({});
    const [cabeloAtual, setCabeloAtual] = useState('');
    const [modoPulado, setModoPulado] = useState(apenasCor);
    const [resultadoSimulacao, setResultadoSimulacao] = useState(null);
    const [modalAberto, setModalAberto] = useState(false);
    const [carregando, setCarregando] = useState(false);
    const [erro, setErro] = useState('');
    const [corSelecionada, setCorSelecionada] = useState(null);
    const [categoriaCor, setCategoriaCor] = useState(categoriaInicial);
    const versao = useRef(0);
    const botaoSimular = useRef(null);
    const dialogo = useDialog(modalAberto, () => setModalAberto(false), false, botaoSimular);
    const assinaturaAtual = assinaturaSimulacao({ idBarbearia, idsServicos, idVisagismo, idCorte: corteSelecionado?.id_corte, cor: corSelecionada, alvo: alvoCor, categoriaCor });
    const imagemResultado = resultadoSimulacao?.assinatura === assinaturaAtual ? resultadoSimulacao.url : null;
    const avisoSimulacao = imagemResultado ? resultadoSimulacao.aviso : '';

    useEffect(() => () => {
        if (imagem?.startsWith('blob:')) URL.revokeObjectURL(imagem);
    }, [imagem]);
    useEffect(() => () => { versao.current += 1; }, []);

    const invalidarSimulacao = () => {
        versao.current += 1;
        setResultadoSimulacao(null);
        setModalAberto(false);
        setErro('');
        setCarregando(false);
    };
    const limparAnalise = () => {
        invalidarSimulacao();
        setIdVisagismo(null);
        setCortes([]);
        setSelecaoCorte({ escolha: 'catalogo', corte: null });
        setGenerosServicos([]);
        setObservacoes('');
        setCaracteristicas({});
        setCabeloAtual('');
        setCorSelecionada(null);
        setCategoriaCor(categoriaInicial);
    };
    const receberArquivo = (novoArquivo) => {
        limparAnalise();
        setArquivo(novoArquivo);
    };
    const selecionarCorte = (corte) => {
        if (String(corteSelecionado?.id_corte) === String(corte?.id_corte)) return;
        invalidarSimulacao();
        setSelecaoCorte({ escolha: 'catalogo', corte });
    };
    const selecionarEscolhaNoAtendimento = (escolha) => {
        if (!permiteEscolhaNoAtendimento({ modoPulado, temPintar, apenasCor }) || !['na_hora', 'profissional'].includes(escolha)) return;
        invalidarSimulacao();
        setSelecaoCorte({ escolha, corte: null });
    };
    const escolherCor = (cor) => {
        if (cor === corSelecionada) return;
        invalidarSimulacao();
        setCorSelecionada(cor);
    };
    const escolherCategoria = (categoria) => {
        if (categoria === categoriaCor) return;
        invalidarSimulacao();
        setCategoriaCor(categoria);
        setCorSelecionada(null);
    };
    const voltarEtapa = () => {
        limparAnalise();
        setEtapa(1);
    };
    const abrirResultado = () => {
        setEtapa(2);
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };
    const voltarParaServicos = () => { const query = new URLSearchParams({ barbearia: idBarbearia || '' }); const profissional = params.get('funcionario') || params.get('id_funcionario'); if (profissional) query.set('funcionario', profissional); navigate(`/selecionar-servicos?${query}`); };

    const avancarEtapa = async () => {
        if (carregando) return;
        if (!arquivo || !idBarbearia || !idsServicos) {
            setErro('Selecione a barbearia, os serviços e uma foto antes de continuar.');
            return;
        }
        limparAnalise();
        const requisicao = versao.current;
        setCarregando(true);
        try {
            const form = new FormData();
            form.append('imagem', arquivo);
            form.append('id_barbearia', idBarbearia);
            form.append('ids_servicos', idsServicos);
            const dados = await apiFetch(apenasCor ? '/visagismo/salvar-foto' : '/visagismo/analisar', { method: 'POST', body: form });
            if (requisicao !== versao.current) return;
            if (apenasCor) {
                validarFotoSalva(dados);
                setModoPulado(true);
            } else {
                const analise = normalizarAnalise(dados);
                const corte = { ...analise.corte, imagem_url: urlDaApi(analise.corte.imagem_url) };
                setCortes([corte]);
                setSelecaoCorte({ escolha: 'catalogo', corte });
                setObservacoes(analise.observacoes);
                setCaracteristicas(analise.caracteristicas);
                setCabeloAtual(analise.cabeloAtual);
                setModoPulado(false);
            }
            setIdVisagismo(dados.id_visagismo);
            setImagem(urlDaApi(dados.foto_url));
            abrirResultado();
        } catch (error) {
            if (requisicao === versao.current) setErro(mensagemDaApi(error));
        } finally { if (requisicao === versao.current) setCarregando(false); }
    };

    const pularVisagismo = async () => {
        if (carregando) return;
        if (!idBarbearia || !idsServicos) {
            setErro('Volte ao estabelecimento e escolha pelo menos um serviço.');
            return;
        }
        if (temPintar) {
            setErro('Para pintura é obrigatório enviar a foto e concluir a simulação antes de agendar.');
            return;
        }
        limparAnalise();
        const requisicao = versao.current;
        setCarregando(true);
        try {
            const dados = await apiFetch(`/visagismo/cortes?id_barbearia=${encodeURIComponent(idBarbearia)}&ids_servicos=${encodeURIComponent(idsServicos)}`);
            if (requisicao !== versao.current) return;
            const catalogo = normalizarCatalogo(dados);
            setCortes(catalogo.cortes.map((corte) => ({ ...corte, imagem_url: urlDaApi(corte.imagem_url) })));
            setGenerosServicos(catalogo.generosServicos);
            setModoPulado(true);
            setImagem(null);
            abrirResultado();
        } catch (error) { if (requisicao === versao.current) setErro(mensagemDaApi(error)); }
        finally { if (requisicao === versao.current) setCarregando(false); }
    };

    const confirmarSelecao = async () => {
        if (carregando) return;
        const erroSelecao = erroDaSelecao({ apenasCor, temPintar, corteSelecionado, corSelecionada, idVisagismo, modoPulado, escolhaCorte });
        if (erroSelecao) { setErro(erroSelecao); return; }
        if (imagemResultado || (modoPulado && !temPintar)) {
            const destino = new URLSearchParams({ barbearia: idBarbearia, servicos: idsServicos });
            const profissional = params.get('funcionario') || params.get('id_funcionario');
            if (profissional) destino.set('funcionario', profissional);
            const escolha = dadosEscolhaCorte({ escolhaCorte, idCorte: corteSelecionado?.id_corte, idVisagismo });
            if (escolha.escolha_corte) destino.set('escolha_corte', escolha.escolha_corte);
            if (escolha.id_corte) destino.set('corte', escolha.id_corte);
            if (escolha.id_visagismo) destino.set('visagismo', escolha.id_visagismo);
            navigate(`/agendamento?${destino.toString()}`);
            return;
        }
        setCarregando(true); setErro('');
        const requisicao = versao.current;
        const assinatura = assinaturaAtual;
        try {
            const dados = await apiFetch(`/visagismo/${idVisagismo}/simular`, {
                method: 'POST', body: JSON.stringify({ id_corte: corteSelecionado?.id_corte, cor: corSelecionada, alvo: alvoCor })
            });
            if (requisicao !== versao.current) return;
            if (!dados.imagem_url) throw new Error('O servidor não retornou a imagem da simulação. Tente novamente.');
            setResultadoSimulacao({ url: urlDaApi(dados.imagem_url), assinatura, aviso: dados.aviso || (dados.referencia_utilizada === false && !apenasCor ? 'A referência visual não estava disponível. A simulação utilizou o nome e a descrição do corte cadastrado.' : '') });
            setModalAberto(true);
        } catch (error) { if (requisicao === versao.current) setErro(mensagemDaApi(error)); }
        finally { if (requisicao === versao.current) setCarregando(false); }
    };

    return (
        <div className={styles.pagina}>
            <main className={styles.conteudo}>
                <div className={styles.indicadorEtapas} aria-hidden="true">
                    <span className={etapa === 1 ? styles.ativa : ''}></span>
                    <span className={etapa === 2 ? styles.ativa : ''}></span>
                </div>
                {erro && etapa === 1 && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />}
                {etapa === 1 && <EtapaImagem imagem={imagem} arquivo={arquivo} setImagem={setImagem}
                    setArquivo={receberArquivo} avancarEtapa={avancarEtapa} pularVisagismo={pularVisagismo}
                    voltar={voltarParaServicos} carregando={carregando} apenasCor={apenasCor} pintarObrigatorio={temPintar} />}
                {etapa === 2 && <EtapaResultado imagem={imagem} cortes={cortes} observacoes={observacoes}
                    caracteristicas={caracteristicas} cabeloAtual={cabeloAtual} apenasCor={apenasCor}
                    modoPulado={modoPulado} imagemResultado={imagemResultado} avisoSimulacao={avisoSimulacao} carregando={carregando} erro={erro}
                    fecharErro={() => setErro('')} botaoSimular={botaoSimular}
                    corteSelecionado={corteSelecionado} selecionarCorte={selecionarCorte}
                    escolhaCorte={escolhaCorte} generosServicos={generosServicos} selecionarEscolhaNoAtendimento={selecionarEscolhaNoAtendimento}
                    voltarEtapa={voltarEtapa} confirmarSelecao={confirmarSelecao} refazerSimulacao={invalidarSimulacao}
                    corSelecionada={corSelecionada} setCorSelecionada={escolherCor}
                    categoriaCor={categoriaCor} setCategoriaCor={escolherCategoria}
                    temPintar={temPintar} pintarCabelo={pintarCabelo} pintarBarba={pintarBarba} />}
            </main>
            {modalAberto && imagemResultado && (
                <div className={styles.overlay} onClick={() => setModalAberto(false)}>
                    <div ref={dialogo} tabIndex={-1} role="dialog" aria-modal="true" aria-label="Simulação gerada" className={styles.modal} onClick={(e) => e.stopPropagation()}>
                        <h2>Sua simulação está pronta!</h2>
                        <img src={imagemResultado} alt={corteSelecionado ? `Simulação de ${corteSelecionado.nome}` : 'Simulação da cor escolhida'} className={styles.fotoModal} />
                        {avisoSimulacao && <p>{avisoSimulacao}</p>}
                        <p>Confira o resultado. Depois de fechar, você pode refazer a simulação ou seguir para o agendamento.</p>
                        <div className={styles.modalAcoes}>
                            <button type="button" className={styles.botaoModalSecundario} onClick={invalidarSimulacao}>REFAZER SIMULAÇÃO</button>
                            <button type="button" className={styles.botaoModal} onClick={() => setModalAberto(false)}>CONFIRMAR</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
export default function Visagismo() {
    const [params] = useSearchParams();
    // Uma troca de serviços ou de alvo inicia outro fluxo e invalida requisições da sessão anterior.
    return <FluxoVisagismo key={params.toString()} />;
}

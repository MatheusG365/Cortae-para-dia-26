import { chaveItem, corpoQuantidade, nomeVariacao } from './comercialState';
import { somenteDigitos } from '../../services/cadastroState';
import { novoEndereco } from '../../services/cepEnderecoState';
import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { mensagemDaApi } from '../../services/api';
import { marketplace, json } from './marketplaceApi';
import useMarketplace from './useMarketplace';
import { Aviso, Carregamento, FotoProduto, LojaLayout, ModalLoja } from './MarketplaceUI';
import { agruparCarrinho, moeda, novoCheckoutId } from './marketplaceState';
import styles from './Marketplace.module.css';
import useTermosUso from '../../services/useTermosUso';
import TermosAceite from '../../components/TermosAceite/TermosAceite';
import ResumoTaxa from '../../components/ResumoTaxa/ResumoTaxa';
import useResumoOperacao from '../../services/useResumoOperacao';
import { useAuth } from '../../contexts/useAuth';
import CupomCheckout from './CupomCheckout';
import EnderecosCheckout from './EnderecosCheckout';
import { orientacaoCheckout, pendenciasEndereco } from './checkoutState';
import checkoutStyles from './Checkout.module.css';

function Checkout({ grupo, fechar }) {
    const navigate = useNavigate();
    const { usuario } = useAuth();
    const chave = useRef(novoCheckoutId());
    const [endereco, setEndereco] = useState(() => novoEndereco(usuario));
    const [retirada, setRetirada] = useState(false);
    const [cotacoes, setCotacoes] = useState([]);
    const [cotacao, setCotacao] = useState('');
    const [contextoCotacoes, setContextoCotacoes] = useState('');
    const [ocupado, setOcupado] = useState(false);
    const [calculoAtivo, setCalculoAtivo] = useState('');
    const [erro, setErro] = useState('');
    const [erroFrete, setErroFrete] = useState('');
    const [cupomInput, setCupomInput] = useState('');
    const [cupom, setCupom] = useState('');
    const freteController = useRef(null);
    const assinaturaCarrinho = JSON.stringify(grupo.itens.map(item => [chaveItem(item), item.quantidade, item.preco]));
    const contextoFrete = JSON.stringify([grupo.id_barbearia, assinaturaCarrinho, endereco, retirada]);
    const calculando = calculoAtivo === contextoFrete;
    const cotacoesAtuais = contextoCotacoes === contextoFrete ? cotacoes : [];
    const selecionada = cotacoesAtuais.find(item => item.id_cotacao === cotacao);
    const podeConferir = (retirada || !!selecionada) && pendenciasEndereco(endereco).length === 0;
    const previa = useResumoOperacao('/marketplace/pedidos/resumo', { id_barbearia: grupo.id_barbearia, cupom, retirada, id_cotacao: retirada ? null : selecionada?.id_cotacao || '', endereco }, podeConferir);
    const termos = useTermosUso({ versaoEsperada: previa.resumo?.termos_versao });
    const orientacao = orientacaoCheckout({ endereco, retirada, selecionada, calculando, temCotacoes: cotacoesAtuais.length > 0, previa, termos });
    const subtotal = grupo.itens.reduce((total, item) => total + Number(item.preco) * item.quantidade, 0);
    useEffect(() => () => { freteController.current?.abort(); }, [contextoFrete]);

    function invalidarEntrega() {
        freteController.current?.abort();
        setCalculoAtivo('');
        setCotacoes([]);
        setCotacao('');
        setContextoCotacoes('');
        setErro('');
        setErroFrete('');
        previa.recarregar();
    }
    function atualizarEndereco(proximo) {
        invalidarEntrega();
        setEndereco(proximo);
    }
    function mudarRetirada(valor) {
        invalidarEntrega();
        setRetirada(valor);
    }
    async function calcular() {
        freteController.current?.abort();
        const controller = new AbortController();
        freteController.current = controller;
        const contexto = contextoFrete;
        setErro('');
        setErroFrete('');
        setCalculoAtivo(contexto);
        setCotacao('');
        setCotacoes([]);
        previa.recarregar();
        try {
            const dados = await marketplace('/frete', { ...json('POST', { id_barbearia: grupo.id_barbearia, cep: endereco.cep }), signal: controller.signal });
            if (!controller.signal.aborted) {
                setCotacoes(dados.cotacoes || []);
                setContextoCotacoes(contexto);
                if (!dados.cotacoes?.length) setErroFrete('Nenhuma transportadora disponível para este CEP. Você pode escolher retirada.');
            }
        } catch (falha) {
            if (!controller.signal.aborted) { setCotacoes([]); setErroFrete(mensagemDaApi(falha)); }
        } finally { if (!controller.signal.aborted) setCalculoAtivo(''); }
    }
    async function comprar(evento) {
        evento.preventDefault();
        setErro('');
        if (!previa.resumo) { setErro('Aguarde a confirmação dos valores antes de continuar.'); return; }
        if (!retirada && !selecionada) { setErro('Calcule e selecione uma opção de entrega.'); return; }
        const snapshot = { id_barbearia: grupo.id_barbearia, cupom, retirada, id_cotacao: retirada ? null : selecionada.id_cotacao, endereco: { ...endereco }, confirmacao_resumo: previa.resumo.confirmacao_resumo, chave_idempotencia: chave.current };
        setOcupado(true);
        try {
            await termos.aceitar();
            const dados = await marketplace('/pedidos', json('POST', snapshot));
            navigate(`/marketplace/pedidos/${dados.pedido.id_pedido}`);
        } catch (falha) {
            if (falha.status === 409 || falha.status === 428) { previa.recarregar(); termos.recarregar(); }
            setErro(mensagemDaApi(falha));
        } finally { setOcupado(false); }
    }
    return <ModalLoja idLoja={grupo.id_barbearia} titulo={`Finalizar compra · ${grupo.barbearia}`} fechar={fechar} ocupado={ocupado} className={checkoutStyles.modal}>
        <form onSubmit={comprar} className={checkoutStyles.formulario}>
            <div className={checkoutStyles.conteudo}>
                <section className={checkoutStyles.entrega} aria-label="Forma de recebimento">
                    <div className={checkoutStyles.etapa}><span>1</span><div><h3>Como deseja receber?</h3><p>Escolha entrega ou retirada na loja.</p></div></div>
                    <div className={styles.entregaEscolha}>
                        <label><input type="radio" name="entrega" checked={!retirada} onChange={() => mudarRetirada(false)} disabled={ocupado} />Receber em casa</label>
                        <label><input type="radio" name="entrega" checked={retirada} onChange={() => mudarRetirada(true)} disabled={ocupado} />Retirar na barbearia · grátis</label>
                    </div>
                    <EnderecosCheckout endereco={endereco} atualizar={atualizarEndereco} usuario={usuario} ocupado={ocupado} />
                    {!retirada && <section className={checkoutStyles.frete} aria-label="Frete e prazo de entrega">
                        <h3>Frete e prazo</h3><p>Calcule as opções para seu CEP e selecione como receber.</p>
                        <button className={styles.primario} type="button" disabled={ocupado || calculando || somenteDigitos(endereco.cep).length !== 8} onClick={calcular}>{calculando ? 'Buscando opções…' : cotacoesAtuais.length ? 'Recalcular frete' : 'Calcular opções de entrega'}</button>
                        {somenteDigitos(endereco.cep).length !== 8 && <small>Informe um CEP com oito dígitos para consultar a entrega.</small>}
                        <Aviso erro={erroFrete} />
                        {cotacoesAtuais.length > 0 && <fieldset className={checkoutStyles.opcoes}><legend>Escolha uma opção de entrega</legend>{cotacoesAtuais.map(item => <label key={item.id_cotacao} className={checkoutStyles.opcao}>
                            <input type="radio" name="cotacao" value={item.id_cotacao} checked={cotacao === item.id_cotacao} onChange={() => setCotacao(item.id_cotacao)} required disabled={ocupado} />
                            <span><strong>{item.transportadora} · {item.servico}</strong><small>Até {item.prazo_dias} dias úteis</small></span><b>{moeda(item.preco)}</b>
                        </label>)}</fieldset>}
                    </section>}
                    {retirada && <p className={checkoutStyles.retirada}>Retirada em {grupo.barbearia}, sem custo de frete. Aguarde o aviso de que seu pedido está pronto.</p>}
                </section>
                <aside className={checkoutStyles.resumo} aria-label="Resumo do pedido">
                    <div className={checkoutStyles.etapa}><span>2</span><div><h3>Resumo do pedido</h3><p>{grupo.barbearia}</p></div></div>
                    <ul className={checkoutStyles.itens}>{grupo.itens.map(item => <li key={chaveItem(item)}><span>{item.quantidade} × {item.nome}{item.variacao ? ` · ${nomeVariacao(item.variacao)}` : ''}</span><strong>{moeda(Number(item.preco) * item.quantidade)}</strong></li>)}</ul>
                    {previa.resumo ? <ResumoTaxa resumo={previa.resumo} /> : <div className={checkoutStyles.valores}><p><span>Produtos</span><strong>{moeda(subtotal)}</strong></p><p><span>Frete</span><strong>{retirada ? 'Grátis' : selecionada ? moeda(selecionada.preco) : 'A calcular'}</strong></p><small>O total, com descontos e taxa, aparece após conferir os dados e a entrega.</small></div>}
                    <details className={checkoutStyles.cupom}><summary>{cupom ? `Cupom: ${cupom}` : 'Adicionar cupom (opcional)'}</summary><CupomCheckout entrada={cupomInput} cupom={cupom} atualizar={setCupomInput} aplicar={setCupom} remover={() => { setCupom(''); setCupomInput(''); }} ocupado={ocupado} previa={previa} podeConferir={podeConferir} /></details>
                    <Aviso erro={erro || previa.erro} />
                    {(previa.erro || termos.erro) && <button type="button" disabled={ocupado} onClick={() => { previa.recarregar(); termos.recarregar(); }}>Conferir valores e termos novamente</button>}
                    <TermosAceite termos={termos} disabled={ocupado} />
                    <p id="checkout-orientacao" role="status" className={orientacao ? checkoutStyles.pendente : checkoutStyles.pronto}>{ocupado ? 'Criando seu pedido…' : orientacao || 'Tudo conferido. Você já pode criar seu pedido.'}</p>
                    <div className={checkoutStyles.finalizar}><button className={styles.primario} aria-describedby="checkout-orientacao" disabled={ocupado || !!orientacao}>{ocupado ? 'Criando pedido…' : 'Criar pedido'}</button><button type="button" onClick={fechar} disabled={ocupado}>Continuar no carrinho</button></div>
                    <p className={checkoutStyles.nota}>O pagamento por Pix será feito na próxima etapa.</p>
                </aside>
            </div>
        </form>
    </ModalLoja>;
}
export default function MarketplaceCarrinho() {
    const estado = useMarketplace('/carrinho'); const [erro, setErro] = useState(''); const [ocupado, setOcupado] = useState(false); const [grupo, setGrupo] = useState(null);
    async function quantidade(item, n) { setErro(''); setOcupado(true); try { await marketplace(`/carrinho/${item.id_produto}`, json('PUT', corpoQuantidade(item,n))); estado.recarregar(); } catch (e) { setErro(mensagemDaApi(e)); } finally { setOcupado(false); } }
    const grupos = agruparCarrinho(estado.dados?.itens);
    return <LojaLayout titulo="Seu carrinho" descricao="Cada barbearia recebe um pedido separado. Confira quantidades e escolha como receber."><Aviso erro={erro} /><Carregamento estado={estado} vazio="Seu carrinho está vazio.">{grupos.length > 0 && <div className={styles.lista}>{grupos.map(g => <section key={g.id_barbearia} className={styles.painel}><h2>{g.barbearia}</h2>{g.itens.map(i => <article key={chaveItem(i)} className={styles.itemCarrinho}><FotoProduto className={styles.fotoItem} url={i.imagem || i.imagens?.[0]} nome={i.nome} /><div><Link to={`/marketplace/produtos/${i.id_produto}`}><h3>{i.nome}</h3></Link><p>{i.variacao ? `${nomeVariacao(i.variacao)} · ` : ''}{moeda(i.preco)} por unidade</p><small>{i.disponivel === false ? 'Indisponível. Remova este item para finalizar.' : `${i.estoque} em estoque`}</small></div><div className={styles.quantidade}><button aria-label={`Diminuir quantidade: ${i.nome}`} disabled={ocupado || i.quantidade <= 1} onClick={() => quantidade(i, i.quantidade - 1)}>−</button><span aria-label="Quantidade">{i.quantidade}</span><button aria-label={`Aumentar quantidade: ${i.nome}`} disabled={ocupado || i.quantidade >= i.estoque} onClick={() => quantidade(i, i.quantidade + 1)}>+</button></div><strong>{moeda(Number(i.preco) * i.quantidade)}</strong><button disabled={ocupado} className={styles.textoBotao} onClick={() => quantidade(i, 0)}>Remover</button></article>)}<div className={styles.linha}><p>Subtotal <strong>{moeda(g.itens.reduce((t, i) => t + Number(i.preco) * i.quantidade, 0))}</strong></p><button className={styles.primario} onClick={() => setGrupo(g)} disabled={ocupado || g.itens.some(i => i.quantidade > i.estoque || i.disponivel === false)}>Finalizar nesta loja</button></div></section>)}</div>}</Carregamento><Link className={styles.voltar} to="/marketplace">Continuar comprando</Link>{grupo && <Checkout grupo={grupo} fechar={() => setGrupo(null)} />}</LojaLayout>;
}

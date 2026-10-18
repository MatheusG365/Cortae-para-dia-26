import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { FiShoppingBag, FiHeart, FiShoppingCart, FiPackage, FiX, FiStar, FiBookmark } from 'react-icons/fi';
import { urlDaApi } from '../../services/api';
import { useAuth } from '../../contexts/useAuth';
import useDialog from '../../components/useDialog';
import { moeda, urlFoto } from './marketplaceState';
import styles from './Marketplace.module.css';
import { caminhoDaLoja } from './lojaState';
import useTemaLoja from './useTemaLoja';

export function FotoProduto({ url, nome, className = '' }) {
    const [falhas, setFalhas] = useState([]);
    const segura = urlFoto(url);
    return segura && !falhas.includes(segura) ? <img className={className} src={urlDaApi(segura)} alt={nome} loading="lazy" referrerPolicy="no-referrer" onError={() => setFalhas(anteriores => anteriores.includes(segura) ? anteriores : [...anteriores, segura])} /> : <div className={`${styles.semFoto} ${className}`}><FiShoppingBag aria-hidden="true" /><span>Imagem indisponível</span></div>;
}
export function LojaLayout({ titulo, descricao, children, acoes, embutido = false, idLoja }) {
    const { usuario } = useAuth();
    const tema = useTemaLoja(embutido ? null : idLoja);
    const Elemento = embutido ? 'section' : 'main';
    const Titulo = embutido ? 'h2' : 'h1';
    return <Elemento id={embutido ? 'loja-barbearia' : undefined} style={tema} className={`${styles.pagina} ${embutido ? styles.lojaPreview : ''}`}><header className={styles.cabecalho}><div><span className={styles.eyebrow}>{embutido || idLoja ? 'LOJA DO ESTABELECIMENTO' : 'CORTAÊ · MARKETPLACE'}</span><Titulo>{titulo}</Titulo>{descricao && <p>{descricao}</p>}</div>{acoes}</header><nav className={styles.nav} aria-label="Marketplace"><NavLink end to="/marketplace"><FiShoppingBag />Todas as lojas</NavLink>{Number(usuario?.tipo) === 1 && <><NavLink to="/marketplace/favoritos"><FiHeart />Favoritos</NavLink><NavLink to="/marketplace/lista-desejos"><FiBookmark />Lista de desejos</NavLink><NavLink to="/marketplace/carrinho"><FiShoppingCart />Carrinho</NavLink><NavLink to="/marketplace/pedidos"><FiPackage />Meus pedidos</NavLink></>}{[0, 2].includes(Number(usuario?.tipo)) && <Link to="/gestao-marketplace">Gerenciar loja</Link>}</nav>{children}</Elemento>;
}
export function Aviso({ erro, sucesso }) { return <>{erro && <p className={styles.erro} role="alert">{erro}</p>}{sucesso && <p className={styles.sucesso} role="status">{sucesso}</p>}</>; }
export function Carregamento({ estado, vazio, children }) {
    if (estado.carregando) return <p className={styles.vazio} role="status">Carregando…</p>;
    if (estado.erro) return <div className={styles.vazio}><Aviso erro={estado.erro} /><button onClick={estado.recarregar}>Tentar novamente</button></div>;
    return children || <p className={styles.vazio}>{vazio || 'Nenhum registro encontrado.'}</p>;
}
export function ModalLoja({ titulo, fechar, ocupado = false, children, idLoja, className = '' }) {
    const ref = useDialog(true, fechar, ocupado);
    const tema = useTemaLoja(idLoja);
    return <div style={tema} className={styles.fundoModal} onMouseDown={e => { if (e.target === e.currentTarget && !ocupado) fechar(); }}><section ref={ref} className={`${styles.modal} ${className}`} role="dialog" aria-modal="true" aria-labelledby="modal-loja-titulo" tabIndex={-1}><header><h2 id="modal-loja-titulo">{titulo}</h2><button type="button" aria-label="Fechar diálogo" disabled={ocupado} onClick={fechar}><FiX /></button></header>{children}</section></div>;
}
export function ProdutoCard({ produto, favorito, onFavoritar, ocupado, desejado, onDesejar }) {
    return <article className={styles.produtoCard}><Link to={`/marketplace/produtos/${produto.id_produto}`} className={styles.capa}><FotoProduto key={produto.imagens?.[0]} url={produto.imagens?.[0]} nome={produto.nome} />{Number(produto.estoque) <= 0 && <span className={styles.selo}>Esgotado</span>}</Link><div className={styles.cardConteudo}><div className={styles.selosComerciais}>{produto.em_promocao && <span>Promoção</span>}{produto.lancamento && <span>Lançamento</span>}{produto.tem_variacoes && <span>Com variações</span>}</div><Link className={styles.vendedor} to={caminhoDaLoja(produto.id_barbearia)}>{produto.barbearia}</Link><Link to={`/marketplace/produtos/${produto.id_produto}`}><h2>{produto.nome}</h2></Link><p>{produto.descricao}</p><div className={styles.linha}><div>{produto.em_promocao && <del className={styles.muted}>{moeda(produto.preco_original)}</del>}<strong className={styles.preco}>{produto.tem_variacoes ? 'A partir de ' : ''}{moeda(produto.preco)}</strong></div>{onFavoritar && <button className={favorito ? styles.favoritoAtivo : styles.icone} aria-label={`${favorito ? 'Remover dos' : 'Adicionar aos'} favoritos: ${produto.nome}`} aria-pressed={Boolean(favorito)} disabled={ocupado} onClick={() => onFavoritar(produto)}><FiHeart /></button>}</div><div className={styles.linha}><small><FiStar aria-hidden="true" /> {Number(produto.media_avaliacoes || 0).toFixed(1)} · {produto.total_avaliacoes || 0} avaliações</small><Link className={styles.linkDetalhes} to={`/marketplace/produtos/${produto.id_produto}`}>Ver produto</Link></div>{onDesejar && <button disabled={ocupado} onClick={() => onDesejar(produto)} aria-pressed={Boolean(desejado)}><FiBookmark />Remover da lista</button>}</div></article>;
}



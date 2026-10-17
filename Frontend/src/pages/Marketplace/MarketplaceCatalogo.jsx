import { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import Select from '../../components/Select/Select';
import { useAuth } from '../../contexts/useAuth';
import { mensagemDaApi } from '../../services/api';
import { marketplace, json } from './marketplaceApi';
import useMarketplace from './useMarketplace';
import { Aviso, Carregamento, LojaLayout, ProdutoCard } from './MarketplaceUI';
import { filtrosDoCatalogo } from './lojaState';
import { FiArrowRight, FiSearch, FiShoppingBag } from 'react-icons/fi';
import { caminhoDaLoja } from './lojaState';
import styles from './Marketplace.module.css';

export default function MarketplaceCatalogo(props) {
    const { usuario } = useAuth();
    return <CatalogoConteudo key={`${props.idLoja ?? 'geral'}:${usuario?.id_usuario ?? usuario?.id ?? ''}:${usuario?.tipo ?? ''}`} {...props} />;
}

function CatalogoConteudo({ favoritos = false, desejos = false, idLoja = null, embutido = false }) {
    const { usuario } = useAuth(); const cliente = Number(usuario?.tipo) === 1;
    const [params] = useSearchParams(); const navigate = useNavigate(); const local = useLocation(); const [busca, setBusca] = useState(params.get('busca') || '');
    const estado = useMarketplace(idLoja != null ? `/barbearias/${encodeURIComponent(idLoja)}` : desejos ? '/lista-desejos' : favoritos ? '/favoritos' : '/produtos', filtrosDoCatalogo(params, idLoja));
    const [erro, setErro] = useState(''); const [ocupado, setOcupado] = useState(null); const [marcados, setMarcados] = useState({});
    useEffect(() => {
        if (!cliente || favoritos) return;
        const controle = new AbortController();
        marketplace('/favoritos', { signal: controle.signal }).then(d => { if (!controle.signal.aborted) setMarcados(atual => ({ ...Object.fromEntries((d.produtos || []).map(p => [p.id_produto, true])), ...atual })); }).catch(e => { if (!controle.signal.aborted && !(e.status === 401 && !desejos)) setErro(mensagemDaApi(e)); });
        return () => controle.abort();
    }, [cliente, favoritos, desejos]);
    function filtrar(chave, valor) { const novos = new URLSearchParams(params); valor ? novos.set(chave, valor) : novos.delete(chave); navigate({ pathname: local.pathname, search: `?${novos}`, hash: embutido ? '#loja-barbearia' : local.hash }, { preventScrollReset: true }); }
    async function favoritar(produto) {
        setErro(''); setOcupado(produto.id_produto);
        const atual = marcados[produto.id_produto] ?? (favoritos || produto.favorito);
        try { await marketplace(`/favoritos/${produto.id_produto}`, json('PUT', { favorito: !atual })); setMarcados(m => ({ ...m, [produto.id_produto]: !atual })); if (favoritos) estado.recarregar(); } catch (e) { setErro(mensagemDaApi(e)); } finally { setOcupado(null); }
    }
    const produtos = estado.dados?.produtos || [];
    const loja = estado.dados?.barbearia;
    return <LojaLayout embutido={embutido} titulo={idLoja != null ? loja ? `Loja de ${loja.nome}` : 'Loja da barbearia' : desejos ? 'Sua lista de desejos' : favoritos ? 'Seus favoritos' : 'Produtos das nossas barbearias'} descricao={idLoja != null ? 'Produtos vendidos por este estabelecimento. Escolha entrega ou retirada na barbearia.' : desejos ? 'Planeje suas próximas compras. Esta lista é independente dos favoritos.' : favoritos ? 'Guarde os produtos que você quer conhecer melhor.' : 'Todas as lojas em um só lugar. Encontre seu produto e compre diretamente da barbearia.'}>
        {idLoja != null && <div className={styles.acoesLoja}><Link className={styles.botaoLink} to="/marketplace">Explorar todas as lojas <FiArrowRight /></Link></div>}
        {idLoja == null && !favoritos && !desejos && (estado.dados?.barbearias || []).length > 0 && <section className={styles.lojasFaixa} aria-label="Lojas das barbearias"><div><span className={styles.eyebrow}>COMPRE DA SUA BARBEARIA</span><h2>Conheça as lojas</h2></div><div className={styles.lojasLista}>{estado.dados.barbearias.map(s => <Link key={s.id_barbearia ?? s.id} to={caminhoDaLoja(s.id_barbearia ?? s.id)}><FiShoppingBag /><span>{s.nome}</span><FiArrowRight /></Link>)}</div></section>}
        {!favoritos && !desejos && <form className={styles.filtros} onSubmit={e => { e.preventDefault(); filtrar('busca', busca); }}><label className={styles.busca}>O que você procura?<input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Nome, marca ou descrição" type="search" /></label>{idLoja == null && <label>Barbearia<Select value={params.get('id_barbearia') || ''} onChange={e => filtrar('id_barbearia', e.target.value)}><option value="">Todas as lojas</option>{(estado.dados?.barbearias || []).map(s => <option key={s.id_barbearia ?? s.id} value={s.id_barbearia ?? s.id}>{s.nome}</option>)}</Select></label>}<label>Categoria<Select value={params.get('categoria') || ''} onChange={e => filtrar('categoria', e.target.value)}><option value="">Todas as categorias</option>{(estado.dados?.categorias || []).map(c => <option key={c} value={c}>{c}</option>)}</Select></label><label>Ordenar<Select value={params.get('ordem') || 'recentes'} onChange={e => filtrar('ordem', e.target.value)}><option value="recentes">Mais recentes</option><option value="nome">Nome</option><option value="preco_asc">Menor preço</option><option value="preco_desc">Maior preço</option></Select></label><label>Destaques<Select value={params.get('destaque') || ''} onChange={e => filtrar('destaque',e.target.value)}><option value="">Todos os produtos</option><option value="promocoes">Em promoção</option><option value="lancamentos">Lançamentos</option></Select></label><button className={styles.primario}><FiSearch />Buscar</button></form>}
        <Aviso erro={erro} /><Carregamento estado={estado} vazio={desejos ? 'Sua lista de desejos está vazia.' : favoritos ? 'Você ainda não favoritou nenhum produto.' : idLoja != null && !params.get('busca') && !params.get('categoria') ? 'Esta barbearia ainda não tem produtos à venda.' : 'Nenhum produto corresponde à busca.'}>{produtos.length > 0 && <><div className={styles.resultadoCabecalho}><h2>{params.get('busca') ? 'Resultados da busca' : 'Explore os produtos'}</h2><span>{estado.dados?.total ?? produtos.length} produto(s)</span></div><div className={styles.gradeProdutos}>{produtos.map(p => <ProdutoCard key={p.id_produto} desejado={p.desejado} onDesejar={desejos ? async () => { setErro('');setOcupado(p.id_produto);try { await marketplace(`/lista-desejos/${p.id_produto}`,json('PUT',{desejado:false}));estado.recarregar(); } catch(e) { setErro(mensagemDaApi(e)); } finally { setOcupado(null); } } : undefined} produto={p} favorito={marcados[p.id_produto] ?? (favoritos || p.favorito)} ocupado={ocupado != null} onFavoritar={cliente ? favoritar : undefined} />)}</div></>}</Carregamento>
    </LojaLayout>;
}




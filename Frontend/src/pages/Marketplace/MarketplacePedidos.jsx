import { nomeVariacao } from './comercialState';
import { useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { mensagemDaApi } from '../../services/api';
import { marketplace, json } from './marketplaceApi';
import useMarketplace from './useMarketplace';
import { Aviso, Carregamento, FotoProduto, LojaLayout, ModalLoja } from './MarketplaceUI';
import { moeda, dataHora, statusPedido, statusPagamento, pagamentoDoPedido } from './marketplaceState';
import styles from './Marketplace.module.css';
import ResumoTaxa from '../../components/ResumoTaxa/ResumoTaxa';
import CartaoArkhe, { ReciboCartao } from '../../components/CartaoArkhe/CartaoArkhe';
import { CARTAO_INCERTO, dadosCartao, cartaoEmConferencia, erroCartaoIncerto, podePagarPedido, reciboCartao } from '../../services/cartaoArkhe';

export default function MarketplacePedidos() {
    const { id } = useParams(); const estado = useMarketplace(id ? `/pedidos/${id}` : '/pedidos');
    const [erro, setErro] = useState(''); const [sucesso, setSucesso] = useState(''); const [ocupado, setOcupado] = useState(false); const [confirmacao, setConfirmacao] = useState(false); const [pagamento, setPagamento] = useState(null);
    const trava = useRef(false);
    const [conferencia, setConferencia] = useState(null);
    const pedido = estado.dados?.pedido; const pedidos = estado.dados?.pedidos || [];
    const pix = pagamentoDoPedido(id, pedido, pagamento);
    const bloqueado = conferencia === String(id) || cartaoEmConferencia(pedido);
    const recibo = reciboCartao(pix);
    async function atualizarPedido() {
        const atual = await marketplace(`/pedidos/${id}`);
        if (['aprovado', 'recusado'].includes(atual.pedido?.pagamento?.cartao_estado) || atual.pedido?.pagamento_status === 'pago') setConferencia(null);
        estado.recarregar(); return atual.pedido;
    }
    async function agir(acao) {
        if (trava.current) return;
        trava.current = true; setErro(''); setSucesso(''); setOcupado(true); let enviado = false;
        try {
            if (acao === 'pix') {
                const atual = await marketplace(`/pedidos/${id}`);
                if (bloqueado || !podePagarPedido(atual.pedido)) throw new Error('Já existe pagamento ou cobrança. Atualize o pedido.');
            }
            if (acao === 'pagamento' && (pedido?.pagamento?.metodo === 'cartao' || bloqueado)) { await atualizarPedido(); return; }
            enviado = acao !== 'pagamento';
            const dados = await marketplace(`/pedidos/${id}${acao === 'pagamento' ? '/pagamento' : `/${acao}`}`, acao === 'pagamento' ? {} : json('POST', {}));
            if (dados.pagamento) setPagamento({ id, dados: dados.pagamento });
            setConfirmacao(false); estado.recarregar();
        } catch (e) { if (enviado && acao === 'pix' && erroCartaoIncerto(e)) setConferencia(String(id)); setErro(mensagemDaApi(e)); }
        finally { trava.current = false; setOcupado(false); }
    }
    async function pagarCartao(campos) {
        if (trava.current) return;
        trava.current = true; setOcupado(true); setErro(''); let enviado = false;
        try {
            const atual = await marketplace(`/pedidos/${id}`);
            if (bloqueado || !podePagarPedido(atual.pedido)) throw new Error('Já existe pagamento ou cobrança. Atualize o pedido.');
            if (Math.abs(Number(atual.pedido.total) - Number(pedido.total)) > 0.005) throw new Error('O valor mudou. Atualize e confira o novo total.');
            enviado = true;
            const dados = await marketplace(`/pedidos/${id}/cartao`, json('POST', dadosCartao(campos, atual.pedido.total)));
            setPagamento({ id, dados: dados.pagamento });
            if (!reciboCartao(dados)) { setConferencia(String(id)); setErro(CARTAO_INCERTO); }
        } catch (e) {
            const incerto = enviado && erroCartaoIncerto(e);
            if (incerto) setConferencia(String(id));
            setErro(incerto ? CARTAO_INCERTO : mensagemDaApi(e));
        } finally {
            if (enviado) { try { await atualizarPedido(); } catch { setErro('Não foi possível atualizar o pedido. Confira o banco antes de outra cobrança.'); } }
            trava.current = false; setOcupado(false);
        }
    }
    async function copiar() { try { await navigator.clipboard.writeText(pix.codigo_pix); setSucesso('Código Pix copiado.'); } catch { setErro('Não foi possível copiar. Selecione o código abaixo e copie manualmente.'); } }
    return <LojaLayout titulo={id ? `Pedido #${id}` : 'Meus pedidos'} descricao="Acompanhe suas compras, pagamentos e entregas."><Aviso erro={erro} sucesso={sucesso} /><Carregamento estado={estado} vazio="Você ainda não fez compras.">{id ? pedido && <>
        <section className={styles.painel}><div className={styles.linha}><div><span className={styles.status}>{statusPedido[pedido.status] || pedido.status}</span><h2>{pedido.barbearia}</h2><small>{dataHora(pedido.criado_em)}</small></div><strong className={styles.precoGrande}>{moeda(pedido.total)}</strong></div>{pedido.itens.map(i => <article key={`${i.id_produto}:${i.id_variacao ?? 'base'}`} className={styles.itemCarrinho}><FotoProduto className={styles.fotoItem} url={i.imagem} nome={i.nome} /><div><Link to={`/marketplace/produtos/${i.id_produto}`}><h3>{i.nome}</h3></Link><p>{nomeVariacao(i.variacao) && <span>{nomeVariacao(i.variacao)} · </span>}{i.quantidade} × {moeda(i.preco)}</p>{pedido.status === 'entregue' && <Link className={styles.linkDetalhes} to={`/marketplace/produtos/${i.id_produto}`}>Avaliar produto</Link>}</div><strong>{moeda(i.total)}</strong></article>)}{pedido.resumo ? <ResumoTaxa resumo={pedido.resumo} /> : <div className={styles.totalResumo}><span>Produtos<strong>{moeda(pedido.subtotal)}</strong></span><span>Frete<strong>{moeda(pedido.frete)}</strong></span><span>Total<strong>{moeda(pedido.total)}</strong></span></div>}</section>
        <div className={styles.duasColunas}><section className={styles.painel}><h2>Pagamento</h2>
            <p>Status: <strong>{statusPagamento[pedido.pagamento_status] || pedido.pagamento_status || 'Não iniciado'}</strong></p>
            <ReciboCartao recibo={recibo} />
            {bloqueado && <p role="status">{CARTAO_INCERTO}</p>}
            {!bloqueado && !recibo && podePagarPedido(pedido) && <><CartaoArkhe key={id} total={pedido.total} onSubmit={pagarCartao} disabled={ocupado} /><button className={styles.primario} disabled={ocupado} onClick={() => agir('pix')}>Gerar cobrança Pix</button></>}
            <button disabled={ocupado} onClick={() => agir('pagamento')}>Consultar pagamento</button>
            {pix?.metodo !== 'cartao' && pix?.codigo_pix && <div className={styles.pix}><QRCodeSVG value={pix.codigo_pix} size={180} /><label>Pix copia e cola<textarea value={pix.codigo_pix} readOnly rows={3} /></label><button disabled={ocupado} onClick={copiar}>Copiar código Pix</button><small>{moeda(pix.valor)} · A confirmação é consultada no banco.</small></div>}
            <p className={styles.nota}>Uma cobrança em processamento ou com resultado incerto exige conferência antes de qualquer nova tentativa.</p></section><section className={styles.painel}><h2>{pedido.retirada ? 'Retirada na barbearia' : 'Entrega'}</h2>{pedido.retirada ? <p>Acompanhe o status e retire quando estiver pronto.</p> : <><p>{pedido.endereco?.logradouro}, {pedido.endereco?.numero}{pedido.endereco?.complemento ? ` · ${pedido.endereco.complemento}` : ''}<br />{pedido.endereco?.bairro} · {pedido.endereco?.cidade}/{pedido.endereco?.uf}<br />CEP {pedido.endereco?.cep}</p><p>{pedido.entrega?.rastreio ? `Rastreamento: ${pedido.entrega.rastreio}` : 'Código de rastreamento ainda não disponível.'}</p><button disabled={ocupado} onClick={estado.recarregar}>Atualizar pedido</button></>}</section></div>{pedido.pode_cancelar && <button disabled={ocupado} onClick={() => setConfirmacao(true)}>Cancelar pedido</button>}
    </> : pedidos.length > 0 && <div className={styles.lista}>{pedidos.map(p => <article key={p.id_pedido} className={styles.painel}><div className={styles.linha}><div><span className={styles.status}>{statusPedido[p.status] || p.status}</span><h2>Pedido #{p.id_pedido} · {p.barbearia}</h2><p>{dataHora(p.criado_em)} · {p.retirada ? 'Retirada' : 'Entrega'}</p></div><strong>{moeda(p.total)}</strong><Link className={styles.botaoLink} to={`/marketplace/pedidos/${p.id_pedido}`}>Ver pedido</Link></div></article>)}</div>}</Carregamento>{id && <Link className={styles.voltar} to="/marketplace/pedidos">← Todos os pedidos</Link>}{confirmacao && <ModalLoja titulo="Cancelar pedido?" fechar={() => setConfirmacao(false)} ocupado={ocupado}><p>Os produtos reservados voltarão ao estoque e este pedido será encerrado.</p><div className={styles.acoes}><button disabled={ocupado} onClick={() => setConfirmacao(false)}>Manter pedido</button><button className={styles.primario} disabled={ocupado} onClick={() => agir('cancelar')}>Confirmar cancelamento</button></div></ModalLoja>}</LojaLayout>;
}




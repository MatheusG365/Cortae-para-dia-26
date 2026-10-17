import { useEffect, useState } from 'react';
import { useAuth } from '../../contexts/useAuth';
import { periodoDoMes as periodoInicial } from '../../services/agendaState';
import { dinheiro, momento } from '../../services/gestaoState';
import { mensagemDaApi } from '../../services/api';

const situacoes = { anulada: 'Anulada', aguardando_pagamento_cliente: 'Aguardando pagamento do cliente', repasse_pendente: 'Repasse pendente' };

export default function TaxasPlataformaGestao({ requisicao, styles, idSalao }) {
    const { usuario } = useAuth();
    const [filtro, setFiltro] = useState(periodoInicial);
    const [periodo, setPeriodo] = useState(periodoInicial);
    const [revisao, setRevisao] = useState(0);
    const [estado, setEstado] = useState(null);
    const identidade = JSON.stringify([usuario?.id_usuario, idSalao, periodo, revisao]);
    const atual = estado?.identidade === identidade ? estado : null;
    useEffect(() => {
        const controller = new AbortController();
        requisicao('/taxas-plataforma', { signal: controller.signal }, periodo)
            .then(dados => { if (!controller.signal.aborted) setEstado({ identidade, dados }); })
            .catch(e => { if (!controller.signal.aborted) setEstado({ identidade, erro: mensagemDaApi(e) }); });
        return () => controller.abort();
    }, [requisicao, periodo, identidade]);
    const dados = atual?.dados;
    return <section><h2>Taxas da plataforma</h2><p className={styles.subtitulo}>Confira a taxa de 1,5% registrada em cada compra ou agendamento deste estabelecimento. A base considera produtos ou serviços, sem o frete. Registros antigos permanecem sem cobrança retroativa.</p><form className={styles.filtros} onSubmit={e => { e.preventDefault(); setPeriodo({ ...filtro }); setRevisao(a => a + 1); }}><label>De<input type="date" required value={filtro.inicio} max={filtro.fim} onChange={e => setFiltro({ ...filtro, inicio: e.target.value })} /></label><label>Até<input type="date" required value={filtro.fim} min={filtro.inicio} onChange={e => setFiltro({ ...filtro, fim: e.target.value })} /></label><button type="submit">Consultar taxas</button></form><p className={styles.subtitulo}>Período da consulta: {periodo.inicio} a {periodo.fim}, conforme a data de registro da operação.</p>{!atual && <p role="status">Consultando taxas…</p>}{atual?.erro && <p role="alert" className={styles.erro}>{atual.erro}</p>}{dados && <><div className={styles.metricas}><article><span>Taxas registradas no histórico</span><strong>{dinheiro(dados.totais?.registradas)}</strong></article><article><span>Taxas previstas / devidas</span><strong>{dinheiro(dados.totais?.previstas)}</strong></article><article><span>Repasse pendente · cliente pagou</span><strong>{dinheiro(dados.totais?.repasse_pendente)}</strong></article></div><p className={styles.subtitulo}>{dados.informacao || 'Este relatório não executa nem confirma repasses à plataforma.'}</p><p className={styles.subtitulo}>“Previstas / devidas” exclui operações anuladas e inclui operações ainda aguardando pagamento do cliente. “Repasse pendente” indica pagamento do cliente confirmado; não indica recebimento da taxa pela plataforma.</p>{!dados.taxas?.length ? <p className={styles.placeholder}>Nenhuma taxa registrada neste período. A política precisa estar ativa para registrar taxas em novas operações.</p> : <div className={styles.tabela}><table><thead><tr><th>Operação</th><th>Responsável pela taxa</th><th>Base sem frete</th><th>Frete</th><th>Taxa registrada</th><th>Taxa devida</th><th>Total do cliente</th><th>Líquido do estabelecimento</th><th>Situação</th></tr></thead><tbody>{dados.taxas.map(t => <tr key={`${t.tipo}:${t.id_operacao}`}><td>{t.tipo === 'pedido' ? 'Compra' : 'Agendamento'} #{t.id_operacao}<br /><small>{momento(t.criado_em)} · {t.status}</small></td><td>{t.taxa_pagador === 'cliente' ? 'Cliente · acréscimo no total' : 'Barbearia · sem acréscimo ao cliente'}</td><td>{dinheiro(t.valor_base)}</td><td>{dinheiro(t.frete)}</td><td>{dinheiro(t.taxa_valor)}<br /><small>{Number(t.taxa_percentual).toLocaleString('pt-BR')}%</small></td><td>{dinheiro(t.taxa_devida)}</td><td>{dinheiro(t.valor_total_cliente)}</td><td>{dinheiro(t.valor_liquido_barbearia)}<br /><small>Sem frete; valor informativo</small></td><td>{situacoes[t.situacao] || t.situacao}<br /><small>{t.pagamento_cliente_confirmado ? 'Pagamento do cliente confirmado' : 'Pagamento do cliente pendente'}</small></td></tr>)}</tbody></table></div>}</>}</section>;
}

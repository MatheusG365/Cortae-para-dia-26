import { useCallback, useEffect, useState } from 'react';
import { periodoDoMes } from '../../services/agendaState';
import { dinheiro, momento } from '../../services/gestaoState';
import { mensagemDaApi } from '../../services/api';

function Tabela({ titulo, colunas, linhas, styles }) {
    return <section className={styles.cartao}><h3>{titulo}</h3>{linhas.length ? <div className={styles.tabela}><table><thead><tr>{colunas.map(([key, nome]) => <th key={key}>{nome}</th>)}</tr></thead><tbody>{linhas.map((linha, i) => <tr key={i}>{colunas.map(([key, , formatar]) => <td key={key}>{formatar ? formatar(linha[key]) : linha[key] ?? '—'}</td>)}</tr>)}</tbody></table></div> : <p>Sem registros para esse período.</p>}</section>;
}
export default function RelatoriosGestao({ requisicao, styles }) {
    const [filtro, setFiltro] = useState(periodoInicial); const [periodo, setPeriodo] = useState(periodoInicial);
    const [dados, setDados] = useState(null); const [erro, setErro] = useState(''); const [ocupado, setOcupado] = useState(false);
    const carregar = useCallback(async () => { setOcupado(true); setErro(''); try { setDados(await requisicao('/relatorios', {}, periodo)); } catch (e) { setErro(mensagemDaApi(e)); } finally { setOcupado(false); } }, [requisicao, periodo]);
    useEffect(() => { queueMicrotask(carregar); }, [carregar]);
    return <><h2>Relatórios dos atendimentos</h2><form className={styles.filtros} onSubmit={(e) => { e.preventDefault(); if (filtro.inicio > filtro.fim) { setErro('A data inicial deve preceder a final.'); return; } setPeriodo({ ...filtro }); }}><label>De<input required type="date" value={filtro.inicio} onChange={(e) => setFiltro({ ...filtro, inicio: e.target.value })} /></label><label>Até<input required type="date" value={filtro.fim} onChange={(e) => setFiltro({ ...filtro, fim: e.target.value })} /></label><label>Cliente inativo após (dias)<input required type="number" min="1" max="3650" value={filtro.inativos_dias} onChange={(e) => setFiltro({ ...filtro, inativos_dias: e.target.value })} /></label><button type="submit" disabled={ocupado}>Consultar relatórios</button></form>{erro && <p role="alert" className={styles.erro}>{erro}</p>}{ocupado && <p role="status">Carregando relatórios…</p>}
        {dados && <><div className={styles.metricas}>{[['agendamentos', 'Agendamentos'], ['realizados', 'Realizados'], ['cancelados', 'Cancelados'], ['faltas', 'Faltas'], ['clientes', 'Clientes'], ['valor_realizado', 'Valor dos atendimentos realizados']].map(([key, nome]) => <article key={key}><span>{nome}</span><strong>{key === 'valor_realizado' ? dinheiro(dados.resumo?.[key] || 0) : dados.resumo?.[key] ?? 0}</strong></article>)}</div><p className={styles.subtitulo}>O valor de atendimentos realizados é o preço registrado na reserva. Recebimentos e despesas ficam na área Caixa e comissões.</p>
            <Tabela styles={styles} titulo="Serviços procurados" colunas={[["nome", "Serviço"], ["quantidade", "Quantidade"], ["valor", "Valor registrado", dinheiro]]} linhas={dados.servicos || []} />
            <Tabela styles={styles} titulo="Profissionais" colunas={[["nome", "Profissional"], ["quantidade", "Agendamentos"], ["realizados", "Realizados"], ["valor", "Valor realizado", dinheiro]]} linhas={dados.profissionais || []} />
            <Tabela styles={styles} titulo="Horários mais procurados" colunas={[["hora", "Horário"], ["quantidade", "Agendamentos"]]} linhas={dados.horarios || []} />
            <Tabela styles={styles} titulo="Clientes frequentes" colunas={[["nome", "Cliente"], ["telefone", "Telefone"], ["total_agendamentos", "Agendamentos"], ["atendimentos_realizados", "Realizados"], ["faltas", "Faltas"], ["ultima_visita", "Última visita", momento]]} linhas={dados.clientes || []} />
            <Tabela styles={styles} titulo={`Clientes inativos há ${periodo.inativos_dias} dias`} colunas={[["nome", "Cliente"], ["telefone", "Telefone"], ["email", "E-mail"], ["ultima_visita", "Última visita", momento], ["dias_inativo", "Dias sem visita"]]} linhas={dados.inativos || []} />
        </>}
    </>;
}

const periodoInicial = () => ({ ...periodoDoMes(), inativos_dias: '90' });

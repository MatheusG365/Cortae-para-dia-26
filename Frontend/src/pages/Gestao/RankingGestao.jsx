import Select from '../../components/Select/Select';
import { useEffect, useState } from 'react';
import { Trophy, Star, Scissors, TrendingUp, MessageSquare } from 'lucide-react';
import { periodoDoMes } from '../../services/agendaState';
import { dinheiro, momento } from '../../services/gestaoState';
import { rotuloMedia } from '../../services/avaliacaoState';
import { mensagemDaApi } from '../../services/api';
import { AvaliacaoResumo } from '../../components/AvaliacaoAtendimento/AvaliacaoAtendimento';
import styles from './RankingGestao.module.css';

const criterios = { faturamento: 'Valor dos serviços realizados', atendimentos: 'Atendimentos realizados', avaliacao: 'Média das avaliações' };

export default function RankingGestao({ requisicao }) {
    const [filtro, setFiltro] = useState(periodoInicial);
    const [periodo, setPeriodo] = useState(periodoInicial);
    const [ranking, setRanking] = useState(null);
    const [comentarios, setComentarios] = useState(null);
    const [erro, setErro] = useState(''); const [erroComentarios, setErroComentarios] = useState('');
    const [carregando, setCarregando] = useState(true); const [lendoComentarios, setLendoComentarios] = useState(true);
    const [pagina, setPagina] = useState(1); const [profissional, setProfissional] = useState('');
    const [revisao, setRevisao] = useState(0);
    useEffect(() => {
        let ativo = true; const controller = new AbortController();
        const carregar = async () => {
            await Promise.resolve(); if (!ativo) return;
            setCarregando(true); setErro(''); setRanking(null);
            try { const dados = await requisicao('/ranking', { signal: controller.signal }, periodo); if (ativo) setRanking(dados); }
            catch (error) { if (ativo && error.name !== 'AbortError') setErro(mensagemDaApi(error)); }
            finally { if (ativo) setCarregando(false); }
        };
        carregar(); return () => { ativo = false; controller.abort(); };
    }, [requisicao, periodo, revisao]);
    useEffect(() => {
        let ativo = true; const controller = new AbortController();
        const carregar = async () => {
            await Promise.resolve(); if (!ativo) return;
            setLendoComentarios(true); setErroComentarios(''); setComentarios(null);
            try { const dados = await requisicao('/avaliacoes', { signal: controller.signal }, { inicio: periodo.inicio, fim: periodo.fim, pagina, ...(profissional ? { id_funcionario: profissional } : {}) }); if (ativo) setComentarios(dados); }
            catch (error) { if (ativo && error.name !== 'AbortError') setErroComentarios(mensagemDaApi(error)); }
            finally { if (ativo) setLendoComentarios(false); }
        };
        carregar(); return () => { ativo = false; controller.abort(); };
    }, [requisicao, periodo, pagina, profissional, revisao]);
    const aplicar = (evento) => {
        evento.preventDefault();
        if (filtro.inicio > filtro.fim) { setErro('A data inicial deve ser anterior ou igual à data final.'); return; }
        setPagina(1); setPeriodo({ ...filtro });
    };
    const resumo = ranking?.resumo;
    return <div className={styles.pagina}>
        <header className={styles.cabecalho}><span className={styles.icone}><Trophy size={24} aria-hidden="true" /></span><div><p className={styles.sobre}>DESEMPENHO DA EQUIPE</p><h2>Ranking e avaliações</h2><p>Reconheça os resultados de cada profissional e acompanhe a experiência dos clientes.</p></div></header>
        <form className={styles.filtros} onSubmit={aplicar}>
            <label>Data inicial<input type="date" required value={filtro.inicio} onChange={(e) => setFiltro({ ...filtro, inicio: e.target.value })} /></label>
            <label>Data final<input type="date" required value={filtro.fim} onChange={(e) => setFiltro({ ...filtro, fim: e.target.value })} /></label>
            <label className={styles.criterio}>Ordenar ranking por<Select value={filtro.ordenar} onChange={(e) => setFiltro({ ...filtro, ordenar: e.target.value })}>{Object.entries(criterios).map(([valor, titulo]) => <option key={valor} value={valor}>{titulo}</option>)}</Select></label>
            <button type="submit" disabled={carregando}>Consultar ranking</button>
        </form>
        {erro && <div className={styles.erro} role="alert">{erro}<button type="button" onClick={() => setRevisao((valor) => valor + 1)}>Tentar novamente</button></div>}
        {carregando && <p role="status" className={styles.vazio}>Carregando desempenho da equipe…</p>}
        {!carregando && ranking && <>
            <p className={styles.periodo}>Atendimentos de {momento(ranking.periodo?.inicio)} a {momento(ranking.periodo?.fim)}</p>
            <section className={styles.metricas} aria-label="Resumo do desempenho">
                <article><Scissors size={20} aria-hidden="true" /><span>Atendimentos realizados</span><strong>{resumo?.atendimentos_realizados ?? 0}</strong><small>Concluídos no período</small></article>
                <article><TrendingUp size={20} aria-hidden="true" /><span>Valor dos serviços realizados</span><strong>{dinheiro(resumo?.faturamento)}</strong><small>Valores registrados no atendimento</small></article>
                <article><Star size={20} aria-hidden="true" /><span>Média das avaliações</span><strong>{rotuloMedia(resumo?.media_nota)}</strong><small>{resumo?.total_avaliacoes ?? 0} avaliação(ões)</small></article>
            </section>
            <p className={styles.nota}>O valor dos serviços realizados usa o histórico de cada atendimento. Não representa necessariamente dinheiro recebido.</p>
            {resumo?.sem_valor_historico > 0 && <p className={styles.aviso}>{resumo.sem_valor_historico} atendimento(s) sem valor histórico registrado ficam fora dos valores financeiros.</p>}
            {resumo?.sem_profissional?.atendimentos_realizados > 0 && <p className={styles.aviso}>{resumo.sem_profissional.atendimentos_realizados} atendimento(s) sem profissional vinculado entram no resumo geral e ficam fora do ranking.</p>}
            <section className={styles.secao}><div className={styles.tituloSecao}><div><h3>Profissionais</h3><p>{criterios[ranking.criterio] || criterios[periodo.ordenar]}. Empates compartilham a mesma posição.</p></div><span>{ranking.profissionais?.length || 0} na equipe</span></div>
                {ranking.profissionais?.length ? <div className={styles.tabela}><table><caption className={styles.somenteLeitor}>Ranking dos profissionais no período consultado</caption><thead><tr><th>Posição</th><th>Profissional</th><th>Realizados</th><th>Valor dos serviços</th><th>Avaliações</th></tr></thead><tbody>{ranking.profissionais.map((item) => <tr key={item.id_funcionario}>
                    <td data-label="Posição"><span className={`${styles.posicao} ${item.posicao === 1 ? styles.primeiro : ''}`}>{item.posicao == null ? '—' : `${item.posicao}º`}</span></td>
                    <td data-label="Profissional"><strong>{item.nome}</strong><small>{item.ativo === false ? 'Inativo · histórico preservado' : 'Ativo'}</small></td>
                    <td data-label="Realizados">{item.atendimentos_realizados}</td>
                    <td data-label="Valor dos serviços"><strong>{dinheiro(item.faturamento)}</strong>{item.sem_valor_historico > 0 && <small>{item.sem_valor_historico} sem valor registrado</small>}</td>
                    <td data-label="Avaliações"><strong className={styles.media}><Star size={15} aria-hidden="true" />{rotuloMedia(item.media_nota)}</strong><small>{item.total_avaliacoes} avaliação(ões)</small></td>
                </tr>)}</tbody></table></div> : <p className={styles.vazio}>Nenhum profissional cadastrado neste estabelecimento.</p>}
            </section>
        </>}
        <section className={styles.secao} aria-labelledby="titulo-comentarios"><div className={styles.tituloSecao}><div><h3 id="titulo-comentarios"><MessageSquare size={20} aria-hidden="true" />Avaliações dos atendimentos</h3><p>Notas e comentários dos clientes atendidos no período consultado.</p></div></div>
            <label className={styles.filtroComentario}>Profissional das avaliações<Select value={profissional} onChange={(e) => { setProfissional(e.target.value); setPagina(1); }} disabled={!ranking}><option value="">Toda a equipe</option>{(ranking?.profissionais || []).map((item) => <option key={item.id_funcionario} value={item.id_funcionario}>{item.nome}</option>)}</Select></label>
            {erroComentarios && <div role="alert" className={styles.erro}>{erroComentarios}<button type="button" onClick={() => setRevisao((valor) => valor + 1)}>Tentar novamente</button></div>}
            {lendoComentarios && <p role="status" className={styles.vazio}>Carregando avaliações…</p>}
            {!lendoComentarios && comentarios && <><div className={styles.comentarios}>{comentarios.avaliacoes?.map((item) => <article key={item.id_agendamento}><div className={styles.autor}><strong>{item.cliente_nome || 'Cliente'}</strong><span>{item.funcionario_nome || 'Sem profissional vinculado'} · {momento(item.inicio_em)}</span></div><AvaliacaoResumo avaliacao={item} /></article>)}</div>
                {!comentarios.avaliacoes?.length && <p className={styles.vazio}>Nenhuma avaliação para este período e profissional.</p>}
                {comentarios.paginas > 1 && <nav className={styles.paginacao} aria-label="Páginas das avaliações"><button type="button" disabled={pagina <= 1 || lendoComentarios} onClick={() => setPagina((valor) => valor - 1)}>Anterior</button><span>Página {comentarios.pagina} de {comentarios.paginas} · {comentarios.total} avaliações</span><button type="button" disabled={pagina >= comentarios.paginas || lendoComentarios} onClick={() => setPagina((valor) => valor + 1)}>Próxima</button></nav>}
            </>}
        </section>
    </div>;
}

const periodoInicial = () => ({ ...periodoDoMes(), ordenar: 'faturamento' });

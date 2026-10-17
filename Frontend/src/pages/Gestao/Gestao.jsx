import MetasGestao from './MetasGestao';
import { barbeariasDaResposta } from '../../services/cadastroState';
import Select from '../../components/Select/Select';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowUpRight, CalendarDays, ChartNoAxesCombined, ContactRound, ReceiptText, ShieldCheck, Store, Target, Trophy, UsersRound, WalletCards } from 'lucide-react';
import { useAuth } from '../../contexts/useAuth';
import { apiFetch, mensagemDaApi, queryDaApi } from '../../services/api';
import AgendaGestao from './AgendaGestao';
import EquipeGestao from './EquipeGestao';
import ClientesGestao from './ClientesGestao';
import FinanceiroGestao from './FinanceiroGestao';
import RelatoriosGestao from './RelatoriosGestao';
import LogsGestao from './LogsGestao';
import RankingGestao from './RankingGestao';
import TaxasPlataformaGestao from './TaxasPlataformaGestao';
import styles from './Gestao.module.css';

const abas = [['agenda', 'Agenda', CalendarDays], ['equipe', 'Equipe e serviços', UsersRound], ['clientes', 'Clientes', ContactRound], ['financeiro', 'Caixa e comissões', WalletCards], ['taxas', 'Taxas da plataforma', ReceiptText], ['ranking', 'Ranking e avaliações', Trophy], ['metas','Metas',Target], ['relatorios', 'Relatórios', ChartNoAxesCombined], ['logs', 'Auditoria', ShieldCheck]];
export default function Gestao() {
    const { usuario } = useAuth(); const tipo = Number(usuario?.tipo);
    const [params, setParams] = useSearchParams();
    const [saloes, setSaloes] = useState([]); const [erro, setErro] = useState('');
    const navegacaoRef = useRef(null);
    const idSalao = tipo === 0 ? params.get('id_barbearia') || '' : String(usuario?.id_usuario ?? usuario?.id ?? '');
    const aba = tipo === 3 ? (params.get('aba') === 'metas' ? 'metas' : 'agenda') : params.get('aba') || 'agenda';
    const abasVisiveis = abas.filter(([key]) => tipo === 3 ? ['agenda','metas'].includes(key) : key !== 'logs' || tipo === 0);
    useEffect(() => {
        const navegacao = navegacaoRef.current;
        if (!navegacao) return;
        const mostrarAbaAtiva = () => {
            const ativa = navegacao.querySelector('[aria-current="page"]');
            if (!ativa || navegacao.scrollWidth <= navegacao.clientWidth) return;
            const limite = navegacao.getBoundingClientRect();
            const item = ativa.getBoundingClientRect();
            if (item.left >= limite.left && item.right <= limite.right) return;
            navegacao.scrollTo({ left: Math.max(0, navegacao.scrollLeft + item.left - limite.left - (navegacao.clientWidth - item.width) / 2) });
        };
        mostrarAbaAtiva();
        const observador = new ResizeObserver(mostrarAbaAtiva);
        observador.observe(navegacao);
        return () => observador.disconnect();
    }, [aba, tipo]);
    useEffect(() => {
        if (tipo !== 0) return;
        const controller = new AbortController();
        apiFetch('/barbearias-disponiveis', { signal: controller.signal }).then((dados) => setSaloes(barbeariasDaResposta(dados))).catch((e) => { if (e.name !== 'AbortError') setErro(mensagemDaApi(e)); });
        return () => controller.abort();
    }, [tipo]);
    const requisicao = useCallback((rota, options = {}, filtro = {}) => {
        const query = new URLSearchParams(filtro);
        if (tipo === 0 && idSalao) query.set('id_barbearia', idSalao);
        return apiFetch(`/gestao${rota}${queryDaApi(query)}`, options);
    }, [tipo, idSalao]);
    const props = { requisicao, tipo, idSalao, styles };
    return <main className={styles.pagina}>
        <header className={styles.cabecalho}><p>GESTÃO DO ESTABELECIMENTO</p><h1>{tipo === 3 ? 'Sua agenda' : 'Rotina da barbearia'}</h1><p>Organize atendimentos, profissionais, clientes e valores do seu estabelecimento.</p></header>
        {tipo === 0 && aba !== 'logs' && <label>Barbearia<Select value={idSalao} onChange={(e) => { const novos = new URLSearchParams(params); novos.set('id_barbearia', e.target.value); setParams(novos); }}><option value="">Selecione uma barbearia</option>{saloes.map((s) => <option key={s.id} value={s.id}>{s.nome}</option>)}</Select></label>}
        <div className={styles.navegacaoGestao}>
            <nav ref={navegacaoRef} className={styles.abas} aria-label="Áreas de gestão" style={{ '--quantidade-abas': abasVisiveis.length }}>{abasVisiveis.map(([key, label, Icone]) => { const query = new URLSearchParams({ aba: key }); if (tipo === 0 && idSalao) query.set('id_barbearia', idSalao); return <Link key={key} to={`/gestao?${query}`} aria-current={aba === key ? 'page' : undefined}><Icone size={18} aria-hidden="true" /><span>{label}</span></Link>; })}</nav>
            {abasVisiveis.length > 1 && <p className={styles.dicaNavegacao}>Deslize para ver todas as áreas de gestão.</p>}
        </div>
        {[0, 2].includes(tipo) && <aside className={styles.faixaLoja} aria-label="Loja do estabelecimento">
            <div className={styles.lojaInformacao}><span className={styles.lojaIcone}><Store size={22} aria-hidden="true" /></span><div><h2>Loja do estabelecimento</h2><p>Organize seus produtos, estoque e pedidos.</p></div></div>
            <Link className={styles.lojaAcao} to={`/gestao-marketplace${tipo === 0 && idSalao ? `?id_barbearia=${idSalao}` : ''}`}>Gerenciar loja<ArrowUpRight size={18} aria-hidden="true" /></Link>
        </aside>}
        {erro && <p role="alert" className={styles.erro}>{erro}</p>}
        {tipo === 0 && !idSalao && aba !== 'logs' ? <p className={styles.placeholder}>Selecione a barbearia para abrir os dados.</p> : <section key={`${idSalao}:${aba}`}>
            {aba === 'taxas' && [0, 2].includes(tipo) && <TaxasPlataformaGestao {...props} />}
            {aba === 'metas' && <MetasGestao {...props} />}{aba === 'agenda' && <AgendaGestao {...props} />}{aba === 'equipe' && tipo !== 3 && <EquipeGestao {...props} />}{aba === 'clientes' && tipo !== 3 && <ClientesGestao {...props} />}{aba === 'financeiro' && tipo !== 3 && <FinanceiroGestao {...props} />}{aba === 'ranking' && tipo !== 3 && <RankingGestao {...props} />}{aba === 'relatorios' && tipo !== 3 && <RelatoriosGestao {...props} />}{aba === 'logs' && tipo === 0 && <LogsGestao {...props} />}
        </section>}
    </main>;
}

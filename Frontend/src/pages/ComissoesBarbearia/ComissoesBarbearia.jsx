import { barbeariasDaResposta } from '../../services/cadastroState';
import { dinheiroZero as dinheiro, momentoCurto as momento } from '../../services/formatacao';
import Select from '../../components/Select/Select';
import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../contexts/useAuth';
import { apiFetch, mensagemDaApi } from '../../services/api';
import { periodoDoMes as periodoInicial } from '../../services/agendaState';
import styles from './ComissoesBarbearia.module.css';


export default function ComissoesBarbearia() {
    const { usuario } = useAuth();
    const admin = Number(usuario?.tipo) === 0;
    const [params] = useSearchParams();
    const [filtro, setFiltro] = useState(() => ({ ...periodoInicial(), id_usuario: params.get('id_usuario') || params.get('barbearia') || '' }));
    const [periodo, setPeriodo] = useState(null);
    const [dados, setDados] = useState(null);
    const [barbearias, setBarbearias] = useState([]);
    const [carregando, setCarregando] = useState(false);
    const [erro, setErro] = useState('');
    const [erroBarbearias, setErroBarbearias] = useState('');
    useEffect(() => {
        if (!admin) return undefined;
        const controller = new AbortController();
        apiFetch('/barbearias-disponiveis', { signal: controller.signal })
            .then((resposta) => setBarbearias(barbeariasDaResposta(resposta)))
            .catch((falha) => { if (falha.name !== 'AbortError') setErroBarbearias(mensagemDaApi(falha)); });
        return () => controller.abort();
    }, [admin]);
    useEffect(() => {
        if (admin && !periodo?.id_usuario) return undefined;
        let ativo = true;
        const controller = new AbortController();
        const carregar = async () => {
            await Promise.resolve();
            if (!ativo) return;
            setCarregando(true); setErro(''); setDados(null);
            const alvo = periodo || periodoInicial();
            const query = new URLSearchParams({ inicio: alvo.inicio, fim: alvo.fim });
            if (admin) query.set('id_usuario', alvo.id_usuario);
            try { const resposta = await apiFetch(`/barbearia/comissoes?${query}`, { signal: controller.signal }); if (ativo) setDados(resposta); }
            catch (falha) { if (ativo) setErro(mensagemDaApi(falha)); }
            finally { if (ativo) setCarregando(false); }
        };
        carregar();
        return () => { ativo = false; controller.abort(); };
    }, [admin, periodo]);
    return <main className={styles.pagina}>
        <header><p className={styles.sobre}>COMISSÕES DA EQUIPE</p><h1>Valores para pagamento manual</h1><p>Comissões calculadas sobre atendimentos realizados. Confira quanto pagar a cada profissional. Registre os pagamentos já efetuados na área Caixa e comissões.</p><Link to={`/gestao?aba=financeiro${admin && (periodo?.id_usuario || filtro.id_usuario) ? `&id_barbearia=${periodo?.id_usuario || filtro.id_usuario}` : ''}`}>Abrir controle de comissões pagas e pendentes</Link></header>
        <form className={styles.filtro} onSubmit={(evento) => { evento.preventDefault(); if (filtro.inicio > filtro.fim) { setErro('A data inicial deve ser anterior à data final.'); return; } setPeriodo({ ...filtro }); }}>
            {admin && <label>Barbearia<Select required value={filtro.id_usuario} onChange={(evento) => setFiltro((atual) => ({ ...atual, id_usuario: evento.target.value }))}><option value="">Selecione a barbearia</option>{barbearias.map((item) => <option key={item.id} value={item.id}>{item.nome}</option>)}</Select></label>}
            <label>De<input required type="date" value={filtro.inicio} onChange={(evento) => setFiltro((atual) => ({ ...atual, inicio: evento.target.value }))} /></label>
            <label>Até<input required type="date" value={filtro.fim} onChange={(evento) => setFiltro((atual) => ({ ...atual, fim: evento.target.value }))} /></label>
            <button type="submit" disabled={carregando}>Consultar comissões</button>
        </form>
        {erroBarbearias && <p role="alert" className={styles.erro}>Não foi possível carregar as barbearias: {erroBarbearias}</p>}
        {erro && <p role="alert" className={styles.erro}>{erro}</p>}
        {carregando && <p role="status">Calculando o relatório…</p>}
        {admin && !periodo && <p>Selecione a barbearia e consulte o período.</p>}
        {dados && <>
            {admin && <p><strong>Barbearia: {barbearias.find((item) => String(item.id) === String(periodo?.id_usuario))?.nome || `#${periodo?.id_usuario}`}</strong></p>}
            <p>Período consultado: {dados.inicio} a {dados.fim}. A regra de cada atendimento é preservada no histórico; mudanças na configuração não alteram comissões antigas.</p>
            {Object.values(dados.avisos || {}).some((valor) => Number(valor) > 0) && <div role="status" className={styles.aviso}><p><strong>O cálculo tem registros incompletos:</strong></p>
                {Number(dados.avisos?.valores_historicos_ausentes) > 0 && <p>{dados.avisos.valores_historicos_ausentes} atendimento(s) sem valor histórico registrado.</p>}
                {Number(dados.avisos?.atendimentos_sem_profissional) > 0 && <p>{dados.avisos.atendimentos_sem_profissional} atendimento(s) sem profissional associado.</p>}
                {Number(dados.avisos?.atendimentos_sem_comissao) > 0 && <p>{dados.avisos.atendimentos_sem_comissao} atendimento(s) sem comissão registrada.</p>}
                <p>Regularize esses registros antes de fechar o valor a pagar. Os totais abaixo incluem somente comissões registradas.</p>
            </div>}
            <section className={styles.totais} aria-label="Totais do período"><article><span>Atendimentos com comissão</span><strong>{dados.totais?.quantidade_atendimentos ?? 0}</strong></article><article><span>Base dos atendimentos com comissão</span><strong>{dinheiro(dados.totais?.valor_base)}</strong></article><article><span>Total calculado para pagar manualmente</span><strong>{dinheiro(dados.totais?.valor_comissao)}</strong></article></section>
            <section className={styles.equipe} aria-label="Comissões por profissional">{(dados.funcionarios || []).map((item) => <article className={styles.profissional} key={item.id_funcionario}>
                <h2>{item.nome}{item.ativo === false && <small> · Inativo</small>}</h2><p>Regra atual: {item.comissao_tipo === 'fixa' ? `${dinheiro(item.comissao_valor)} por atendimento` : `${item.comissao_valor ?? item.comissao_percentual ?? 0}%`} · {item.quantidade_atendimentos ?? 0} atendimento(s) com comissão · Base: {dinheiro(item.valor_base)}</p><p className={styles.valor}>Comissão calculada: <strong>{dinheiro(item.valor_comissao)}</strong></p>
                <details><summary>Ver base, regra e comissão de cada atendimento</summary><div className={styles.detalhes}>{(item.atendimentos || []).map((atendimento) => <article key={atendimento.id_agendamento}><h3>{atendimento.cliente_nome || 'Cliente'} · #{atendimento.id_agendamento}</h3><p>Atendimento: {momento(atendimento.inicio_em)}</p><p>Base: {dinheiro(atendimento.valor_base)} · Regra: {atendimento.tipo === 'fixa' ? `fixa de ${dinheiro(atendimento.valor_configurado)}` : `${atendimento.percentual}%`} · Comissão: <strong>{dinheiro(atendimento.valor_comissao)}</strong></p><p>Registrado em {momento(atendimento.registrado_em)}</p></article>)}{!item.atendimentos?.length && <p>Sem atendimentos com comissão neste período.</p>}</div></details>
            </article>)}</section>{!dados.funcionarios?.length && <p>Nenhum profissional com comissão neste período.</p>}
        </>}
    </main>;
}

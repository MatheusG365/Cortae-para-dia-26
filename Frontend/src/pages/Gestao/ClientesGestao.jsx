import { useCallback, useEffect, useState } from 'react';
import { FileDown } from 'lucide-react';
import { mensagemDaApi } from '../../services/api';
import { dinheiro, estadoFinanceiroHistorico, momento, servicosDoAtendimento } from '../../services/gestaoState';
import fichaStyles from './ClientesGestao.module.css';

export default function ClientesGestao({ requisicao, styles }) {
    const [clientes, setClientes] = useState([]);
    const [filtro, setFiltro] = useState({ busca: '', inativos_dias: '' });
    const [detalhe, setDetalhe] = useState(null);
    const [erro, setErro] = useState('');
    const [sucesso, setSucesso] = useState('');
    const [carregando, setCarregando] = useState(false);
    const [gerandoPdf, setGerandoPdf] = useState(false);
    const [erroPdf, setErroPdf] = useState('');
    const [statusPdf, setStatusPdf] = useState('');

    const carregar = useCallback(async (query = {}) => {
        setCarregando(true);
        setErro('');
        try {
            const dados = await requisicao('/clientes', {}, query);
            setClientes(dados.clientes || []);
        } catch (e) {
            setErro(mensagemDaApi(e));
        } finally {
            setCarregando(false);
        }
    }, [requisicao]);

    useEffect(() => { queueMicrotask(() => carregar()); }, [carregar]);

    async function abrirFicha(cliente) {
        setErro('');
        setSucesso('');
        setErroPdf('');
        setStatusPdf('');
        try {
            setDetalhe(await requisicao(`/clientes/${cliente.id_usuario}`));
        } catch (e) {
            setErro(mensagemDaApi(e));
        }
    }

    async function salvarFicha(evento) {
        evento.preventDefault();
        setErro('');
        setSucesso('');
        try {
            await requisicao(`/clientes/${detalhe.cliente.id_usuario}`, {
                method: 'PUT',
                body: JSON.stringify({ observacoes: detalhe.observacoes || '', preferencias: detalhe.preferencias || '' }),
            });
            setSucesso('Ficha do cliente salva.');
        } catch (e) {
            setErro(mensagemDaApi(e));
        }
    }

    async function baixarPdf() {
        if (gerandoPdf || !detalhe) return;
        setGerandoPdf(true);
        setErroPdf('');
        setStatusPdf('Gerando PDF da ficha…');
        try {
            const { baixarFichaClientePdf } = await import('../../services/fichaClientePdf.js');
            await baixarFichaClientePdf(detalhe);
            setStatusPdf('PDF gerado. O download foi iniciado.');
        } catch {
            setStatusPdf('');
            setErroPdf('Não foi possível gerar o PDF da ficha. Tente novamente.');
        } finally {
            setGerandoPdf(false);
        }
    }

    return <>
        <h2>Clientes e histórico</h2>
        <form className={styles.filtros} onSubmit={(e) => {
            e.preventDefault();
            carregar(Object.fromEntries(Object.entries(filtro).filter(([, v]) => v)));
        }}>
            <label>Nome, e-mail ou telefone<input value={filtro.busca} onChange={(e) => setFiltro({ ...filtro, busca: e.target.value })} /></label>
            <label>Sem visita há pelo menos (dias)<input type="number" min="1" max="3650" value={filtro.inativos_dias} onChange={(e) => setFiltro({ ...filtro, inativos_dias: e.target.value })} /></label>
            <button type="submit" disabled={carregando}>Buscar clientes</button>
        </form>
        {erro && <p role="alert" className={styles.erro}>{erro}</p>}
        {sucesso && <p role="status" className={styles.sucesso}>{sucesso}</p>}
        {carregando && <p role="status">Carregando clientes…</p>}
        <div className={styles.tabela}>
            <table>
                <thead><tr><th>Cliente</th><th>Contato</th><th>Realizados / faltas</th><th>Última visita</th><th>Ficha</th></tr></thead>
                <tbody>{clientes.map((c) => <tr key={c.id_usuario}>
                    <td>{c.nome}</td><td>{c.email}<br />{c.telefone}</td><td>{c.atendimentos_realizados} / {c.faltas}</td>
                    <td>{c.ultima_visita ? momento(c.ultima_visita) : 'Ainda não realizou atendimento'}</td>
                    <td><button type="button" onClick={() => abrirFicha(c)}>Abrir ficha</button></td>
                </tr>)}</tbody>
            </table>
        </div>
        {!clientes.length && !carregando && <p>Nenhum cliente encontrado.</p>}
        {detalhe && <section className={styles.cartao} aria-labelledby="titulo-ficha-cliente">
            <div className={fichaStyles.cabecalhoFicha}>
                <div className={fichaStyles.identificacao}>
                    <h3 id="titulo-ficha-cliente">Ficha de {detalhe.cliente?.nome}</h3>
                    <p>{detalhe.cliente?.email} · {detalhe.cliente?.telefone}</p>
                </div>
                <div className={fichaStyles.acoesFicha}>
                    <button type="button" className={fichaStyles.baixarPdf} onClick={baixarPdf} disabled={gerandoPdf} aria-busy={gerandoPdf} aria-describedby="nota-pdf-cliente">
                        <FileDown size={18} aria-hidden="true" />{gerandoPdf ? 'Gerando PDF…' : 'Baixar PDF'}
                    </button>
                    <small id="nota-pdf-cliente" className={fichaStyles.notaPdf}>O PDF usa os dados exibidos. Salve alterações para manter no sistema.</small>
                </div>
            </div>
            {statusPdf && <p role="status" className={fichaStyles.statusPdf}>{statusPdf}</p>}
            {erroPdf && <p role="alert" className={styles.erro}>{erroPdf}</p>}
            <form className={styles.formulario} onSubmit={salvarFicha}>
                <label>Observações<textarea maxLength={5000} value={detalhe.observacoes || ''} onChange={(e) => setDetalhe({ ...detalhe, observacoes: e.target.value })} /></label>
                <label>Preferências<textarea maxLength={5000} value={detalhe.preferencias || ''} onChange={(e) => setDetalhe({ ...detalhe, preferencias: e.target.value })} /></label>
                <button type="submit">Salvar ficha</button>
            </form>
            <h4>Atendimentos e faltas</h4>
            <div className={styles.tabela}><table>
                <thead><tr><th>Data</th><th>Profissional / serviços</th><th>Status</th><th>Valor</th></tr></thead>
                <tbody>{(detalhe.agendamentos || []).map((a) => <tr key={a.id_agendamento}>
                    <td>{momento(a.inicio_em)}</td><td>{a.funcionario_nome}<br />{servicosDoAtendimento(a)}</td><td>{a.status}</td><td>{dinheiro(a.valor_total)}</td>
                </tr>)}</tbody>
            </table></div>
            <h4>Histórico financeiro</h4>
            <div className={styles.tabela}><table>
                <thead><tr><th>Data</th><th>Agendamento</th><th>Forma / descrição</th><th>Valor</th><th>Status</th></tr></thead>
                <tbody>{(detalhe.pagamentos || []).map((p, i) => <tr key={p.id_recebimento || p.id_financeiro || i}>
                    <td>{momento(p.data_pagamento || p.data_hora)}</td><td>#{p.id_agendamento}</td><td>{p.forma || p.descricao}</td><td>{dinheiro(p.valor)}</td><td>{estadoFinanceiroHistorico(p)}</td>
                </tr>)}</tbody>
            </table></div>
            <button type="button" onClick={() => setDetalhe(null)}>Fechar ficha</button>
        </section>}
    </>;
}

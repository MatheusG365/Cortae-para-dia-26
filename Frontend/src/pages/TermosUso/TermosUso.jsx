import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch, mensagemDaApi } from '../../services/api';
import { useAuth } from '../../contexts/useAuth';
import useTermosUso from '../../services/useTermosUso';
import TermosAceite from '../../components/TermosAceite/TermosAceite';
import styles from './TermosUso.module.css';

function AceiteDaConta() {
    const termos = useTermosUso();
    const [ocupado, setOcupado] = useState(false);
    const [mensagem, setMensagem] = useState('');
    async function aceitar() {
        setOcupado(true); setMensagem('');
        try { await termos.aceitar(); setMensagem('Aceite registrado para sua conta.'); }
        catch (e) { setMensagem(mensagemDaApi(e)); }
        finally { setOcupado(false); }
    }
    return <section className={styles.aceite} aria-label="Aceite dos termos para sua conta"><h2>Termos da sua conta</h2><TermosAceite termos={termos} disabled={ocupado} />{!termos.rascunho && !termos.aceito && <button type="button" disabled={ocupado || !termos.permitido} onClick={aceitar}>{ocupado ? 'Registrando aceite…' : 'Aceitar termos para minha conta'}</button>}{mensagem && <p role="status">{mensagem}</p>}</section>;
}

export default function TermosUso() {
    const { logado } = useAuth();
    const [dados, setDados] = useState(null);
    const [erro, setErro] = useState('');
    useEffect(() => {
        const controller = new AbortController();
        apiFetch('/termos-uso', { signal: controller.signal }).then(setDados).catch(e => { if (!controller.signal.aborted) setErro(mensagemDaApi(e)); });
        return () => controller.abort();
    }, []);
    return <main className={styles.pagina}><Link className={styles.voltar} to="/">← Voltar ao início</Link><header className={styles.cabecalho}><span>TRANSPARÊNCIA · CORTAÊ</span><h1>Termos de Uso</h1><p>Conheça as regras para agendar, comprar e oferecer produtos e serviços na plataforma.</p>{dados && <div className={styles.versao}>{dados.estado_publicacao === 'rascunho' ? "Rascunho" : "Versão"} {dados.versao} · {dados.estado_publicacao === 'rascunho' ? "Atualização" : "Publicação"}: {dados.publicado_em}</div>}</header>{erro ? <p role="alert" className={styles.aviso}>{erro}</p> : !dados ? <p role="status">Carregando termos…</p> : <div className={styles.conteudo}><nav className={styles.indice} aria-label="Seções dos Termos de Uso"><h2>Nesta página</h2>{(dados.secoes || []).map((s, i) => <a key={i} href={`#termo-${i}`}>{String(i + 1).padStart(2, '0')} · {s.titulo.replace(/^\d+[.)]\s*/, '')}</a>)}</nav><div className={styles.texto}>{dados.identificacao_pendente && <div className={styles.aviso} role="note"><strong>Identificação da plataforma pendente</strong><p>Para publicar estes termos, o responsável deve informar nome ou razão social e canal de atendimento. Documento e endereço serão exibidos quando forem informados.</p></div>}{dados.responsavel?.nome && <section className={styles.secao}><h2>Responsável pela plataforma</h2><p>{dados.responsavel.nome}{dados.responsavel.documento && ` · ${dados.responsavel.documento}`}</p>{dados.responsavel.endereco && <p>Endereço: {dados.responsavel.endereco}</p>}{dados.responsavel.contato && <p>Atendimento: {dados.responsavel.contato}</p>}</section>}{logado && dados.aceite_habilitado === true && dados.estado_publicacao !== 'rascunho' && <AceiteDaConta />}{(dados.secoes || []).map((s, i) => <section id={`termo-${i}`} key={i} className={styles.secao}><span className={styles.numero}>{String(i + 1).padStart(2, '0')}</span><h2>{s.titulo.replace(/^\d+[.)]\s*/, '')}</h2>{s.paragrafos.map((p, index) => <p key={index}>{p}</p>)}</section>)}</div></div>}</main>;
}

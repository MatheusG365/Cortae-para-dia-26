import { Link } from 'react-router-dom';
import styles from './TermosAceite.module.css';

export default function TermosAceite({ termos, disabled = false }) {
    if (termos.carregando) return <p className={styles.aviso} role="status">Consultando Termos de Uso…</p>;
    if (termos.erro) return <p className={styles.aviso} role="alert">Não foi possível consultar os termos: {termos.erro}</p>;
    if (termos.rascunho) return <p className={styles.aviso}>Termos de Uso em preparação · <Link to="/termos-de-uso" target="_blank" rel="noopener noreferrer">Consultar rascunho</Link>. O aceite será solicitado após a publicação.</p>;
    if (termos.aceito) return <p className={styles.aviso}>Termos de Uso aceitos · <Link to="/termos-de-uso" target="_blank" rel="noopener noreferrer">Consultar termos</Link></p>;
    return <div className={styles.caixa}><label className={styles.linha}><input type="checkbox" checked={termos.marcado} onChange={e => termos.marcar(e.target.checked)} disabled={disabled} required /><span>Li e aceito os <Link to="/termos-de-uso" target="_blank" rel="noopener noreferrer">Termos de Uso</Link>, versão {termos.dados?.versao}.</span></label><small>O aceite será registrado para sua conta. Consulte as regras e a taxa da plataforma antes de continuar.</small></div>;
}

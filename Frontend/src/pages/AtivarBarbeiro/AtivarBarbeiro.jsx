import PasswordInput from '../../components/PasswordInput/PasswordInput';
import { useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import styles from './AtivarBarbeiro.module.css';
import { erroSenhaBarbeiro } from '../../services/agendaState';

export default function AtivarBarbeiro() {
    const [params] = useSearchParams();
    const token = params.get('token') || '';
    const [senha, setSenha] = useState('');
    const [confirmarSenha, setConfirmarSenha] = useState('');
    const [processando, setProcessando] = useState(false);
    const [ativado, setAtivado] = useState(false);
    const [mensagem, setMensagem] = useState(null);
    const botao = useRef(null);
    const ativar = async (evento) => {
        evento.preventDefault();
        if (processando) return;
        const erroSenha = erroSenhaBarbeiro(senha, confirmarSenha);
        if (erroSenha) { setMensagem({ tipo: 'erro', informacao: erroSenha }); return; }
        setProcessando(true);
        try {
            await apiFetch('/barbeiros/ativar', { method: 'POST', body: JSON.stringify({ token, senha, confirmarSenha }) });
            setSenha(''); setConfirmarSenha(''); setAtivado(true);
            // O token não deve permanecer no histórico depois de ser utilizado.
            window.history.replaceState(window.history.state, '', window.location.pathname);
        } catch (falha) { setMensagem({ tipo: 'erro', informacao: mensagemDaApi(falha) }); }
        finally { setProcessando(false); }
    };
    return <main className={styles.pagina}><section className={styles.card}>
        <h1>{ativado ? 'Acesso ativado' : 'Ative seu acesso de barbeiro'}</h1>
        <MensagemCard mensagem={mensagem} fechar={() => setMensagem(null)} focoAoFechar={botao} />
        {ativado ? <><p>Sua senha foi definida. Entre com o e-mail informado no convite para acessar seu painel.</p><Link to="/login">Ir para o login</Link></> : !token ? <p role="alert">O convite está incompleto. Solicite um novo link à barbearia.</p> : <>
            <p>Defina sua própria senha. Convites vencidos ou já usados precisam ser renovados pela barbearia.</p>
            <form onSubmit={ativar}><div className={styles.grupoEntrada}><label htmlFor="nova-senha-barbeiro">Nova senha</label><PasswordInput id="nova-senha-barbeiro" autoComplete="new-password" required minLength={8} maxLength={128} value={senha} disabled={processando} onChange={(evento) => setSenha(evento.target.value)} /></div>
                <div className={styles.grupoEntrada}><label htmlFor="confirmar-senha-barbeiro">Confirmar senha</label><PasswordInput id="confirmar-senha-barbeiro" autoComplete="new-password" required minLength={8} maxLength={128} value={confirmarSenha} disabled={processando} onChange={(evento) => setConfirmarSenha(evento.target.value)} /></div>
                <small>Use pelo menos 8 caracteres, com maiúscula, minúscula, número e caractere especial. Limite de 72 bytes; caracteres acentuados podem ocupar mais de um byte.</small><button ref={botao} type="submit" disabled={processando}>{processando ? 'Ativando…' : 'Definir senha e ativar acesso'}</button></form>
        </>}
    </section></main>;
}


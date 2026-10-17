import { Link } from 'react-router-dom';
import styles from './footer.module.css';
import { useAuth } from '../../contexts/useAuth';
import { urlImagemDoSite } from '../../services/imagensDoSite.js';

export default function Footer() {
    const { usuario, logado } = useAuth();
    const barbeiro = Number(usuario?.tipo) === 3;
    return (
        <footer className={styles.footer}>
            <div className={styles.container}>
                <div className={styles.logoArea}>
                    <img src={urlImagemDoSite('logobranca.png')} alt="CORTAÊ" />
                    <p>Leve sua barbearia para o <br /><strong>Próximo estágio.</strong></p>
                </div>
                <nav className={styles.links} aria-label="Acesso rápido">
                    <h3>Acesso rápido</h3>
                    <Link to="/">Início</Link>
                    <Link to="/barbearias-disponiveis">Encontrar estabelecimento</Link>
                    <Link to={barbeiro ? '/painel-barbeiro' : '/meus-agendamentos'}>{barbeiro ? 'Meu painel' : 'Meus agendamentos'}</Link>
                </nav>
                <nav className={styles.links} aria-label="Conta">
                    <h3>Sua conta</h3>
                    <Link to="/termos-de-uso">Termos de Uso</Link>
                    {logado ? <Link to="/editarusuario">Meu perfil</Link> : <><Link to="/login">Entrar</Link><Link to="/cadastro">Cadastrar</Link></>}
                </nav>
            </div>
            <div className={styles.copy}>© 2026 CORTAÊ. Todos os direitos reservados.</div>
        </footer>
    );
}

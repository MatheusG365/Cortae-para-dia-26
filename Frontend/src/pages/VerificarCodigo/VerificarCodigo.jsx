import { useState } from 'react';
import { IMaskInput } from 'react-imask';
import { useLocation, useNavigate } from 'react-router-dom';
import styles from './VerificarCodigo.module.css';
import { apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';

export default function VerificarCodigo() {
    // O e-mail é definido antes da primeira renderização; não é necessário
    // disparar outro ciclo de renderização apenas para ler o armazenamento local.
    const [email] = useState(() => localStorage.getItem('email_verificacao') || '');
    const [codigo, setCodigo] = useState('');
    const [erro, setErro] = useState('');
    const [sucesso, setSucesso] = useState('');
    const [carregando, setCarregando] = useState(false);
    const navigate = useNavigate();
    const location = useLocation();

    const verificar = async (e) => {
        e.preventDefault();
        setErro('');
        setSucesso('');

        if (codigo.length !== 6) {
            setErro('Digite o código de 6 dígitos.');
            return;
        }

        setCarregando(true);

        try {
            const dados = await apiFetch('/verificar-codigo', {
                method: 'POST',
                body: JSON.stringify({ email, codigo }),
            });

            setSucesso(
                dados?.mensagem?.informacao ||
                'E-mail confirmado com sucesso!'
            );

            localStorage.removeItem('email_verificacao');

            setTimeout(() => navigate('/login', { state: { de: location.state?.de } }), 1000);
        } catch (error) {
            setErro(mensagemDaApi(error));
        } finally {
            setCarregando(false);
        }
    };

    return (
        <main className={styles.container}>
            <section className={styles.card}>
                <h1>CONFIRME SEU E-MAIL</h1>

                <p>
                    Digite o código de 6 dígitos enviado para:
                    <br />
                    <strong>{email || 'seu e-mail'}</strong>
                </p>

                {erro && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />}
                {sucesso && <MensagemCard mensagem={{ informacao: sucesso, tipo: 'sucesso' }} fechar={() => setSucesso('')} />}

                <form onSubmit={verificar}>
                    <IMaskInput
                        mask="000000"
                        type="text"
                        inputMode="numeric"
                        id="input-codigo"
                        value={codigo}
                        onAccept={(value) => setCodigo(value)}
                        className={styles.codigo}
                        placeholder="000000"
                        required
                    />

                    <button
                        id="btn-confirmar-email"
                        type="submit"
                        disabled={carregando}
                    >
                        {carregando ? 'VERIFICANDO...' : 'CONFIRMAR E-MAIL'}
                    </button>
                </form>
            </section>
        </main>
    );
}

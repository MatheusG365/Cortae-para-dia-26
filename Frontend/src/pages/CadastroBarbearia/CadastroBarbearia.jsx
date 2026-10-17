import { emailSemEspacos } from '../../services/cadastroState';
import Select from '../../components/Select/Select';
import PasswordInput from '../../components/PasswordInput/PasswordInput';
import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { IMaskInput } from 'react-imask';
import { apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import styles from './CadastroBarbearia.module.css';
import { useAuth } from '../../contexts/useAuth';
import useTermosUso from '../../services/useTermosUso';
import TermosAceite from '../../components/TermosAceite/TermosAceite';

export default function CadastroADM() {
    const { usuario } = useAuth();
    const termos = useTermosUso({ cadastro: true });
    const [nome, setNome] = useState('');
    const [telefone, setTelefone] = useState('');
    const [email, setEmail] = useState('');
    const [senha, setSenha] = useState('');
    const [confirmarSenha, setConfirmarSenha] = useState('');
    const [tipoUsuario, setTipoUsuario] = useState('adm');
    const [genero, setGenero] = useState('');
    const [carregando, setCarregando] = useState(false);
    const [mensagem, setMensagem] = useState(null);

    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const cadastroPorAdmin = searchParams.get('origem') === 'admin';
    const criandoPorTerceiro = Number(usuario?.tipo) === 0;

    const obterTipoNumeric = (tipo) => {
        switch (tipo) {
            case 'adm': return 0;
            case 'barbearia': return 2;
            case 'cliente': default: return 1;
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setMensagem(null);
        if (!criandoPorTerceiro && !termos.permitido) { setMensagem({ informacao: 'Leia e aceite os Termos de Uso para se cadastrar.', tipo: 'erro' }); return; }

        if (senha !== confirmarSenha) {
            setMensagem({ informacao: 'As senhas não coincidem.', tipo: 'erro' });
            return;
        }

        setCarregando(true);

        try {
            const dados = await apiFetch('/cadastro', {
                method: 'POST',
                body: JSON.stringify({
                    nome,
                    telefone,
                    email: emailSemEspacos(email),
                    senha,
                    confirmarSenha,
                    tipo: obterTipoNumeric(tipoUsuario),
                    genero: tipoUsuario === 'cliente' ? genero : undefined,
                    ...(!criandoPorTerceiro && !termos.rascunho ? { termos_aceitos: true, termos_versao: termos.dados.versao } : {}),
                }),
            });

            setMensagem(dados?.mensagem || { informacao: 'Cadastro realizado com sucesso!', tipo: 'sucesso' });

            setTimeout(() => {
                // Cadastro iniciado pelo painel não deve tirar o ADM da gestão.
                if (cadastroPorAdmin) {
                    navigate('/admin/usuarios', { replace: true });
                    return;
                }
                localStorage.setItem('email_verificacao', emailSemEspacos(email));
                navigate('/verificar-codigo');
            }, 1000);
        } catch (error) {
            setMensagem({ informacao: mensagemDaApi(error), tipo: 'erro' });
        } finally {
            setCarregando(false);
        }
    };

    return (
        <div className={styles.paginaCompleta}>
            <MensagemCard mensagem={mensagem} fechar={() => setMensagem(null)} />

            {/* CONTEÚDO PRINCIPAL (SPLIT 50/50) */}
            <main className={styles.containerConteudo}>
                <section className={styles.areaFormulario}>
                    <div className={styles.cartaoCadastro}>
                        <h1 className={styles.titulo}>CADASTRO</h1>

                        <form onSubmit={handleSubmit} className={styles.formulario}>
                            <div className={styles.grupoEntrada}>
                                <label htmlFor="input-nome" className={styles.rotulo}>Nome</label>
                                <IMaskInput
                                    mask={/^[A-Za-zÀ-ÿ ]*$/}
                                    type="text"
                                    id="input-nome"
                                    value={nome}
                                    onAccept={(val) => setNome(val)}
                                    className={styles.entrada}
                                    required
                                />
                            </div>

                            <div className={styles.grupoEntrada}>
                                <label htmlFor="input-telefone" className={styles.rotulo}>Telefone</label>
                                <IMaskInput
                                    mask="(00) 0000[0]-0000"
                                    type="tel"
                                    id="input-telefone"
                                    value={telefone}
                                    onAccept={(val) => setTelefone(val)}
                                    className={styles.entrada}
                                    required
                                />
                            </div>

                            <div className={styles.grupoEntrada}>
                                <label htmlFor="input-email" className={styles.rotulo}>E-mail</label>
                                <IMaskInput
                                    mask={/^[\w.+-@]*$/}
                                    type="email"
                                    id="input-email"
                                    value={email}
                                    onAccept={(val) => setEmail(val)}
                                    className={styles.entrada}
                                    required
                                />
                            </div>

                            {tipoUsuario === 'cliente' && (
                                <div className={styles.grupoEntrada}>
                                    <label htmlFor="input-genero" className={styles.rotulo}>Gênero</label>
                                    <Select
                                        id="input-genero"
                                        value={genero}
                                        onChange={(e) => setGenero(e.target.value)}
                                        className={styles.entrada}
                                    >
                                        <option value="">Selecione</option>
                                        <option value="masculino">Masculino</option>
                                        <option value="feminino">Feminino</option>
                                        <option value="outro">Outro</option>
                                    </Select>
                                </div>
                            )}

                            <div className={styles.grupoEntrada}>
                                <label htmlFor="input-senha" className={styles.rotulo}>Senha</label>
                                <PasswordInput
                                    mask={/^[\s\S]*$/}
                                    
                                    id="input-senha"
                                    value={senha}
                                    onAccept={(val) => setSenha(val)}
                                    className={styles.entrada}
                                    required
                                />
                            </div>

                            <div className={styles.grupoEntrada}>
                                <label htmlFor="input-confirmar-senha" className={styles.rotulo}>Confirmar Senha</label>
                                <PasswordInput
                                    mask={/^[\s\S]*$/}
                                    
                                    id="input-confirmar-senha"
                                    value={confirmarSenha}
                                    onAccept={(val) => setConfirmarSenha(val)}
                                    className={styles.entrada}
                                    required
                                />
                            </div>

                            {/* RADIOS */}
                            <div className={styles.grupoTipoUsuario}>
                                <label className={styles.opcaoRadio}>
                                    <input
                                        type="radio"
                                        id="radio-adm"
                                        name="tipoUsuario"
                                        value="adm"
                                        checked={tipoUsuario === 'adm'}
                                        onChange={(e) => setTipoUsuario(e.target.value)}
                                    />
                                    <span>ADM</span>
                                </label>

                                <label className={styles.opcaoRadio}>
                                    <input
                                        type="radio"
                                        id="radio-cliente"
                                        name="tipoUsuario"
                                        value="cliente"
                                        checked={tipoUsuario === 'cliente'}
                                        onChange={(e) => setTipoUsuario(e.target.value)}
                                    />
                                    <span>Cliente</span>
                                </label>

                                <label className={styles.opcaoRadio}>
                                    <input
                                        type="radio"
                                        id="radio-barbearia"
                                        name="tipoUsuario"
                                        value="barbearia"
                                        checked={tipoUsuario === 'barbearia'}
                                        onChange={(e) => setTipoUsuario(e.target.value)}
                                    />
                                    <span>Barbearia</span>
                                </label>
                            </div>

                            {/* BOTOES */}
                            {criandoPorTerceiro ? <p>O titular desta conta deverá aceitar os Termos de Uso ao utilizar a plataforma.</p> : <TermosAceite termos={termos} disabled={carregando} />}
                            <button
                                type="submit"
                                id="btn-cadastre-se"
                                className={styles.btnCadastreSe}
                                disabled={carregando || (!criandoPorTerceiro && !termos.permitido)}
                            >
                                {carregando ? 'CARREGANDO...' : 'CADASTRE-SE'}
                            </button>
                        </form>

                        <span className={styles.textoOu}>OU</span>

                        <button
                            type="button"
                            id="btn-voltar"
                            className={styles.btnVoltar}
                            onClick={() => navigate(-1)}
                        >
                            VOLTAR
                        </button>
                    </div>
                </section>

                {/* LADO DIREITO COM A FOTO DA BARBEARIA */}
                <section className={styles.areaImagem}></section>
            </main>

            {/* FOOTER */}
            <footer className={styles.footer}>
                <div className={styles.colunaBranding}>
                    <div className={styles.logoFooter}>CORTAÊ</div>
                    <p className={styles.sloganFooter}>
                        Leve sua barbearia para o<br />Próximo <span>estágio.</span>
                    </p>
                </div>

                <div className={styles.colunaLinks}>
                    <h4>Acesso rápido</h4>
                    <ul>
                        <li>Início</li>
                        <li>Encontrar estabelecimento</li>
                        <li>Meus agendamentos</li>
                    </ul>
                </div>

                <div className={styles.colunaLinks}>
                    <h4>Mais</h4>
                    <ul>
                        <li>Sobre nós</li>
                        <li>Trabalhe conosco</li>
                    </ul>
                </div>

                <div className={styles.redesSociais}>
                    <span className={styles.iconeRede}>FB</span>
                    <span className={styles.iconeRede}>IG</span>
                    <span className={styles.iconeRede}>YT</span>
                    <span className={styles.iconeRede}>TW</span>
                </div>
            </footer>
        </div>
    );
}


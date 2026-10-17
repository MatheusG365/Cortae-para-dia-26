import { emailSemEspacos, somenteDigitos } from '../../services/cadastroState';
import Select from '../../components/Select/Select';
import PasswordInput from '../../components/PasswordInput/PasswordInput';
import styles from './cadastro.module.css';

import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { IMaskInput } from 'react-imask';

import {
    apiFetch,
    mensagemDaApi
} from '../../services/api';

import MensagemCard from '../../components/MensagemCard/MensagemCard';
import TermosAceite from '../../components/TermosAceite/TermosAceite';
import useTermosUso from '../../services/useTermosUso';


export default function Cadastro() {
    const termos = useTermosUso({ cadastro: true });

    // ==================================================
    // ESTADOS
    // ==================================================

    const [nome, setNome] = useState('');
    const [telefone, setTelefone] = useState('');
    const [email, setEmail] = useState('');
    const [senha, setSenha] = useState('');
    const [confirmarSenha, setConfirmarSenha] = useState('');
    const [genero, setGenero] = useState('');

    const [carregando, setCarregando] = useState(false);

    // ==================================================
    // MENSAGEM DO CARD
    // ==================================================

    const [mensagem, setMensagem] = useState(null);

    const navigate = useNavigate();
    const location = useLocation();
    const retorno = location.state?.de;


    // ==================================================
    // CADASTRO
    // ==================================================

    const handleSubmit = async (e) => {

        e.preventDefault();

        // Remove mensagem anterior
        setMensagem(null);
        if (!termos.permitido) { setMensagem({ informacao: 'Leia e aceite os Termos de Uso para se cadastrar.', tipo: 'erro' }); return; }
        if (![10, 11].includes(somenteDigitos(telefone).length)) {
            setMensagem({ informacao: 'Informe um telefone válido com DDD.', tipo: 'erro' });
            return;
        }


        // ==================================================
        // VALIDAR SENHAS
        // ==================================================

        if (senha !== confirmarSenha) {

            setMensagem({
                informacao: 'As senhas não coincidem.',
                tipo: 'erro'
            });

            return;
        }


        setCarregando(true);


        try {

            // ==================================================
            // ENVIAR CADASTRO
            // ==================================================

            const dados = await apiFetch(
                '/cadastro',
                {
                    method: 'POST',

                    body: JSON.stringify({

                        nome,

                        telefone,

                        email: emailSemEspacos(email),

                        senha,

                        confirmarSenha,

                        // Tipo 1 = usuário/cliente
                        tipo: 1,
                        ...(!termos.rascunho ? { termos_aceitos: true, termos_versao: termos.dados.versao } : {}),

                        genero: genero || undefined
                    })
                }
            );


            // ==================================================
            // SALVAR EMAIL PARA VERIFICAÇÃO
            // ==================================================

            const emailLimpo =
                emailSemEspacos(email);


            localStorage.setItem(
                'email_verificacao',
                emailLimpo
            );


            // ==================================================
            // MOSTRAR MENSAGEM DE SUCESSO
            // ==================================================

            setMensagem(
                dados?.mensagem || {
                    informacao:
                        'Cadastro realizado com sucesso!',
                    tipo: 'sucesso'
                }
            );


            // ==================================================
            // IR PARA VERIFICAÇÃO
            // ==================================================

            setTimeout(() => {

                navigate('/verificar-codigo', { state: { de: retorno } });

            }, 1000);


        } catch (error) {



            // ==================================================
            // MOSTRAR ERRO
            // ==================================================

            setMensagem({

                informacao:
                    mensagemDaApi(error),

                tipo: 'erro'
            });

        } finally {

            setCarregando(false);

        }
    };


    // ==================================================
    // JSX
    // ==================================================

    return (

        <main className={styles.container}>

            {/* ==================================================
                CARD DE MENSAGEM
            ================================================== */}

            <MensagemCard
                mensagem={mensagem}
                fechar={() => setMensagem(null)}
            />


            {/* ==================================================
                FORMULÁRIO
            ================================================== */}

            <section className={styles.areaFormulario}>

                <div className={styles.cartaoCadastro}>

                    <h1 className={styles.titulo}>
                        FAÇA SEU CADASTRO
                    </h1>


                    <form
                        onSubmit={handleSubmit}
                        className={styles.formulario}
                    >

                        {/* ==================================================
                            NOME
                        ================================================== */}

                        <div className={styles.grupoEntrada}>

                            <label
                                htmlFor="nome"
                                className={styles.rotulo}
                            >
                                Nome
                            </label>

                            <IMaskInput
                                mask={/^[A-Za-zÀ-ÿ ]*$/}
                                type="text"
                                id="nome"
                                value={nome}
                                onAccept={(value) =>
                                    setNome(value)
                                }
                                className={styles.entrada}
                                required
                            />

                        </div>


                        {/* ==================================================
                            TELEFONE
                        ================================================== */}

                        <div className={styles.grupoEntrada}>

                            <label
                                htmlFor="telefone"
                                className={styles.rotulo}
                            >
                                Telefone
                            </label>

                            <IMaskInput
                                mask="(00) 0000[0]-0000"
                                type="tel"
                                id="telefone"
                                value={telefone}
                                onAccept={(value) =>
                                    setTelefone(value)
                                }
                                className={styles.entrada}
                                required
                            />

                        </div>


                        {/* ==================================================
                            EMAIL
                        ================================================== */}

                        <div className={styles.grupoEntrada}>

                            <label
                                htmlFor="email"
                                className={styles.rotulo}
                            >
                                E-mail
                            </label>

                            <IMaskInput
                                mask={/^[\w.+-@]*$/}
                                type="email"
                                id="email"
                                value={email}
                                onAccept={(value) =>
                                    setEmail(value)
                                }
                                className={styles.entrada}
                                required
                            />

                        </div>


                        {/* ==================================================
                            SENHA
                        ================================================== */}

                        <div className={styles.grupoEntrada}>

                            <label
                                htmlFor="senha"
                                className={styles.rotulo}
                            >
                                Senha
                            </label>

                            <PasswordInput
                                mask={/^[\s\S]*$/}
                                
                                id="senha"
                                value={senha}
                                onAccept={(value) =>
                                    setSenha(value)
                                }
                                className={styles.entrada}
                                required
                            />

                        </div>


                        {/* ==================================================
                            CONFIRMAR SENHA
                        ================================================== */}

                        <div className={styles.grupoEntrada}>

                            <label
                                htmlFor="confirmarSenha"
                                className={styles.rotulo}
                            >
                                Confirmar Senha
                            </label>

                            <PasswordInput
                                mask={/^[\s\S]*$/}
                                
                                id="confirmarSenha"
                                value={confirmarSenha}
                                onAccept={(value) =>
                                    setConfirmarSenha(value)
                                }
                                className={styles.entrada}
                                required
                            />

                        </div>


                        {/* ==================================================
                            GÊNERO
                        ================================================== */}

                        <div className={styles.grupoEntrada}>

                            <label
                                htmlFor="genero"
                                className={styles.rotulo}
                            >
                                Gênero
                            </label>

                            <Select
                                id="genero"
                                value={genero}
                                onChange={(e) => setGenero(e.target.value)}
                                className={styles.entrada}
                            >
                                <option value="">Selecione (opcional)</option>
                                <option value="masculino">Masculino</option>
                                <option value="feminino">Feminino</option>
                                <option value="outro">Outro</option>
                            </Select>

                        </div>

                        {/* ==================================================
                            BOTÃO
                        ================================================== */}

                        <TermosAceite termos={termos} disabled={carregando} />
                        <button
                            type="submit"
                            id = "cadastrar"
                            name = "cadastrar"
                            className={styles.botaoCadastrar}
                            disabled={carregando || !termos.permitido}
                        >

                            {carregando
                                ? 'CADASTRANDO...'
                                : 'CADASTRAR'
                            }

                        </button>

                    </form>


                    {/* ==================================================
                        LOGIN
                    ================================================== */}

                    <div className={styles.areaLogin}>

                        <p className={styles.textoLogin}>
                            Já possui Cadastro?
                        </p>

                        <button
                            type="button"
                            id ="login"
                            className={styles.botaoLogin}
                            onClick={() =>
                                navigate('/login', { state: { de: retorno } })
                            }
                        >
                            FAÇA O LOGIN
                        </button>

                    </div>

                </div>

            </section>


            {/* ==================================================
                IMAGEM
            ================================================== */}

            <section className={styles.areaImagem}>

                <div
                    className={styles.sobreposicaoImagem}
                />

            </section>

        </main>
    );
}

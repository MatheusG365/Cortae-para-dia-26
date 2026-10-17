import { emailSemEspacos, somenteDigitos } from '../../services/cadastroState';
import PasswordInput from '../../components/PasswordInput/PasswordInput';
import styles from './RedefinicaoSenha.module.css';

import { useRef, useState } from 'react';
import { IMaskInput } from 'react-imask';

import {
    apiFetch,
    mensagemDaApi
} from '../../services/api';

import MensagemCard from '../../components/MensagemCard/MensagemCard';


export default function RedefinicaoSenha() {

    // ==================================================
    // ESTADOS
    // ==================================================

    const [etapa, setEtapa] = useState(1);

    const [email, setEmail] = useState('');

    const [codigo, setCodigo] = useState(
        Array(6).fill('')
    );

    const [novaSenha, setNovaSenha] = useState('');

    const [confirmarSenha, setConfirmarSenha] =
        useState('');

    const [carregando, setCarregando] =
        useState(false);


    // ==================================================
    // MENSAGEM
    // ==================================================

    const [mensagem, setMensagem] = useState(null);


    // ==================================================
    // REFERÊNCIAS DOS INPUTS
    // ==================================================

    const inputs = useRef([]);


    // ==================================================
    // ALTERAR CÓDIGO
    // ==================================================

    const handleChangeCode = (e, index) => {
        const valor = somenteDigitos(e.target.value)
            .slice(-1);

        const novoCodigo = [...codigo];
        novoCodigo[index] = valor;

        setCodigo(novoCodigo);

        // Avança automaticamente para o próximo quadrado
        if (valor && index < 5) {
            inputs.current[index + 1]?.focus();
        }
    };


    // ==================================================
    // BACKSPACE
    // ==================================================

    const handleKeyDown = (e, index) => {

        if (e.key === 'Backspace') {

            // Se o quadrado atual estiver preenchido,
            // apaga ele primeiro
            if (codigo[index]) {
                const novoCodigo = [...codigo];
                novoCodigo[index] = '';
                setCodigo(novoCodigo);

                e.preventDefault();
                return;
            }

            // Se estiver vazio, volta para o anterior
            if (index > 0) {
                inputs.current[index - 1]?.focus();
            }
        }
    };


    // ==================================================
    // COLAR CÓDIGO
    // ==================================================

    const handlePaste = (e) => {

        const texto = somenteDigitos(e.clipboardData.getData('text'))
            .slice(0, 6);

        if (!texto) {
            return;
        }

        const novoCodigo =
            Array(6).fill('');

        texto
            .split('')
            .forEach((numero, index) => {

                novoCodigo[index] = numero;

            });

        setCodigo(novoCodigo);

        const proximo =
            Math.min(texto.length, 5);

        inputs.current[proximo]?.focus();

        e.preventDefault();
    };


    // ==================================================
    // ETAPA 1
    // ENVIAR CÓDIGO
    // ==================================================

    const enviarCodigo = async (e) => {

        e.preventDefault();

        setMensagem(null);

        setCarregando(true);

        try {

            const dados = await apiFetch(
                '/recuperar-senha',
                {
                    method: 'POST',

                    body: JSON.stringify({

                        etapa: 1,

                        email: emailSemEspacos(email)

                    })
                }
            );


            // ==========================================
            // SUCESSO
            // ==========================================

            setMensagem(
                dados?.mensagem || {
                    tipo: 'sucesso',
                    informacao:
                        'Código enviado para o seu e-mail.'
                }
            );


            setEtapa(2);

        } catch (error) {



            // ==========================================
            // ERRO
            // ==========================================

            setMensagem({

                tipo: 'erro',

                informacao:
                    mensagemDaApi(error)

            });

        } finally {

            setCarregando(false);

        }
    };


    // ==================================================
    // ETAPA 2
    // CONFIRMAR CÓDIGO
    // ==================================================

    const confirmarCodigo = async (e) => {

        e.preventDefault();

        const codigoCompleto =
            codigo.join('');


        // ==========================================
        // VALIDAR CÓDIGO
        // ==========================================

        if (
            codigoCompleto.length !== 6
        ) {

            setMensagem({

                tipo: 'erro',

                informacao:
                    'Digite os 6 dígitos do código.'

            });

            return;
        }


        setMensagem(null);

        setCarregando(true);


        try {

            const dados = await apiFetch(
                '/recuperar-senha',
                {
                    method: 'POST',

                    body: JSON.stringify({

                        etapa: 2,

                        email: emailSemEspacos(email),

                        codigo: codigoCompleto

                    })
                }
            );


            // ==========================================
            // SUCESSO
            // ==========================================

            setMensagem(
                dados?.mensagem || {

                    tipo: 'sucesso',

                    informacao:
                        'Código confirmado com sucesso.'

                }
            );


            setEtapa(3);

        } catch (error) {



            // ==========================================
            // ERRO
            // ==========================================

            setMensagem({

                tipo: 'erro',

                informacao:
                    mensagemDaApi(error)

            });

        } finally {

            setCarregando(false);

        }
    };


    // ==================================================
    // ETAPA 3
    // REDEFINIR SENHA
    // ==================================================

    const redefinirSenha = async (e) => {

        e.preventDefault();


        // ==========================================
        // VALIDAR SENHAS
        // ==========================================

        if (
            novaSenha !== confirmarSenha
        ) {

            setMensagem({

                tipo: 'erro',

                informacao:
                    'As senhas não coincidem.'

            });

            return;
        }


        setMensagem(null);

        setCarregando(true);


        try {

            const dados = await apiFetch(
                '/recuperar-senha',
                {
                    method: 'POST',

                    body: JSON.stringify({

                        etapa: 3,

                        email: emailSemEspacos(email),

                        codigo:
                            codigo.join(''),

                        senha: novaSenha,

                        confirmarSenha

                    })
                }
            );


            // ==========================================
            // SUCESSO
            // ==========================================

            setMensagem(
                dados?.mensagem || {

                    tipo: 'sucesso',

                    informacao:
                        'Senha alterada com sucesso!'

                }
            );


            // ==========================================
            // REDIRECIONAR PARA LOGIN
            // ==========================================

            setTimeout(() => {

                window.location.href = '/login';

            }, 1200);

        } catch (error) {



            // ==========================================
            // ERRO
            // ==========================================

            setMensagem({

                tipo: 'erro',

                informacao:
                    mensagemDaApi(error)

            });

        } finally {

            setCarregando(false);

        }
    };


    // ==================================================
    // VOLTAR
    // ==================================================

    const voltar = () => {

        setMensagem(null);

        if (etapa === 1) {

            window.history.back();

        } else {

            setEtapa(etapa - 1);

        }
    };


    // ==================================================
    // RENDER
    // ==================================================

    return (

        <main className={styles.container}>

            {/* ==================================================
                MENSAGEM CARD
            ================================================== */}

            <MensagemCard
                mensagem={mensagem}
                fechar={() => setMensagem(null)}
            />


            {/* ==================================================
                BOTÃO VOLTAR
            ================================================== */}

            <button
                id="btn-voltar"
                type="button"
                className={styles.botaoVoltar}
                onClick={voltar}
            >
                VOLTAR
            </button>


            {/* ==================================================
                ÁREA DE REDEFINIÇÃO
            ================================================== */}

            <section
                className={styles.areaRedefinicao}
            >

                <div className={styles.conteudo}>


                    {/* ==================================================
                        ETAPAS
                    ================================================== */}

                    <div className={styles.etapas}>

                        <div
                            className={`
                                ${styles.etapa}
                                ${
                                etapa >= 1
                                    ? styles.etapaAtiva
                                    : ''
                            }
                            `}
                        >

                            <span>
                                1
                            </span>

                            <p>
                                E-mail
                            </p>

                        </div>


                        <div
                            className={styles.linha}
                        />


                        <div
                            className={`
                                ${styles.etapa}
                                ${
                                etapa >= 2
                                    ? styles.etapaAtiva
                                    : ''
                            }
                            `}
                        >

                            <span>
                                2
                            </span>

                            <p>
                                Código
                            </p>

                        </div>


                        <div
                            className={styles.linha}
                        />


                        <div
                            className={`
                                ${styles.etapa}
                                ${
                                etapa >= 3
                                    ? styles.etapaAtiva
                                    : ''
                            }
                            `}
                        >

                            <span>
                                3
                            </span>

                            <p>
                                Senha
                            </p>

                        </div>

                    </div>


                    {/* ==================================================
                        ETAPA 1
                    ================================================== */}

                    {etapa === 1 && (

                        <>

                            <h1 className={styles.titulo}>
                                REDEFINIÇÃO DE SENHA
                            </h1>

                            <p className={styles.subtitulo}>
                                Informe seu e-mail para receber
                                o código de recuperação.
                            </p>


                            <form
                                onSubmit={enviarCodigo}
                                className={styles.formulario}
                            >

                                <div
                                    className={
                                        styles.grupoEntrada
                                    }
                                >

                                    <label
                                        htmlFor="email"
                                        className={
                                            styles.rotulo
                                        }
                                    >
                                        Email de recuperação
                                    </label>


                                    <IMaskInput
                                        mask={
                                            /^[\w.+-@]*$/
                                        }

                                        type="email"

                                        id="email"

                                        placeholder="example@gmail.com"

                                        value={email}

                                        onAccept={(value) =>
                                            setEmail(value)
                                        }

                                        className={
                                            styles.entrada
                                        }

                                        required
                                    />

                                </div>


                                <button
                                    id="btn-enviar-codigo"
                                    type="submit"
                                    className={
                                        styles.botaoEnviar
                                    }
                                    disabled={carregando}
                                >

                                    {carregando
                                        ? 'ENVIANDO...'
                                        : 'ENVIAR CÓDIGO'
                                    }

                                </button>

                            </form>

                        </>

                    )}


                    {/* ==================================================
                        ETAPA 2
                    ================================================== */}

                    {etapa === 2 && (

                        <>

                            <h1 className={styles.titulo}>
                                CONFIRMAR CÓDIGO
                            </h1>


                            <p className={styles.subtitulo}>

                                Digite o código de 6
                                dígitos enviado para:

                                <br />

                                <strong>
                                    {email}
                                </strong>

                            </p>


                            <form
                                onSubmit={confirmarCodigo}
                                className={styles.formulario}
                            >

                                <div className={styles.otpContainer}>

                                    {codigo.map((digito, index) => (
                                        <input
                                            key={index}

                                            ref={(elemento) => {
                                                inputs.current[index] = elemento;
                                            }}

                                            type="text"
                                            inputMode="numeric"
                                            maxLength={1}

                                            value={digito}

                                            onChange={(e) =>
                                                handleChangeCode(e, index)
                                            }

                                            onKeyDown={(e) =>
                                                handleKeyDown(e, index)
                                            }

                                            onPaste={handlePaste}

                                            className={styles.entradaCodigo}

                                            aria-label={`Dígito ${index + 1}`}
                                        />
                                    ))}

                                </div>


                                <button
                                    id="btn-confirmar-codigo"
                                    type="submit"
                                    className={
                                        styles.botaoEnviar
                                    }
                                    disabled={
                                        codigo.join('').length !== 6 ||
                                        carregando
                                    }
                                >

                                    {carregando
                                        ? 'CONFIRMANDO...'
                                        : 'CONFIRMAR CÓDIGO'
                                    }

                                </button>

                            </form>

                        </>

                    )}


                    {/* ==================================================
                        ETAPA 3
                    ================================================== */}

                    {etapa === 3 && (

                        <>

                            <h1 className={styles.titulo}>
                                NOVA SENHA
                            </h1>


                            <p className={styles.subtitulo}>
                                Digite sua nova senha abaixo.
                            </p>


                            <form
                                onSubmit={redefinirSenha}
                                className={styles.formulario}
                            >

                                <div
                                    className={
                                        styles.grupoEntrada
                                    }
                                >

                                    <label
                                        htmlFor="novaSenha"
                                        className={
                                            styles.rotulo
                                        }
                                    >
                                        Nova senha
                                    </label>


                                    <PasswordInput
                                        mask={
                                            /^[\s\S]*$/
                                        }

                                        

                                        id="novaSenha"

                                        placeholder="Mínimo 6 caracteres"

                                        value={novaSenha}

                                        onAccept={(value) =>
                                            setNovaSenha(value)
                                        }

                                        className={
                                            styles.entrada
                                        }

                                        minLength={6}

                                        required
                                    />

                                </div>


                                <div
                                    className={
                                        styles.grupoEntrada
                                    }
                                >

                                    <label
                                        htmlFor="confirmarSenha"
                                        className={
                                            styles.rotulo
                                        }
                                    >
                                        Confirmar nova senha
                                    </label>


                                    <PasswordInput
                                        mask={
                                            /^[\s\S]*$/
                                        }

                                        

                                        id="confirmarSenha"

                                        placeholder="Digite a senha novamente"

                                        value={confirmarSenha}

                                        onAccept={(value) =>
                                            setConfirmarSenha(value)
                                        }

                                        className={
                                            styles.entrada
                                        }

                                        minLength={6}

                                        required
                                    />

                                </div>


                                <button
                                    id="btn-redefinir-senha"
                                    type="submit"
                                    className={
                                        styles.botaoEnviar
                                    }
                                    disabled={carregando}
                                >

                                    {carregando
                                        ? 'SALVANDO...'
                                        : 'REDEFINIR SENHA'
                                    }

                                </button>

                            </form>

                        </>

                    )}

                </div>

            </section>

        </main>

    );
}

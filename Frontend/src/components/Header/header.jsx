import estilo from "./header.module.css";

import {
    Link,
    useNavigate
} from "react-router-dom";

import {
    useCallback,
    useEffect,
    useState
} from "react";

import {
    FiUser,
    FiMenu,
    FiX
} from "react-icons/fi";
import { urlDaApi, apiFetch, mensagemDaApi } from '../../services/api';
import { urlImagemDoSite } from '../../services/imagensDoSite.js';
import MensagemCard from '../MensagemCard/MensagemCard';

export default function Header() {

    const navigate = useNavigate();

    // ==========================================================
    // ESTADOS
    // ==========================================================

    const [logado, setLogado] = useState(false);
    const [fotoPerfil, setFotoPerfil] = useState(null);
    const [nomeUsuario, setNomeUsuario] = useState("");
    const [tipoUsuario, setTipoUsuario] = useState(null);
    const [menuAberto, setMenuAberto] = useState(false);
    const [saindo, setSaindo] = useState(false);
    const [erroSessao, setErroSessao] = useState('');


    // ==========================================================
    // URL DA FOTO
    // ==========================================================

    const obterUrlFoto = useCallback((
        foto,
        atualizarCache = false
    ) => {

        if (!foto) {
            return null;
        }


        if (foto.startsWith("blob:")) {
            return foto;
        }


        let url;


        if (
            foto.startsWith("http://") ||
            foto.startsWith("https://")
        ) {

            url = foto;

        } else if (
            foto.startsWith("/")
        ) {

            url = urlDaApi(foto);

        } else {

            url =
                urlDaApi(`/uploads/perfil/${foto}`);

        }


        // ==================================================
        // CACHE BUSTING
        // ==================================================
        // Mesmo se a imagem nova tiver o mesmo nome,
        // o navegador será obrigado a buscar novamente.

        if (atualizarCache) {

            url +=
                `${url.includes("?") ? "&" : "?"}t=${Date.now()}`;

        }


        return url;
    }, []);


    // ==========================================================
    // VERIFICAR LOGIN
    // ==========================================================

    const verificarLogin = useCallback(() => {

        try {

            const usuarioSalvo =
                localStorage.getItem("usuario");


            if (!usuarioSalvo) {

                setLogado(false);
                setFotoPerfil(null);
                setNomeUsuario("");
                setTipoUsuario(null);

                return;
            }


            const usuario =
                JSON.parse(usuarioSalvo);


            const id =
                usuario?.id_usuario ??
                usuario?.id;


            if (!id) {

                setLogado(false);
                setFotoPerfil(null);
                setNomeUsuario("");
                setTipoUsuario(null);

                return;
            }


            // ==================================================
            // USUÁRIO LOGADO
            // ==================================================

            setLogado(true);

            setNomeUsuario(
                usuario?.nome || ""
            );

            // TIPO 2 = barbeiro/barbearia.
            // Para esse usuário, o botão BARBEARIAS abre diretamente
            // a página da própria barbearia.
            setTipoUsuario(usuario?.tipo ?? null);


            // ==================================================
            // FOTO
            // ==================================================

            if (
                usuario?.foto_perfil
            ) {

                setFotoPerfil(
                    obterUrlFoto(
                        usuario.foto_perfil,
                        true
                    )
                );

            } else {

                setFotoPerfil(null);

                // No login a foto não vem no payload. Buscamos o perfil
                // autenticado para preencher o header sem depender de reload.
                apiFetch(`/dados-perfil/${id}`)
                    .then((dados) => {
                        // Uma resposta antiga não pode restaurar o usuário após sair ou trocar de conta.
                        const atual = JSON.parse(localStorage.getItem('usuario') || 'null');
                        if (String(atual?.id_usuario ?? atual?.id) !== String(id)) return;
                        const foto = dados?.usuario?.foto_perfil;
                        if (!foto) return;
                        const atualizado = { ...usuario, ...dados.usuario, foto_perfil: foto };
                        localStorage.setItem('usuario', JSON.stringify(atualizado));
                        setFotoPerfil(obterUrlFoto(foto, true));
                    })
                    .catch(() => setFotoPerfil(null));

            }


        } catch {


            setLogado(false);
            setFotoPerfil(null);
            setNomeUsuario("");

        }

    }, [obterUrlFoto]);


    // ==========================================================
    // INICIALIZAÇÃO
    // ==========================================================

    useEffect(() => {

        // Agenda a leitura da sessão após a montagem para evitar atualizar
        // estado durante a execução síncrona do efeito.
        queueMicrotask(verificarLogin);


        // ==================================================
        // ATUALIZAR HEADER
        // ==================================================

        const atualizarLogin = () => {

            verificarLogin();

        };


        // ==================================================
        // LOGIN / USUÁRIO ALTERADO
        // ==================================================

        window.addEventListener(
            "loginAlterado",
            atualizarLogin
        );


        // ==================================================
        // FOTO ALTERADA
        // ==================================================

        window.addEventListener(
            "fotoPerfilAlterada",
            atualizarLogin
        );


        // ==================================================
        // STORAGE
        // ==================================================

        window.addEventListener(
            "storage",
            atualizarLogin
        );


        // ==================================================
        // LIMPEZA
        // ==================================================

        return () => {

            window.removeEventListener(
                "loginAlterado",
                atualizarLogin
            );


            window.removeEventListener(
                "fotoPerfilAlterada",
                atualizarLogin
            );


            window.removeEventListener(
                "storage",
                atualizarLogin
            );

        };

    }, [verificarLogin]);


    // ==========================================================
    // MENU
    // ==========================================================

    const alternarMenu = () => {

        setMenuAberto(
            atual => !atual
        );

    };


    const fecharMenu = () => {

        setMenuAberto(false);

    };


    // ==========================================================
    // PERFIL
    // ==========================================================

    const abrirPerfil = () => {

        fecharMenu();

        navigate("/EditarUsuario");

    };


    // ==========================================================
    // SAIR
    // ==========================================================

    const sair = async () => {
        if (saindo) return;
        setSaindo(true);
        setErroSessao('');
        try {
            await apiFetch('/logout', { method: 'POST' });
        } catch (erro) {
            setErroSessao(mensagemDaApi(erro));
            setSaindo(false);
            return;
        }

        localStorage.removeItem("usuario");

        localStorage.removeItem("access_token");

        localStorage.removeItem("token");


        setLogado(false);

        setFotoPerfil(null);

        setNomeUsuario("");

        setMenuAberto(false);


        window.dispatchEvent(
            new Event("loginAlterado")
        );


        navigate("/login");
        setSaindo(false);

    };


    // ==========================================================
    // ERRO NA FOTO
    // ==========================================================

    const erroFoto = () => {


        setFotoPerfil(null);

    };


    // ==========================================================
    // RENDER
    // ==========================================================

    return (

        <header className={estilo.header}>
            {erroSessao && <MensagemCard mensagem={{ informacao: erroSessao, tipo: 'erro' }} fechar={() => setErroSessao('')} />}

            <div className={estilo.container}>

                {/* ==================================================
                    LOGO
                ================================================== */}

                <Link
                    to="/"
                    className={estilo.logo}
                    onClick={fecharMenu}
                >

                    <img
                        src={urlImagemDoSite('logopreta.png')}
                        alt="Cortaê"
                    />

                </Link>


                {/* ==================================================
                    BOTÃO HAMBÚRGUER
                ================================================== */}

                <button
                    type="button"
                    className={estilo.menuMobile}
                    onClick={alternarMenu}
                    aria-label={
                        menuAberto
                            ? "Fechar menu"
                            : "Abrir menu"
                    }
                    aria-expanded={menuAberto}
                >

                    {menuAberto ? (
                        <FiX />
                    ) : (
                        <FiMenu />
                    )}

                </button>


                {/* ==================================================
                    MENU
                ================================================== */}

                <nav
                    className={`${estilo.menu} ${
                        menuAberto
                            ? estilo.menuAberto
                            : ""
                    }`}
                >
                    <Link to="/marketplace" className={estilo.historico} onClick={fecharMenu}>LOJA</Link>

                    {/* ==================================================
                        DESLOGADO
                    ================================================== */}

                    {!logado && (

                        <>

                            <Link
                                to="/cadastro"
                                className={estilo.cadastro}
                                onClick={fecharMenu}
                            >
                                CADASTRAR
                            </Link>


                            <Link
                                to="/login"
                                className={estilo.login}
                                onClick={fecharMenu}
                            >
                                LOGIN
                            </Link>

                        </>

                    )}


                    {/* ==================================================
                        LOGADO
                    ================================================== */}

                    {logado && (

                        <>

                            {Number(tipoUsuario) === 0 && <>
                                <Link to="/admin/usuarios" className={estilo.historico} onClick={fecharMenu}>USUÁRIOS</Link>
                                <Link to="/admin/cortes" className={estilo.historico} onClick={fecharMenu}>CORTES</Link>
                                <Link to="/gestao" className={estilo.historico} onClick={fecharMenu}>GESTÃO</Link>
                                <Link to="/barbearias-disponiveis" className={estilo.historico} onClick={fecharMenu}>BARBEARIAS</Link>
                                <Link to="/financeiro" className={estilo.historico} onClick={fecharMenu}>FINANCEIRO</Link>
                                <Link to="/comissoes-barbearia" className={estilo.historico} onClick={fecharMenu}>COMISSÕES</Link>
                            </>}

                            {Number(tipoUsuario) === 1 && <>
                                <Link to="/marketplace/carrinho" className={estilo.historico} onClick={fecharMenu}>CARRINHO</Link>
                                <Link to="/marketplace/pedidos" className={estilo.historico} onClick={fecharMenu}>COMPRAS</Link>
                                <Link to="/barbearias-disponiveis" className={estilo.historico} onClick={fecharMenu}>BARBEARIAS</Link>
                                <Link to="/meus-agendamentos" className={estilo.historico} onClick={fecharMenu}>HISTÓRICO</Link>
                            </>}

                            {Number(tipoUsuario) === 3 && <><Link to="/painel-barbeiro" className={estilo.historico} onClick={fecharMenu}>MEU PAINEL</Link><Link to="/gestao" className={estilo.historico} onClick={fecharMenu}>AGENDA</Link></>}
                            {Number(tipoUsuario) === 2 && <>
                                <Link to="/gestao-marketplace" className={estilo.historico} onClick={fecharMenu}>MINHA LOJA</Link>
                                <Link to="/estabelecimento" className={estilo.historico} onClick={fecharMenu}>MINHA BARBEARIA</Link>
                                <Link to="/gestao" className={estilo.historico} onClick={fecharMenu}>GESTÃO</Link>
                                <Link to="/editarbarbearia" className={estilo.historico} onClick={fecharMenu}>EDITAR BARBEARIA</Link>
                                <Link to="/comissoes-barbearia" className={estilo.historico} onClick={fecharMenu}>COMISSÕES</Link>
                            </>}


                            <button
                                type="button"
                                id = "bnt-sair"
                                className={estilo.sair}
                                onClick={sair}
                                disabled={saindo}
                            >
                                {saindo ? 'SAINDO…' : 'SAIR'}
                            </button>


                            {/* ==================================================
                                FOTO DO USUÁRIO
                            ================================================== */}

                            <button
                                type="button"
                                className={estilo.usuario}
                                onClick={abrirPerfil}
                                aria-label="Editar usuário"
                            >

                                {fotoPerfil ? (

                                    <img
                                        src={fotoPerfil}
                                        alt={
                                            nomeUsuario ||
                                            "Foto de perfil"
                                        }
                                        className={estilo.fotoPerfil}
                                        onError={erroFoto}
                                    />

                                ) : (

                                    <FiUser />

                                )}

                            </button>

                        </>

                    )}

                </nav>

            </div>

        </header>

    );

}



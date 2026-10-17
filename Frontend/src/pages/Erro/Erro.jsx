import estilo from "./Erro.module.css";
import { Link, useNavigate } from "react-router-dom";
import { FaExclamationTriangle, FaHome, FaArrowLeft } from "react-icons/fa";

export default function Erro() {
    const navigate = useNavigate();

    return (
        <main className={estilo.container}>

            <div className={estilo.card}>

                {/* Ícone */}
                <div className={estilo.icone}>
                    <FaExclamationTriangle />
                </div>

                {/* Código do erro */}
                <span className={estilo.codigo}>
                    404
                </span>

                {/* Título */}
                <h1>
                    Página não encontrada
                </h1>

                {/* Descrição */}
                <p>
                    Ops! Parece que a página que você está procurando
                    não existe ou foi movida para outro endereço.
                </p>

                {/* Botões */}
                <div className={estilo.botoes}>

                    <button
                        id="btn-voltar"
                        className={estilo.voltar}
                        onClick={() => navigate(-1)}
                    >
                        <FaArrowLeft />
                        Voltar
                    </button>

                    <Link
                        id="btn-pagina-inicial"
                        to="/"
                        className={estilo.inicio}
                    >
                        <FaHome />
                        Página inicial
                    </Link>

                </div>

            </div>

        </main>
    );
}
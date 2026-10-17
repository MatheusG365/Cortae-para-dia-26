import { useNavigate } from "react-router-dom";
import css from "./Button.module.css";

export default function Botao({ acao, pagina, texto, id, disabled = false, className = '', ...atributos }) {
    const navigate = useNavigate();

    function handleClick(e) {
        e.preventDefault();

        if (acao) {
            acao(e);
        }

        if (pagina) {
            navigate(pagina);
        }
    }

    return (
        <button
            {...atributos}
            id={id}
            type="button"
            className={`${css.botao} ${className}`}
            disabled={disabled}
            onClick={handleClick}
        >
            {texto}
        </button>
    );
}

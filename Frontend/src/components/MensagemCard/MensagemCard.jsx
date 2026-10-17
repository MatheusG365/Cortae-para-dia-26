import { FiCheckCircle, FiAlertCircle, FiX } from 'react-icons/fi';
import styles from './MensagemCard.module.css';
import { useId } from 'react';
import useDialog from '../useDialog';

export default function MensagemCard({
                                         mensagem,
                                         fechar,
                                         focoAoFechar
                                     }) {
    const dialogo = useDialog(!!mensagem, fechar, false, focoAoFechar);
    const tituloId = useId();
    const mensagemId = useId();

    if (!mensagem) {
        return null;
    }

    const tipo =
        mensagem?.tipo === 'sucesso'
            ? 'sucesso'
            : 'erro';

    return (
        <div className={styles.overlay}>

            <div
                ref={dialogo}
                tabIndex={-1}
                role="alertdialog"
                aria-modal="true"
                aria-labelledby={tituloId}
                aria-describedby={mensagemId}
                className={`${styles.card} ${
                    tipo === 'sucesso'
                        ? styles.cardSucesso
                        : styles.cardErro
                }`}
            >

                <button
                    type="button"
                    className={styles.fechar}
                    onClick={fechar}
                    aria-label="Fechar mensagem"
                >
                    <FiX />
                </button>


                <div className={styles.icone}>

                    {tipo === 'sucesso' ? (
                        <FiCheckCircle />
                    ) : (
                        <FiAlertCircle />
                    )}

                </div>


                <h2 id={tituloId}>
                    {tipo === 'sucesso'
                        ? 'Sucesso!'
                        : 'Atenção!'
                    }
                </h2>


                <p id={mensagemId}>
                    {mensagem.informacao}
                </p>


                <button
                    type="button"
                    id='button-confirmar'
                    className={styles.botao}
                    onClick={fechar}
                >
                    OK
                </button>

            </div>

        </div>
    );
}

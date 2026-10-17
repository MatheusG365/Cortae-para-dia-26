import { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import MaskedInput from '../MaskedInput/MaskedInput';
import styles from './PasswordInput.module.css';

export default function PasswordInput({ id, className = '', disabled, ...props }) {
    const generatedId = useId();
    const inputId = id || generatedId;
    const [visible, setVisible] = useState(false);
    const action = visible ? 'Ocultar senha' : 'Mostrar senha';

    return <span className={styles.campo}>
        <MaskedInput {...props} id={inputId} disabled={disabled}
            type={visible ? 'text' : 'password'}
            className={`${className} ${styles.entrada}`} />
        <button type="button" className={styles.botao} disabled={disabled}
            onClick={() => setVisible((current) => !current)}
            aria-label={action} title={action} aria-controls={inputId} aria-pressed={visible}>
            {visible ? <EyeOff size={20} aria-hidden="true" /> : <Eye size={20} aria-hidden="true" />}
        </button>
    </span>;
}

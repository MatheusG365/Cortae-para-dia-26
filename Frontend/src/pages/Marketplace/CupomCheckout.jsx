import { useId } from 'react';
import { CircleCheck, TicketPercent } from 'lucide-react';
import { cupomNormalizado } from './comercialState';
import { estadoCupomCheckout } from './cupomCheckoutState';
import { moeda } from './marketplaceState';
import styles from './CupomCheckout.module.css';
import lojaStyles from './Marketplace.module.css';

export default function CupomCheckout({ entrada, cupom, atualizar, aplicar, remover, ocupado, previa, podeConferir }) {
    const id = useId();
    const estado = estadoCupomCheckout({ cupom, ...previa, podeConferir });
    const confirmado = estado.tipo === 'aplicado';
    function aplicarCodigo() {
        if (!ocupado && cupomNormalizado(entrada)) aplicar(cupomNormalizado(entrada));
    }
    return <section className={styles.cupom} aria-labelledby={`${id}-titulo`}>
        <header className={styles.cabecalho}>
            <span className={styles.icone}><TicketPercent size={23} aria-hidden="true" /></span>
            <div><h3 id={`${id}-titulo`}>Tem um cupom?</h3><p>Aplique seu código e economize nesta compra.</p></div>
        </header>
        <div className={styles.controles}>
            <label className={styles.campo} htmlFor={id}>Código do cupom
                <input id={id} placeholder="Ex.: BEMVINDO10" autoComplete="off" value={entrada} maxLength={40} disabled={ocupado}
                    onChange={e => atualizar(e.target.value)} aria-describedby={`${id}-estado`}
                    onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); aplicarCodigo(); } }} />
            </label>
            <button className={lojaStyles.primario} type="button" disabled={ocupado || !cupomNormalizado(entrada)} onClick={aplicarCodigo}>Aplicar cupom</button>
        </div>
        <div id={`${id}-estado`} className={styles.estado} role="status" aria-live="polite">
            {confirmado ? <div className={styles.confirmado}><CircleCheck size={20} aria-hidden="true" /><div><strong>Você economizou {moeda(estado.desconto)}</strong><span>Cupom <b className={styles.codigo}>{estado.codigo}</b> aplicado nos produtos.</span></div></div>
                : estado.tipo === 'dados' ? <p>Complete os dados e escolha a entrega para conferir o cupom.</p>
                    : estado.tipo === 'conferindo' ? <p>Conferindo cupom {estado.codigo}…</p>
                        : estado.tipo === 'erro' ? <p>Não foi possível aplicar {estado.codigo}. Confira o aviso abaixo.</p>
                            : estado.tipo === 'semDesconto' ? <p>O cupom {estado.codigo} não gerou desconto nesta compra.</p>
                                : <p>Use um cupom válido desta barbearia.</p>}
            {cupom && <button className={styles.remover} type="button" disabled={ocupado} onClick={remover}>Remover cupom</button>}
        </div>
    </section>;
}

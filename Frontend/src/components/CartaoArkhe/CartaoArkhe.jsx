import { useEffect, useRef, useState } from 'react';
import { dadosCartao, limiteParcelas } from '../../services/cartaoArkhe';
import { dinheiro } from '../../services/gestaoState';
import styles from './CartaoArkhe.module.css';

const vazio = () => ({ numero_cartao: '', validade: '', cvv: '', tipo: 'DEBITO', parcelas: 1 });
export function ReciboCartao({ recibo }) {
    if (!recibo) return null;
    return <section aria-label="Comprovante do cartão virtual Arkhé"><h3>Pagamento aprovado · Cartão virtual Arkhé</h3>
        <p>{dinheiro(recibo.valor)} · {recibo.tipo === 'CREDITO' ? 'Crédito' : 'Débito'} · {recibo.parcelas} parcela(s) · final {String(recibo.final_cartao || '').slice(-4)}</p>
        <p>Compra {recibo.id_compra} · Movimentação {recibo.id_movimentacao}</p>
        <p>Recebimento do estabelecimento: {dinheiro(recibo.valor_recebido)} · taxa do estabelecimento: {dinheiro(recibo.taxa)}.</p>
    </section>;
}
export default function CartaoArkhe({ total, onSubmit, disabled = false, onBusyChange }) {
    const [campos, setCampos] = useState(vazio);
    const [confirmando, setConfirmando] = useState(false);
    const [ocupado, setOcupado] = useState(false);
    const [erro, setErro] = useState('');
    const trava = useRef(false);
    const sensiveis = useRef(null);
    useEffect(() => () => { if (sensiveis.current) Object.assign(sensiveis.current, vazio()); }, []);
    function limpar() { if (sensiveis.current) Object.assign(sensiveis.current, vazio()); setCampos(vazio()); setConfirmando(false); }
    const alterar = (nome, valor) => { const novo = { ...campos, [nome]: valor, ...(nome === 'tipo' ? { parcelas: 1 } : {}) }; sensiveis.current = novo; setConfirmando(false); setCampos(novo); };
    function conferir(evento) {
        evento.preventDefault(); setErro('');
        try { dadosCartao(campos, total); setConfirmando(true); } catch (falha) { setErro(falha.message); }
    }
    async function enviar() {
        if (trava.current || disabled) return;
        trava.current = true; setOcupado(true); onBusyChange?.(true); setErro('');
        let corpo;
        try {
            corpo = dadosCartao(campos, total);
            limpar();
            await onSubmit(corpo);
        } catch (falha) { setErro(falha.message || 'Não foi possível concluir. Atualize o status antes de tentar novamente.'); }
        finally {
            if (corpo) { corpo.numero_cartao = ''; corpo.cvv = ''; corpo.validade = ''; }
            limpar(); trava.current = false; setOcupado(false); onBusyChange?.(false);
        }
    }
    return <form className={styles.formulario} onSubmit={conferir} autoComplete="off" aria-label="Cartão virtual Arkhé">
        <h3>Cartão virtual Arkhé</h3><p>Use o cartão da sua conta Arkhé. Total confirmado pelo servidor: <strong>{dinheiro(total)}</strong>.</p>
        <p>Crédito: até 15 parcelas; a taxa de 5% é descontada do estabelecimento. Débito: uma parcela, recebimento integral.</p>
        <fieldset disabled={disabled || ocupado} className={styles.campos}>
            <label>Número do cartão virtual Arkhé<input value={campos.numero_cartao} onChange={e => alterar('numero_cartao', e.target.value.replace(/\D/g, '').slice(0, 16))} inputMode="numeric" maxLength={16} autoComplete="off" /></label>
            <label>Validade (MM/YYYY)<input value={campos.validade} onChange={e => alterar('validade', e.target.value.slice(0, 7))} placeholder="MM/YYYY" maxLength={7} autoComplete="off" /></label>
            <label>CVV<input type="password" value={campos.cvv} onChange={e => alterar('cvv', e.target.value.replace(/\D/g, '').slice(0, 3))} inputMode="numeric" maxLength={3} autoComplete="off" /></label>
            <label>Modalidade<select value={campos.tipo} onChange={e => alterar('tipo', e.target.value)}><option value="DEBITO">Débito</option><option value="CREDITO">Crédito</option></select></label>
            <label>Parcelas<select value={campos.parcelas} onChange={e => alterar('parcelas', Number(e.target.value))} disabled={campos.tipo !== 'CREDITO'}>{Array.from({ length: 15 }, (_, i) => i + 1).map(n => <option key={n} value={n} disabled={n > limiteParcelas(total) || (campos.tipo === 'DEBITO' && n !== 1)}>{n} parcela(s)</option>)}</select></label>
        </fieldset>
        {erro && <p role="alert">{erro}</p>}
        {confirmando ? <div><p>Confirmar pagamento de <strong>{dinheiro(total)}</strong> no {campos.tipo === 'CREDITO' ? 'crédito' : 'débito'}, em {campos.parcelas} parcela(s)?</p><button type="button" disabled={ocupado || disabled} onClick={enviar}>Confirmar pagamento</button><button type="button" disabled={ocupado} onClick={() => setConfirmando(false)}>Voltar</button></div> : <button type="submit" disabled={ocupado || disabled || !limiteParcelas(total)}>{ocupado ? 'Enviando…' : 'Conferir pagamento com cartão'}</button>}
        <button type="button" disabled={ocupado} onClick={() => { limpar(); setErro(''); }}>Limpar dados do cartão</button>
    </form>;
}

import { useEffect, useEffectEvent, useRef } from 'react';
const dialogosAbertos = [];

// Os diálogos comuns compartilham foco inicial, navegação por teclado e retorno do foco.
export default function useDialog(aberto, aoFechar, processando = false, focoAoFechar) {
    const dialogo = useRef(null);
    const fechar = useEffectEvent(() => {
        if (!processando) aoFechar?.();
    });

    useEffect(() => {
        if (!aberto) return undefined;
        const elemento = dialogo.current;
        const focoAnterior = document.activeElement;
        const focoRetorno = focoAoFechar?.current;
        dialogosAbertos.push(elemento);
        const selecionaveis = () => Array.from(elemento?.querySelectorAll(
            'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'
        ) || []).filter(item => !item.hidden && item.tabIndex !== -1 && item.getClientRects().length > 0);
        (selecionaveis()[0] || elemento)?.focus();

        const aoTeclar = (evento) => {
            if (dialogosAbertos.at(-1) !== elemento) return;
            if (evento.key === 'Escape') {
                evento.preventDefault();
                fechar();
            }
            if (evento.key !== 'Tab') return;
            const itens = selecionaveis();
            const primeiro = itens[0];
            const ultimo = itens.at(-1);
            if (!itens.length) {
                evento.preventDefault();
                elemento?.focus();
            } else if (evento.shiftKey && (document.activeElement === primeiro || !elemento?.contains(document.activeElement))) {
                evento.preventDefault();
                ultimo.focus();
            } else if (!evento.shiftKey && (document.activeElement === ultimo || !elemento?.contains(document.activeElement))) {
                evento.preventDefault();
                primeiro.focus();
            }
        };
        document.addEventListener('keydown', aoTeclar);
        return () => {
            const indice = dialogosAbertos.lastIndexOf(elemento);
            if (indice >= 0) dialogosAbertos.splice(indice, 1);
            document.removeEventListener('keydown', aoTeclar);
            const destino = focoRetorno || focoAnterior;
            if (destino?.isConnected && !destino.disabled) destino.focus();
        };
    }, [aberto, focoAoFechar]);
    return dialogo;
}

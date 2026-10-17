import { Children, Fragment, isValidElement, useEffect, useEffectEvent, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { FiCheck, FiChevronDown } from 'react-icons/fi';
import { buscarOpcao, indiceSelecionado, moverOpcao, posicionarLista } from './selectState';
import styles from './Select.module.css';

function textoDosFilhos(filhos) {
    return Children.toArray(filhos).map(filho => isValidElement(filho) ? textoDosFilhos(filho.props.children) : String(filho)).join('').replace(/\s+/g, ' ').trim();
}

function coletarOpcoes(filhos, lista = []) {
    Children.forEach(filhos, filho => {
        if (!isValidElement(filho)) return;
        if (filho.type === Fragment) coletarOpcoes(filho.props.children, lista);
        else if (filho.type === 'option') {
            const label = filho.props.label || textoDosFilhos(filho.props.children);
            lista.push({ value: String(filho.props.value ?? label), label, disabled: Boolean(filho.props.disabled) });
        }
    });
    return lista;
}

// O select nativo mantém submissão e validação. Apenas o combobox é interativo.
export default function Select({ children, value, defaultValue, onChange, onInvalid, disabled = false, required = false, id, name, className = '', onKeyDown, onBlur, onFocus, ...props }) {
    const gerado = useId();
    const triggerId = id || `seletor-${gerado}`;
    const listaId = `${triggerId}-opcoes`;
    const raiz = useRef(null);
    const trigger = useRef(null);
    const nativo = useRef(null);
    const listaRef = useRef(null);
    const busca = useRef({ texto: '', instante: 0 });
    const opcoes = coletarOpcoes(children);
    const [interno, setInterno] = useState(() => String(defaultValue ?? opcoes.find(opcao => !opcao.disabled)?.value ?? ''));
    const atual = value !== undefined ? String(value ?? '') : interno;
    const selecionado = indiceSelecionado(opcoes, atual);
    const [menu, setMenu] = useState(null);
    const [ativo, setAtivo] = useState(-1);
    const [invalido, setInvalido] = useState(false);
    // Uma consulta pode desabilitar o campo enquanto sua lista está aberta.
    if (disabled && menu) setMenu(null);
    const aberto = Boolean(menu) && !disabled;
    const ativoValido = opcoes[ativo] && !opcoes[ativo].disabled ? ativo : moverOpcao(opcoes, selecionado, 'inicio');

    function abrir(indice = selecionado) {
        if (disabled || !opcoes.some(opcao => !opcao.disabled)) return;
        const host = trigger.current.closest('[role="dialog"],dialog') || document.body;
        const viewport = window.visualViewport;
        // O portal pode sair da loja. Copia apenas as cores já calculadas do campo.
        const computado = window.getComputedStyle(trigger.current);
        const tema = Object.fromEntries(['--select-fundo', '--select-texto', '--select-borda', '--select-destaque', '--select-ativo']
            .map(chave => [chave, computado.getPropertyValue(chave).trim()]).filter(([, valor]) => valor));
        setAtivo(opcoes[indice]?.disabled ? moverOpcao(opcoes, indice, 'proximo') : indice);
        setMenu({ host, tema, ...posicionarLista(trigger.current.getBoundingClientRect(), { width: viewport?.width || window.innerWidth, height: viewport?.height || window.innerHeight, left: viewport?.offsetLeft || 0, top: viewport?.offsetTop || 0 }, Math.min(320, opcoes.length * 46 + 14)) });
    }
    function escolher(indice) {
        if (!opcoes[indice] || opcoes[indice].disabled || disabled) return;
        const proximo = opcoes[indice].value;
        setMenu(null);
        trigger.current?.focus();
        if (proximo === atual) return;
        nativo.current.value = proximo;
        nativo.current.dispatchEvent(new Event('change', { bubbles: true }));
    }
    const redefinir = useEffectEvent(evento => {
        // O navegador restaura o formulário depois de disparar reset.
        queueMicrotask(() => {
            if (evento.defaultPrevented || !nativo.current) return;
            const proximo = value !== undefined ? String(value ?? '') : String(defaultValue ?? opcoes.find(opcao => !opcao.disabled)?.value ?? '');
            nativo.current.value = proximo;
            if (value === undefined) setInterno(proximo);
            setInvalido(false);
            setMenu(null);
        });
    });
    useEffect(() => {
        const formulario = nativo.current?.form;
        formulario?.addEventListener('reset', redefinir);
        return () => formulario?.removeEventListener('reset', redefinir);
    }, []);

    useLayoutEffect(() => {
        if (!aberto) return undefined;
        const popup = listaRef.current;
        if (typeof popup.showPopover === 'function') popup.showPopover();
        const reposicionar = () => {
            if (!trigger.current?.isConnected) return;
            const viewport = window.visualViewport;
            const dimensoes = { width: viewport?.width || window.innerWidth, height: viewport?.height || window.innerHeight, left: viewport?.offsetLeft || 0, top: viewport?.offsetTop || 0 };
            const rect = trigger.current.getBoundingClientRect();
            if (rect.bottom <= dimensoes.top || rect.top >= dimensoes.top + dimensoes.height || rect.right <= dimensoes.left || rect.left >= dimensoes.left + dimensoes.width) { setMenu(null); return; }
            // scrollHeight inclui o padding, mas não as bordas da caixa.
            const alturaCompleta = popup.scrollHeight + popup.offsetHeight - popup.clientHeight;
            const posicao = posicionarLista(rect, dimensoes, Math.min(320, alturaCompleta));
            Object.assign(popup.style, { left: `${posicao.left}px`, top: `${posicao.top}px`, width: `${posicao.width}px`, maxHeight: `${posicao.maxHeight}px` });
        };
        reposicionar();
        const fora = evento => { if (!raiz.current?.contains(evento.target) && !popup.contains(evento.target)) setMenu(null); };
        window.addEventListener('resize', reposicionar);
        window.addEventListener('scroll', reposicionar, true);
        window.visualViewport?.addEventListener('resize', reposicionar);
        window.visualViewport?.addEventListener('scroll', reposicionar);
        document.addEventListener('pointerdown', fora);
        const observador = new ResizeObserver(reposicionar);
        observador.observe(trigger.current);
        return () => {
            window.removeEventListener('resize', reposicionar);
            window.removeEventListener('scroll', reposicionar, true);
            window.visualViewport?.removeEventListener('resize', reposicionar);
            window.visualViewport?.removeEventListener('scroll', reposicionar);
            document.removeEventListener('pointerdown', fora);
            observador.disconnect();
            if (typeof popup.hidePopover === 'function' && popup.matches(':popover-open')) popup.hidePopover();
        };
    }, [aberto]);
    useEffect(() => {
        if (aberto) listaRef.current?.querySelector(`[data-indice="${ativoValido}"]`)?.scrollIntoView({ block: 'nearest' });
    }, [aberto, ativoValido]);

    function teclado(evento) {
        onKeyDown?.(evento);
        if (evento.defaultPrevented || disabled) return;
        const tecla = evento.key;
        if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(tecla)) {
            evento.preventDefault();
            const direcao = { ArrowDown: 'proximo', ArrowUp: 'anterior', Home: 'inicio', End: 'fim' }[tecla];
            const indice = moverOpcao(opcoes, aberto ? ativoValido : selecionado, direcao);
            if (aberto) setAtivo(indice); else abrir(indice);
        } else if (tecla === 'Enter' || tecla === ' ') {
            evento.preventDefault();
            if (aberto) escolher(ativoValido); else abrir();
        } else if (tecla === 'Escape' && aberto) {
            evento.preventDefault(); evento.stopPropagation(); setMenu(null);
        } else if (tecla === 'Tab') setMenu(null);
        else if (tecla.length === 1 && !evento.ctrlKey && !evento.metaKey && !evento.altKey) {
            const instante = Date.now();
            busca.current.texto = instante - busca.current.instante < 700 ? busca.current.texto + tecla : tecla;
            busca.current.instante = instante;
            let indice = buscarOpcao(opcoes, busca.current.texto, aberto ? ativoValido : selecionado);
            if (indice < 0 && [...busca.current.texto].every(letra => letra === tecla)) indice = buscarOpcao(opcoes, tecla, aberto ? ativoValido : selecionado);
            if (indice >= 0) { evento.preventDefault(); if (aberto) setAtivo(indice); else abrir(indice); }
        }
    }

    return <span ref={raiz} className={styles.raiz} data-select-root="">
        <button {...props} ref={trigger} id={triggerId} type="button" role="combobox" data-select-trigger="" className={`${styles.trigger} ${className}`} disabled={disabled} aria-expanded={aberto} aria-controls={aberto ? listaId : undefined} aria-haspopup="listbox" aria-required={required || undefined} aria-invalid={props['aria-invalid'] || invalido || undefined} aria-activedescendant={aberto && ativoValido >= 0 ? `${listaId}-${ativoValido}` : undefined} onKeyDown={teclado} onFocus={onFocus} onBlur={evento => { if (!listaRef.current?.contains(evento.relatedTarget)) setMenu(null); onBlur?.(evento); }} onClick={evento => { evento.preventDefault(); if (aberto) setMenu(null); else abrir(); }}>
            <span className={styles.valor}>{opcoes[selecionado]?.label || 'Selecione'}</span><FiChevronDown className={styles.seta} aria-hidden="true" />
        </button>
        <select ref={nativo} hidden aria-hidden="true" tabIndex={-1} name={name} form={props.form} required={required} disabled={disabled} value={atual} onChange={evento => { setInvalido(false); if (value === undefined) setInterno(evento.target.value); onChange?.(evento); }} onInvalid={evento => { evento.preventDefault(); setInvalido(true); trigger.current?.focus(); onInvalid?.(evento); }}>
            {children}
        </select>
        {aberto && createPortal(<div ref={listaRef} popover="manual" id={listaId} role="listbox" aria-label={props['aria-label'] || 'Opções disponíveis'} className={styles.lista} style={{ ...menu.tema, left: menu.left, top: menu.top, width: menu.width, maxHeight: menu.maxHeight }} onPointerDown={evento => evento.preventDefault()} onClick={evento => evento.stopPropagation()}>
            {opcoes.map((opcao, indice) => <div id={`${listaId}-${indice}`} key={`${opcao.value}-${indice}`} role="option" aria-selected={indice === selecionado} aria-disabled={opcao.disabled || undefined} data-indice={indice} data-ativo={indice === ativoValido || undefined} className={styles.opcao} onPointerMove={() => { if (!opcao.disabled) setAtivo(indice); }} onClick={evento => { evento.preventDefault(); evento.stopPropagation(); escolher(indice); }}><span>{opcao.label}</span>{indice === selecionado && <FiCheck aria-hidden="true" />}</div>)}
        </div>, menu.host)}
    </span>;
}

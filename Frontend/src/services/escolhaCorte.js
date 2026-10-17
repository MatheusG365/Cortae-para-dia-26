export function permiteEscolhaNoAtendimento({ modoPulado, temPintar, apenasCor }) {
    return Boolean(modoPulado && !temPintar && !apenasCor);
}

export function rotuloEscolhaCorte(escolha, generosServicos = []) {
    if (escolha === 'na_hora') return 'Escolho na hora';
    if (escolha !== 'profissional') return 'Corte do catálogo';
    const generos = [...new Set(generosServicos)];
    if (generos.length === 1 && generos[0] === 'feminino') return 'A cabeleireira escolhe';
    if (generos.length === 1 && generos[0] === 'masculino') return 'O barbeiro escolhe';
    return 'O profissional escolhe';
}

const idValido = (valor) => Number.isInteger(Number(valor)) && Number(valor) > 0 ? Number(valor) : null;

// Booking and waiting-list requests share the same exclusive selection contract.
// A deferred choice never carries a catalog ID or a simulation from a prior choice.
export function dadosEscolhaCorte({ escolhaCorte = 'catalogo', idCorte, idVisagismo }) {
    const especial = escolhaCorte === 'na_hora' || escolhaCorte === 'profissional';
    const corte = idValido(idCorte);
    return {
        // Color-only simulations have no cut selection; preserve that contract.
        escolha_corte: escolhaCorte === 'catalogo' && !corte ? null : escolhaCorte,
        id_corte: especial ? null : corte,
        id_visagismo: especial ? null : idValido(idVisagismo)
    };
}

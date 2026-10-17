import { useEffect, useState } from 'react';
import { temaDaLoja } from './lojaState';
import { carregarPerfilPublico } from './perfilPublico';

// O tema pertence ao elemento da loja. Nenhuma variável global é alterada.
export default function useTemaLoja(idLoja) {
    const id = idLoja == null ? null : String(idLoja);
    const [estado, setEstado] = useState(null);
    useEffect(() => {
        if (!id) return;
        const controle = new AbortController();
        carregarPerfilPublico(id, { signal: controle.signal })
            .then(dados => { if (!controle.signal.aborted) setEstado({ id, tema: temaDaLoja(dados.personalizacao) }); })
            .catch(() => { if (!controle.signal.aborted) setEstado({ id, tema: temaDaLoja() }); });
        return () => controle.abort();
    }, [id]);
    return id ? estado?.id === id ? estado.tema : temaDaLoja() : undefined;
}

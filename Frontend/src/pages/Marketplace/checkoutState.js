import { estadosBrasil, somenteDigitos } from '../../services/cadastroState.js';

const nomes = { nome: 'nome', email: 'e-mail', telefone: 'telefone', documento: 'CPF ou CNPJ', cep: 'CEP', logradouro: 'rua', numero: 'número', bairro: 'bairro', cidade: 'cidade', uf: 'UF' };
export function pendenciasEndereco(endereco = {}) {
    return Object.entries(nomes).filter(([campo]) => {
        const valor = String(endereco[campo] || '').trim();
        if (!valor) return true;
        if (campo === 'cep') return somenteDigitos(valor).length !== 8;
        if (campo === 'documento') return ![11, 14].includes(somenteDigitos(valor).length);
        if (campo === 'telefone') return ![10, 11].includes(somenteDigitos(valor).length);
        if (campo === 'email') return !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor);
        if (campo === 'uf') return !estadosBrasil.includes(valor.toUpperCase());
        return false;
    }).map(([, nome]) => nome);
}

export function orientacaoCheckout({ endereco, retirada, selecionada, calculando, temCotacoes, previa, termos }) {
    const campos = pendenciasEndereco(endereco);
    if (campos.length) return `Confira os dados de entrega: ${campos.join(', ')}.`;
    if (!retirada && !selecionada) return calculando ? 'Buscando opções de entrega…' : temCotacoes ? 'Escolha uma opção de entrega para conferir o total.' : 'Calcule o frete e escolha uma opção de entrega para continuar.';
    if (previa.erro) return 'Não foi possível conferir o total. Tente atualizar os valores abaixo.';
    if (previa.carregando || !previa.resumo) return 'Conferindo produtos, frete e taxa da plataforma…';
    if (termos.erro) return 'Consulte os Termos de Uso novamente antes de continuar.';
    if (termos.carregando) return 'Consultando os Termos de Uso…';
    if (!termos.permitido) return 'Leia e aceite os Termos de Uso para criar o pedido.';
    return '';
}

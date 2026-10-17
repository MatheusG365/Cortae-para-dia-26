import { permiteEscolhaNoAtendimento } from '../../services/escolhaCorte.js';

const texto = (valor) => typeof valor === 'string' ? valor.trim() : '';

export function normalizarAnalise(dados) {
    const recomendacoes = dados?.recomendacoes;
    if (!Array.isArray(recomendacoes) || recomendacoes.length !== 1) {
        throw new Error('A análise deve retornar um único corte cadastrado. Tente analisar a foto novamente.');
    }
    const corte = recomendacoes[0];
    if (!Number.isInteger(Number(corte?.id_corte)) || Number(corte.id_corte) <= 0 || !texto(corte.nome) || !texto(corte.motivo)) {
        throw new Error('A análise não retornou um corte cadastrado com motivo. Tente novamente.');
    }
    if (corte.compativel_com_cabelo_existente !== true) {
        throw new Error('O corte retornado não é compatível com o cabelo observado. Tente analisar novamente.');
    }
    validarFotoSalva(dados);
    return {
        corte,
        caracteristicas: dados.caracteristicas && typeof dados.caracteristicas === 'object' ? dados.caracteristicas : {},
        cabeloAtual: texto(dados.cabelo_atual),
        observacoes: texto(dados.observacoes)
    };
}

export function validarFotoSalva(dados) {
    if (!Number.isInteger(Number(dados?.id_visagismo)) || Number(dados.id_visagismo) <= 0 || !texto(dados.foto_url)) {
        throw new Error('O servidor não confirmou a foto salva. Envie a foto novamente.');
    }
}

export function normalizarCatalogo(dados) {
    if (!Array.isArray(dados?.cortes) || dados.cortes.some((corte) => !Number.isInteger(Number(corte?.id_corte)) || Number(corte.id_corte) <= 0 || !texto(corte.nome))) {
        throw new Error('O servidor não retornou um catálogo válido. Tente novamente.');
    }
    return {
        cortes: dados.cortes,
        generosServicos: Array.isArray(dados.generos_servico) ? dados.generos_servico.filter((genero) => ['feminino', 'masculino', 'unissex'].includes(genero)) : []
    };
}

export function assinaturaSimulacao({ idBarbearia, idsServicos, idVisagismo, idCorte, cor, alvo, categoriaCor }) {
    return JSON.stringify([idBarbearia, idsServicos, idVisagismo, idCorte, cor, alvo, categoriaCor].map((valor) => valor == null ? '' : String(valor)));
}

export function erroDaSelecao({ apenasCor, temPintar, corteSelecionado, corSelecionada, idVisagismo, modoPulado, escolhaCorte = 'catalogo' }) {
    if (!['catalogo', 'na_hora', 'profissional'].includes(escolhaCorte)) return 'Escolha uma opção de corte válida.';
    const especial = escolhaCorte !== 'catalogo';
    if (especial && !permiteEscolhaNoAtendimento({ modoPulado, temPintar, apenasCor })) return 'Para análise ou pintura, selecione o corte e conclua a simulação.';
    if (!apenasCor && !especial && !corteSelecionado?.id_corte) return 'Selecione um corte cadastrado antes de continuar.';
    if (temPintar && !corSelecionada) return 'Selecione uma cor para gerar a simulação.';
    if (!permiteEscolhaNoAtendimento({ modoPulado, temPintar, apenasCor }) && !idVisagismo) return 'Envie e analise a foto antes de gerar a simulação.';
    return '';
}

export const CAMPOS_CARACTERISTICAS = [
    ['formato_rosto', 'Formato do rosto'],
    ['textura_cabelo', 'Textura do cabelo'],
    ['comprimento_cabelo', 'Comprimento do cabelo'],
    ['densidade_cabelo', 'Densidade do cabelo'],
    ['linha_frontal', 'Linha frontal'],
    ['barba', 'Barba']
];

export function textoCaracteristica(valor) {
    return texto(valor) || 'Não informado na análise';
}

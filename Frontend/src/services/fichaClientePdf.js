import { jsPDF } from 'jspdf';
import { autoTable } from 'jspdf-autotable';
import { dinheiro, estadoFinanceiroHistorico, momento, servicosDoAtendimento } from './gestaoState.js';

const MARGEM = 16;
const INICIO = 36;
const LIMITE = 277;
const COR_TEXTO = [32, 43, 53];
const COR_MARCA = [25, 69, 59];

const texto = (valor, vazio = 'Não informado') => {
    const conteudo = Array.from(String(valor ?? '')).filter((caractere) => {
        const codigo = caractere.charCodeAt(0);
        return (codigo >= 32 && codigo !== 127) || '\n\r\t'.includes(caractere);
    }).join('').trim();
    return conteudo || vazio;
};

export function nomeArquivoFichaCliente(nome, dataGeracao = new Date()) {
    const slug = String(nome ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 70).replace(/-+$/g, '') || 'cliente';
    const dia = `${dataGeracao.getFullYear()}-${String(dataGeracao.getMonth() + 1).padStart(2, '0')}-${String(dataGeracao.getDate()).padStart(2, '0')}`;
    return `ficha-cliente-${slug}-${dia}.pdf`;
}

// Apenas os dados já carregados na ficha são usados; nenhuma requisição ou alteração no cadastro.
export function prepararFichaClientePdf(detalhe) {
    if (!detalhe?.cliente) throw new Error('Abra uma ficha de cliente antes de gerar o PDF.');
    const cliente = detalhe.cliente;
    return {
        nome: texto(cliente.nome, 'Cliente'),
        contato: `E-mail: ${texto(cliente.email)}\nTelefone: ${texto(cliente.telefone)}`,
        resumo: [
            ['Agendamentos', texto(cliente.total_agendamentos, '0')],
            ['Realizados', texto(cliente.atendimentos_realizados, '0')],
            ['Faltas', texto(cliente.faltas, '0')],
            ['Última visita', cliente.ultima_visita ? momento(cliente.ultima_visita) : 'Ainda não realizou atendimento'],
        ],
        observacoes: texto(detalhe.observacoes, 'Nenhuma observação registrada.'),
        preferencias: texto(detalhe.preferencias, 'Nenhuma preferência registrada.'),
        atendimentos: (detalhe.agendamentos || []).map((a) => [
            momento(a.inicio_em),
            `${texto(a.funcionario_nome)}\n${texto(servicosDoAtendimento(a))}`,
            texto(a.status),
            dinheiro(a.valor_total),
        ]),
        pagamentos: (detalhe.pagamentos || []).map((p) => [
            momento(p.data_pagamento || p.data_hora),
            p.id_agendamento == null ? 'Não informado' : `#${p.id_agendamento}`,
            texto([p.forma, p.descricao].filter(Boolean).join(' · ')),
            dinheiro(p.valor),
            estadoFinanceiroHistorico(p),
        ]),
    };
}

export function gerarFichaClientePdf(detalhe, { dataGeracao = new Date() } = {}) {
    const dados = prepararFichaClientePdf(detalhe);
    if (!(dataGeracao instanceof Date) || Number.isNaN(dataGeracao.getTime())) throw new Error('Data de emissão inválida.');
    const documento = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
    documento.setProperties({ title: `Ficha de ${dados.nome}`, subject: 'Ficha de cliente e histórico', author: 'CORTAÊ' });
    documento.setCreationDate(dataGeracao);
    let y = INICIO;
    const largura = documento.internal.pageSize.getWidth() - MARGEM * 2;

    function novaPagina() {
        documento.addPage();
        y = INICIO;
    }

    function reservar(altura) {
        if (y + altura > LIMITE) novaPagina();
    }

    function titulo(conteudo) {
        reservar(17);
        documento.setFont('helvetica', 'bold');
        documento.setFontSize(11);
        documento.setTextColor(...COR_MARCA);
        documento.text(conteudo, MARGEM, y);
        y += 7;
    }

    // Distribui cada linha entre páginas, inclusive observações extensas com quebras manuais.
    function paragrafo(conteudo, { tamanho = 10, negrito = false } = {}) {
        documento.setFont('helvetica', negrito ? 'bold' : 'normal');
        documento.setFontSize(tamanho);
        documento.setTextColor(...COR_TEXTO);
        const alturaLinha = tamanho * 0.48;
        const linhas = documento.splitTextToSize(conteudo, largura);
        for (const linha of linhas) {
            reservar(alturaLinha);
            documento.text(linha, MARGEM, y);
            y += alturaLinha;
        }
        y += 4;
    }

    function tabela(cabecalho, corpo, colunas) {
        autoTable(documento, {
            startY: y,
            margin: { top: INICIO, bottom: 23, left: MARGEM, right: MARGEM },
            head: cabecalho ? [cabecalho] : undefined,
            body: corpo,
            theme: 'striped',
            showHead: 'everyPage',
            rowPageBreak: 'auto',
            styles: { font: 'helvetica', fontSize: 9, cellPadding: 3, textColor: COR_TEXTO, overflow: 'linebreak', valign: 'top', lineColor: [225, 231, 228], lineWidth: 0.1 },
            headStyles: { fillColor: COR_MARCA, textColor: [255, 255, 255], fontStyle: 'bold' },
            alternateRowStyles: { fillColor: [244, 247, 245] },
            columnStyles: colunas,
        });
        y = documento.lastAutoTable.finalY + 10;
    }

    paragrafo(dados.nome, { tamanho: 20, negrito: true });
    paragrafo(dados.contato);
    titulo('Resumo do cliente');
    tabela(null, dados.resumo, { 0: { cellWidth: 45, fontStyle: 'bold' } });
    titulo('Observações');
    paragrafo(dados.observacoes);
    titulo('Preferências');
    paragrafo(dados.preferencias);
    titulo('Atendimentos e faltas');
    if (dados.atendimentos.length) {
        tabela(['Data', 'Profissional / serviços', 'Status', 'Valor'], dados.atendimentos, {
            0: { cellWidth: 31 }, 1: { cellWidth: 71 }, 2: { cellWidth: 34 }, 3: { cellWidth: 42 },
        });
    } else paragrafo('Nenhum atendimento registrado.');
    titulo('Histórico financeiro');
    if (dados.pagamentos.length) {
        tabela(['Data', 'Agendamento', 'Forma / descrição', 'Valor', 'Status'], dados.pagamentos, {
            0: { cellWidth: 29 }, 1: { cellWidth: 29 }, 2: { cellWidth: 44 }, 3: { cellWidth: 39 }, 4: { cellWidth: 37 },
        });
    } else paragrafo('Nenhum lançamento financeiro registrado.');

    const paginas = documento.getNumberOfPages();
    for (let pagina = 1; pagina <= paginas; pagina++) {
        documento.setPage(pagina);
        documento.setFillColor(...COR_MARCA);
        documento.rect(0, 0, 210, 25, 'F');
        documento.setTextColor(255, 255, 255);
        documento.setFont('helvetica', 'bold');
        documento.setFontSize(16);
        documento.text('CORTAÊ', MARGEM, 12);
        documento.setFont('helvetica', 'normal');
        documento.setFontSize(9);
        documento.text('Ficha do cliente', MARGEM, 19);
        documento.text(`Emitido em ${momento(dataGeracao.toISOString())}`, 194, 16, { align: 'right' });
        documento.setDrawColor(215, 225, 220);
        documento.line(MARGEM, 282, 194, 282);
        documento.setTextColor(86, 100, 93);
        documento.setFontSize(8);
        documento.text('PDF usa os dados exibidos; salve alterações para manter no sistema.', MARGEM, 287);
        documento.text(`Página ${pagina} de ${paginas}`, 194, 292, { align: 'right' });
    }
    return { documento, nomeArquivo: nomeArquivoFichaCliente(dados.nome, dataGeracao) };
}

export async function baixarFichaClientePdf(detalhe) {
    const { documento, nomeArquivo } = gerarFichaClientePdf(detalhe);
    await documento.save(nomeArquivo, { returnPromise: true });
}

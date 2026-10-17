import Select from '../../components/Select/Select';
import { useEffect, useState } from 'react';
import { FiEdit2, FiImage, FiPlus, FiTrash2 } from 'react-icons/fi';
import { urlDaApi, apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import ModalConfirmacao from '../../components/ModalConfirmacao/ModalConfirmacao';
import styles from './AdminCortes.module.css';

const FORM_INICIAL = { nome: '', descricao: '', categoria: 'cabelo', genero: '', imagem: null, imagem_url: '' };
const categoriaLabel = { cabelo: 'Cabelo', barba: 'Barba', barba_cabelo: 'Cabelo e barba', corte_pintura: 'Corte e Pintura', pintura: 'Pintura' };
const generoLabel = { masculino: 'Masculino', feminino: 'Feminino', unissex: 'Unissex' };

function ImagemCorte({ corte }) {
    const [urlComErro, setUrlComErro] = useState(null);
    const url = urlDaApi(corte.imagem_url);
    if (!url || urlComErro === url) return <div className={styles.referenceMissing}><FiImage aria-hidden="true" /><span>Referência não disponível</span></div>;
    return <img src={url} alt={`Referência de ${corte.nome}`} onError={() => setUrlComErro(url)} />;
}

export default function AdminCortes() {
    const [cortes, setCortes] = useState([]);
    const [form, setForm] = useState(FORM_INICIAL);
    const [editando, setEditando] = useState(null);
    const [erro, setErro] = useState('');
    const [mensagem, setMensagem] = useState('');
    const [salvando, setSalvando] = useState(false);
    const [pagina, setPagina] = useState(1);
    const [corteRemovendo, setCorteRemovendo] = useState(null);
    const [removendo, setRemovendo] = useState(false);
    const ITENS_POR_PAGINA = 15; // grade 3 x 5

    const totalPaginas = Math.max(1, Math.ceil(cortes.length / ITENS_POR_PAGINA));
    const paginaSegura = Math.min(pagina, totalPaginas);
    const cortesPagina = cortes.slice((paginaSegura - 1) * ITENS_POR_PAGINA, paginaSegura * ITENS_POR_PAGINA);

    async function carregar() {
        try {
            const dados = await apiFetch('/visagismo/cortes');
            setCortes(dados.cortes || []);
            setPagina(1);
        } catch (error) { setErro(mensagemDaApi(error)); }
    }
    useEffect(() => {
        queueMicrotask(carregar);
    }, []);

    function editar(corte) {
        setEditando(corte.id_corte);
        setForm({ nome: corte.nome || '', descricao: corte.descricao || '', categoria: corte.categoria || 'cabelo', genero: corte.genero || '', imagem: null, imagem_url: /^https:\/\//i.test(corte.imagem_url || '') ? corte.imagem_url : '' });
        setErro('');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
    function cancelar() { setEditando(null); setForm(FORM_INICIAL); }
    function atualizar(campo, valor) { setForm((atual) => ({ ...atual, [campo]: valor })); }

    async function salvar(event) {
        event.preventDefault();
        if (salvando) return;
        if (!form.nome.trim()) return setErro('Informe o nome do corte.');
        if (!editando && !form.imagem && !form.imagem_url.trim()) return setErro('Envie uma imagem ou informe uma URL de referência para o corte.');
        if (form.imagem_url.trim()) {
            try {
                const url = new URL(form.imagem_url.trim());
                if (url.protocol !== 'https:') throw new Error();
            } catch { return setErro('Informe uma URL HTTPS válida para a imagem de referência.'); }
        }
        setSalvando(true); setErro(''); setMensagem('');
        try {
            const dados = new FormData();
            dados.append('nome', form.nome.trim());
            dados.append('descricao', form.descricao.trim());
            dados.append('categoria', form.categoria);
            dados.append('genero', form.genero || 'unissex');
            if (form.imagem) dados.append('imagem', form.imagem);
            else if (form.imagem_url.trim()) dados.append('imagem_url', form.imagem_url.trim());
            const resposta = await apiFetch(editando ? `/visagismo/cortes/${editando}` : '/visagismo/cortes', { method: editando ? 'PUT' : 'POST', body: dados });
            setMensagem(resposta.mensagem?.informacao || 'Corte salvo com sucesso.');
            cancelar();
            await carregar();
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setSalvando(false); }
    }
    function remover(corte) {
        // Abre o modal de confirmação (substitui o window.confirm nativo)
        setCorteRemovendo(corte);
    }
    async function confirmarRemocao() {
        if (!corteRemovendo) return;
        setRemovendo(true);
        try {
            const resposta = await apiFetch(`/visagismo/cortes/${corteRemovendo.id_corte}`, { method: 'DELETE' });
            setMensagem(resposta.mensagem?.informacao || 'Corte removido.');
            setCorteRemovendo(null);
            await carregar();
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setRemovendo(false); }
    }

    return <main className={styles.page}>
        <header className={styles.header}><div><p className={styles.eyebrow}>ADMINISTRAÇÃO</p><h1>Catálogo de cortes</h1><p>Cadastre as referências que serão usadas no visagismo e exibidas aos clientes.</p></div></header>
        {erro && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />}
        {mensagem && <MensagemCard mensagem={{ informacao: mensagem, tipo: 'sucesso' }} fechar={() => setMensagem('')} />}
        <section className={styles.formCard}>
            <div className={styles.sectionTitle}><FiPlus /> {editando ? 'Editar tipo de corte' : 'Adicionar tipo de corte'}</div>
            <form onSubmit={salvar} className={styles.form}>
                <label>Nome do corte<input value={form.nome} onChange={(e) => atualizar('nome', e.target.value)} placeholder="Ex.: Corte degradê" /></label>
                <label>Categoria<Select value={form.categoria} onChange={(e) => atualizar('categoria', e.target.value)}><option value="cabelo">Cabelo</option><option value="masculino">Cabelo masculino</option><option value="feminino">Cabelo feminino</option><option value="barba">Barba</option><option value="barba_cabelo">Cabelo e barba</option><option value="corte_pintura">Corte e Pintura</option><option value="pintura">Pintura</option></Select></label>
                <label>Gênero<Select value={form.genero} onChange={(e) => atualizar('genero', e.target.value)}><option value="">Unissex</option><option value="masculino">Masculino</option><option value="feminino">Feminino</option></Select></label>
                <label className={styles.full}>Descrição breve<textarea value={form.descricao} onChange={(e) => atualizar('descricao', e.target.value)} placeholder="Descreva a referência para orientar a recomendação." /></label>
                <label className={styles.full}>URL da imagem de referência<input type="url" placeholder="https://site.com/imagem.jpg" value={form.imagem_url} disabled={salvando} onChange={(e) => setForm((atual) => ({ ...atual, imagem_url: e.target.value, imagem: null }))} /><small>Use uma URL HTTPS direta de imagem ou envie um arquivo abaixo.</small></label>
                <label className={styles.upload}><FiImage /> {form.imagem ? form.imagem.name : editando ? 'Trocar imagem (opcional)' : 'Enviar imagem de referência'}<input type="file" accept="image/png,image/jpeg,image/webp" disabled={salvando} onChange={(e) => { const arquivo = e.target.files?.[0] || null; setForm((atual) => ({ ...atual, imagem: arquivo, imagem_url: arquivo ? '' : atual.imagem_url })); e.target.value = ''; }} /></label>
                <div className={styles.actions}><button className={styles.primary} disabled={salvando}>{salvando ? 'Salvando…' : editando ? 'Salvar alterações' : 'Adicionar corte'}</button>{editando && <button type="button" className={styles.secondary} onClick={cancelar}>Cancelar</button>}</div>
            </form>
        </section>
        <section><div className={styles.listTitle}><h2>Cortes cadastrados</h2><span>{cortes.length} item(ns) · página {paginaSegura} de {totalPaginas}</span></div><div className={styles.grid}>{cortesPagina.map((corte) => <article className={styles.card} key={corte.id_corte}><ImagemCorte corte={corte} /><div className={styles.cardBody}><span className={styles.badge}>{categoriaLabel[corte.categoria] || corte.categoria}</span><span className={styles.badge}>{generoLabel[corte.genero] || 'Unissex'}</span><h3>{corte.nome}</h3><p>{corte.descricao || 'Sem descrição cadastrada.'}</p><div className={styles.cardActions}><button onClick={() => editar(corte)}><FiEdit2 /> Editar</button><button onClick={() => remover(corte)}><FiTrash2 /> Remover</button></div></div></article>)}</div>{!cortes.length && <p className={styles.empty}>Nenhum corte cadastrado ainda.</p>}
            {totalPaginas > 1 && <div className={styles.paginacao}>
                <button type="button" disabled={paginaSegura === 1} onClick={() => setPagina(paginaSegura - 1)} aria-label="Página anterior">‹</button>
                {Array.from({ length: totalPaginas }, (_, i) => i + 1).map((p) => <button type="button" key={p} className={p === paginaSegura ? styles.paginaAtiva : ''} onClick={() => setPagina(p)} aria-current={p === paginaSegura ? 'page' : undefined}>{p}</button>)}
                <button type="button" disabled={paginaSegura === totalPaginas} onClick={() => setPagina(paginaSegura + 1)} aria-label="Próxima página">›</button>
            </div>}
        </section>

        <ModalConfirmacao
            aberto={!!corteRemovendo}
            titulo="Remover do catálogo"
            mensagem={`Deseja remover “${corteRemovendo?.nome || ''}” do catálogo de cortes?`}
            detalhe="O corte deixará de aparecer nas recomendações do visagismo."
            textoConfirmar="Remover"
            textoCancelar="Voltar"
            perigo
            processando={removendo}
            aoConfirmar={confirmarRemocao}
            aoCancelar={() => setCorteRemovendo(null)}
        />
    </main>;
}



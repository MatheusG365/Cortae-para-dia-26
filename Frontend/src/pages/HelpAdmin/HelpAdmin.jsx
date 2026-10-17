import Select from '../../components/Select/Select';
import { useEffect, useMemo, useRef, useState } from 'react';
import { FiArrowRight, FiBookOpen, FiCode, FiFileText, FiFilter, FiSearch, FiShield, FiSmartphone, FiUsers, FiX } from 'react-icons/fi';
import { apiFetch, mensagemDaApi, urlDaApi } from '../../services/api';
import { filtrarRotas, rotuloArea, rotuloOrigem, rotaVinculada, selecionarRota } from './helpCatalogo';
import styles from './HelpAdmin.module.css';
import VisaoImagens from './VisaoImagens';

function ListaInformacao({ titulo, itens, vazio }) {
    return <section className={styles.informacao}>
        <h3>{titulo}</h3>
        {itens?.length ? <ul>{itens.map((item, indice) => <li key={indice}>{item}</li>)}</ul> : <p>{vazio}</p>}
    </section>;
}

function CodigoFonte({ arquivo }) {
    const [consulta, setConsulta] = useState({ estado: 'carregando', dados: null, erro: '' });
    const [tentativa, setTentativa] = useState(0);
    useEffect(() => {
        const controle = new AbortController();
        apiFetch(`/admin/help/codigo/${encodeURIComponent(arquivo.id)}`, { signal: controle.signal })
            .then(dados => { if (!controle.signal.aborted) setConsulta({ estado: 'pronto', dados, erro: '' }); })
            .catch(erro => { if (!controle.signal.aborted) setConsulta({ estado: 'erro', dados: null, erro: mensagemDaApi(erro) }); });
        return () => controle.abort();
    }, [arquivo.id, tentativa]);

    return <div className={styles.fonte}>
        <div className={styles.fonteCabecalho}>
            <div><FiFileText aria-hidden="true" /><strong>{arquivo.caminho}</strong></div>
            <span>{consulta.dados?.linguagem || arquivo.linguagem}{consulta.dados?.total_linhas != null ? ` · ${consulta.dados.total_linhas} linhas` : ''}</span>
        </div>
        {consulta.estado === 'carregando' && <p className={styles.estado} role="status">Carregando código protegido…</p>}
        {consulta.estado === 'erro' && <div className={styles.erro} role="alert"><p>{consulta.erro}</p><button type="button" onClick={() => { setConsulta({ estado: 'carregando', dados: null, erro: '' }); setTentativa(valor => valor + 1); }}>Tentar novamente</button></div>}
        {consulta.estado === 'pronto' && <>
            {consulta.dados.avisos?.length > 0 && <div className={styles.aviso}>{consulta.dados.avisos.map((aviso, indice) => <p key={indice}>{aviso}</p>)}</div>}
            <pre className={styles.codigo} tabIndex={0} aria-label={`Código de ${arquivo.caminho}`}><code>{consulta.dados.conteudo || 'Arquivo sem conteúdo.'}</code></pre>
        </>}
    </div>;
}

function VisaoMobile({ mobile, rotas, onSelecionar, onArea }) {
    const telas = rotas.filter(rota => rota.origem === 'mobile');
    return <section className={styles.mobile} aria-labelledby="help-mobile-titulo">
        <div className={styles.mobileTopo}>
            <div className={styles.mobileIcone}><FiSmartphone aria-hidden="true" /></div>
            <div><p className={styles.eyebrow}>MOBILE · REACT NATIVE</p><h2 id="help-mobile-titulo">{mobile?.titulo || 'Aplicativo mobile'}</h2><p>{mobile?.descricao || 'Consulte pelo site as telas e o funcionamento do aplicativo para clientes e barbearias.'}</p></div>
            <span className={styles.mobileContagem}>{telas.length} telas</span>
        </div>
        {telas.length > 0 ? <>
            <div className={styles.mobileAreas}>{['publico', 'cliente', 'barbearia'].map(area => <button type="button" key={area} onClick={() => onArea(area)}><FiUsers aria-hidden="true" /><span><strong>{rotuloArea(area)}</strong><small>{telas.filter(rota => rota.area === area).length} telas documentadas</small></span><FiArrowRight aria-hidden="true" /></button>)}</div>
            <details className={styles.mobileFuncionamento}><summary>Como o aplicativo se conecta ao sistema</summary>{(mobile?.funcionamento || ['O aplicativo compartilha a API do site e possui telas para clientes e barbearias. O administrador acompanha o sistema pelo site.', 'A conexão é definida automaticamente durante o desenvolvimento e pela equipe na publicação. O usuário não configura IP ou servidor no aplicativo.']).map((texto, indice) => <p key={indice}>{texto}</p>)}</details>
            {!!mobile?.fluxos?.length && <div className={styles.fluxos}><h3>Principais jornadas no aplicativo</h3><div className={styles.fluxosGrade}>{mobile.fluxos.map(fluxo => <details key={fluxo.id}><summary>{fluxo.titulo}</summary><ol>{fluxo.etapas?.map((etapa, indice) => <li key={indice}>{etapa}</li>)}</ol><div className={styles.vinculos}>{fluxo.rotas?.map(id => rotaVinculada(telas, id)).filter(Boolean).map(rota => <button type="button" key={rota.id} onClick={() => onSelecionar(rota.id)}>{rota.titulo || rota.rota}<FiArrowRight aria-hidden="true" /></button>)}</div></details>)}</div></div>}
            {!!mobile?.observacoes?.length && <div className={styles.mobileNotas}>{mobile.observacoes.map((texto, indice) => <p key={indice}>{texto}</p>)}</div>}
        </> : <p className={styles.mobileIndisponivel}>A documentação mobile ainda não foi disponibilizada por esta versão da API. Atualize o backend para consultar as telas e seus códigos nesta central.</p>}
    </section>;
}

function DetalhesRota({ rota, rotas, onSelecionar }) {
    const [aba, setAba] = useState('funcionamento');
    const [arquivoId, setArquivoId] = useState(rota.arquivos?.[0]?.id || '');
    const arquivo = rota.arquivos?.find(item => item.id === arquivoId) || rota.arquivos?.[0];
    return <article className={styles.detalhe}>
        <div className={styles.detalheTopo}>
            <div className={styles.marcas}><span className={styles.origem}>{rotuloOrigem(rota.origem)}</span>{rota.origem === 'mobile' && rota.area && <span className={styles.area}>{rotuloArea(rota.area)}</span>}{rota.metodos?.map(metodo => <span className={styles.metodo} key={metodo}>{metodo}</span>)}</div>
            <h2>{rota.titulo || rota.endpoint || rota.rota}</h2>
            <p className={styles.caminho}>{rota.rota}</p>
            <p className={styles.descricao}>{rota.descricao}</p>
            <div className={styles.acesso}><FiShield aria-hidden="true" /><span>{rota.acesso || 'Acesso definido pela rota.'}</span></div>
        </div>
        <div className={styles.abas} role="tablist" aria-label="Detalhes da rota">
            <button id="help-aba-funcionamento" role="tab" aria-selected={aba === 'funcionamento'} aria-controls="help-painel-funcionamento" type="button" onClick={() => setAba('funcionamento')}><FiBookOpen aria-hidden="true" />Funcionamento</button>
            <button id="help-aba-codigo" role="tab" aria-selected={aba === 'codigo'} aria-controls="help-painel-codigo" type="button" onClick={() => setAba('codigo')}><FiCode aria-hidden="true" />Código-fonte <span>{rota.arquivos?.length || 0}</span></button>
        </div>
        {aba === 'funcionamento' ? <div id="help-painel-funcionamento" role="tabpanel" aria-labelledby="help-aba-funcionamento" className={styles.conteudo}>
            <ListaInformacao titulo="Como funciona" itens={rota.como_funciona} vazio="Consulte os arquivos associados para acompanhar a implementação desta rota." />
            <div className={styles.dadosGrade}>
                <ListaInformacao titulo="O que recebe" itens={rota.entrada} vazio="Nenhuma entrada documentada nesta rota." />
                <ListaInformacao titulo="O que retorna" itens={rota.saida} vazio="Consulte a implementação para os detalhes da resposta." />
            </div>
            {!!rota.observacoes?.length && <ListaInformacao titulo="Observações" itens={rota.observacoes} />}
            {!!rota.api_relacionada?.length && <section className={styles.informacao}><h3>API utilizada por esta tela</h3><p>Abra a documentação da API para acompanhar o código do backend. Estes botões apenas consultam a documentação.</p><div className={styles.apisRelacionadas}>{rota.api_relacionada.map(api => <button type="button" key={api.id} disabled={!rotaVinculada(rotas, api.id)} onClick={() => onSelecionar(api.id)}><span>{api.titulo || 'Consultar API'}</span><code>{api.metodos?.join(' / ')} {api.rota}</code><FiArrowRight aria-hidden="true" /></button>)}</div></section>}
            <section className={styles.informacao}><h3>Arquivos da implementação</h3>{rota.arquivos?.length ? <ul className={styles.arquivosResumo}>{rota.arquivos.map(item => <li key={item.id}><FiFileText aria-hidden="true" /><span>{item.caminho}{item.linha_inicio ? ` · linha ${item.linha_inicio}` : ''}</span></li>)}</ul> : <p>Nenhum arquivo associado.</p>}</section>
        </div> : <div id="help-painel-codigo" role="tabpanel" aria-labelledby="help-aba-codigo" className={styles.conteudo}>
            <p className={styles.nota}>Leitura da implementação atual. Selecione um arquivo para consultar o código.</p>
            {rota.arquivos?.length > 0 ? <>
                <label className={styles.arquivoSeletor}>Arquivo<Select value={arquivo?.id || ''} onChange={evento => setArquivoId(evento.target.value)}>{rota.arquivos.map(item => <option value={item.id} key={item.id}>{item.caminho}</option>)}</Select></label>
                {arquivo && <CodigoFonte key={arquivo.id} arquivo={arquivo} />}
            </> : <p className={styles.estado}>Nenhum código-fonte associado a esta rota.</p>}
        </div>}
    </article>;
}

export default function HelpAdmin() {
    const [consulta, setConsulta] = useState({ estado: 'carregando', dados: null, erro: '' });
    const [tentativa, setTentativa] = useState(0);
    const [busca, setBusca] = useState('');
    const [origem, setOrigem] = useState('');
    const [metodo, setMetodo] = useState('');
    const [area, setArea] = useState('');
    const [rotaId, setRotaId] = useState('');
    const detalheRef = useRef(null);
    useEffect(() => {
        const controle = new AbortController();
        apiFetch('/admin/help/catalogo', { signal: controle.signal })
            .then(dados => { if (!controle.signal.aborted) setConsulta({ estado: 'pronto', dados, erro: '' }); })
            .catch(erro => { if (!controle.signal.aborted) setConsulta({ estado: 'erro', dados: null, erro: mensagemDaApi(erro) }); });
        return () => controle.abort();
    }, [tentativa]);
    const rotas = consulta.dados?.rotas;
    const fluxos = consulta.dados?.mobile?.fluxos;
    const filtradas = useMemo(() => filtrarRotas(rotas || [], { busca, origem, metodo, area, fluxos }), [rotas, busca, origem, metodo, area, fluxos]);
    const metodos = useMemo(() => [...new Set((rotas || []).flatMap(rota => rota.metodos || []))].sort(), [rotas]);
    const selecionada = selecionarRota(filtradas, rotaId);
    const temFiltro = Boolean(busca || origem || metodo || area);
    function limparFiltros() { setBusca(''); setOrigem(''); setMetodo(''); setArea(''); }
    function abrirDocumento(id) {
        if (!rotaVinculada(rotas || [], id)) return;
        limparFiltros();
        selecionar(id, true);
    }
    function filtrarArea(valor) {
        limparFiltros();
        setOrigem('mobile');
        setArea(valor);
        requestAnimationFrame(() => document.getElementById('help-filtros')?.scrollIntoView({ behavior: 'smooth', block: 'start' }));
    }
    function selecionar(id, revelar = false) {
        setRotaId(id);
        if (revelar || window.matchMedia('(max-width: 850px)').matches) requestAnimationFrame(() => {
            detalheRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            detalheRef.current?.focus({ preventScroll: true });
        });
    }

    return <main className={styles.pagina}>
        <header className={styles.cabecalho}>
            <div><p className={styles.eyebrow}><FiShield aria-hidden="true" />EXCLUSIVO DO ADMINISTRADOR</p><h1>Central técnica do sistema</h1><p>Entenda o site, o aplicativo mobile e a API compartilhada. Consulte o funcionamento e o código de cada parte.</p></div>
            <span className={styles.endereco}><FiBookOpen aria-hidden="true" />/help</span>
        </header>
        {consulta.estado === 'carregando' && <p className={styles.estado} role="status">Carregando documentação do sistema…</p>}
        {consulta.estado === 'erro' && <div className={styles.erro} role="alert"><h2>Não foi possível carregar a documentação</h2><p>{consulta.erro}</p><button type="button" onClick={() => { setConsulta({ estado: 'carregando', dados: null, erro: '' }); setTentativa(valor => valor + 1); }}>Tentar novamente</button></div>}
        {consulta.estado === 'pronto' && <>
            <section className={styles.guia} aria-labelledby="help-guia-titulo">
                <div className={styles.guiaTitulo}><FiBookOpen aria-hidden="true" /><div><h2 id="help-guia-titulo">{consulta.dados.ajuda?.titulo || 'Como usar esta página'}</h2><p>Acesse digitando <strong>/help</strong> na URL, com a conta de administrador.</p></div></div>
                <ol>{(consulta.dados.ajuda?.passos || ['Busque uma rota e use os filtros.', 'Selecione um resultado para entender seu funcionamento.', 'Abra Código-fonte e escolha um arquivo.']).map((passo, indice) => <li key={indice}>{passo}</li>)}</ol>
                <div className={styles.documentacaoApi}>
                    <a href={urlDaApi('/docs')} target="_blank" rel="noopener noreferrer"><FiBookOpen aria-hidden="true" />Documentação da API</a>
                    <p>Abre em uma nova aba e exige a sessão de administrador autenticada. O acesso é conferido pelo servidor.</p>
                </div>
                <details><summary>Sobre acesso e documentação</summary>{consulta.dados.ajuda?.seguranca?.map((texto, indice) => <p key={indice}>{texto}</p>)}<p>Esta central também está no catálogo: busque por “help” para consultar seu funcionamento e seus arquivos.</p></details>
            </section>
            <VisaoImagens imagens={consulta.dados.imagens} rotas={rotas || []} onSelecionar={abrirDocumento} />
            <VisaoMobile mobile={consulta.dados.mobile} rotas={rotas || []} onSelecionar={abrirDocumento} onArea={filtrarArea} />
            <section id="help-filtros" className={styles.filtros} aria-label="Filtrar documentação">
                <label className={styles.busca}>Buscar rota ou assunto<div><FiSearch aria-hidden="true" /><input type="search" placeholder="Ex.: Drive, imagens, mobile, checkout…" value={busca} onChange={evento => setBusca(evento.target.value)} /></div></label>
                <label>Origem<Select value={origem} onChange={evento => { setOrigem(evento.target.value); setArea(''); }}><option value="">Site, mobile e API</option><option value="frontend">Site · páginas</option><option value="mobile">Mobile · telas</option><option value="backend">Backend · API</option></Select></label>
                <label>Área do aplicativo<Select value={area} onChange={evento => { setArea(evento.target.value); if (evento.target.value) setOrigem('mobile'); }} disabled={Boolean(origem && origem !== 'mobile')}><option value="">Todas as áreas</option><option value="publico">Acesso e cadastro</option><option value="cliente">Cliente</option><option value="barbearia">Barbearia</option></Select></label>
                <label>Método<Select value={metodo} onChange={evento => setMetodo(evento.target.value)}><option value="">Todos os métodos</option>{metodos.map(item => <option key={item} value={item}>{item === 'PAGE' ? 'PAGE · página' : item}</option>)}</Select></label>
                <button className={styles.limpar} type="button" onClick={limparFiltros} disabled={!temFiltro}><FiX aria-hidden="true" />Limpar</button>
            </section>
            <div className={styles.resumo} role="status"><span><FiFilter aria-hidden="true" /><strong>{filtradas.length}</strong> de {rotas?.length || 0} documentos</span><span>{consulta.dados.total?.frontend ?? rotas?.filter(rota => rota.origem === 'frontend').length} páginas web · {consulta.dados.total?.mobile ?? rotas?.filter(rota => rota.origem === 'mobile').length} telas mobile · {consulta.dados.total?.backend ?? rotas?.filter(rota => rota.origem === 'backend').length} rotas da API</span></div>
            {filtradas.length ? <div className={styles.layout}>
                <nav className={styles.lista} aria-label="Rotas encontradas">{filtradas.map(rota => <button type="button" key={rota.id} aria-current={rota.id === selecionada?.id ? 'true' : undefined} onClick={() => selecionar(rota.id)}>
                    <span className={styles.listaMeta}><span>{rotuloOrigem(rota.origem, true)}{rota.origem === 'mobile' && rota.area ? ` · ${rotuloArea(rota.area)}` : ''}</span><span>{rota.metodos?.join(' / ')}</span></span>
                    <strong>{rota.titulo || rota.endpoint || rota.rota}</strong><span className={styles.listaCaminho}>{rota.rota}</span>
                </button>)}</nav>
                <div className={styles.detalheAlvo} ref={detalheRef} tabIndex={-1}><DetalhesRota key={selecionada.id} rota={selecionada} rotas={rotas || []} onSelecionar={abrirDocumento} /></div>
            </div> : <div className={styles.vazio}><FiSearch aria-hidden="true" /><h2>Nenhuma rota encontrada</h2><p>Tente outro assunto, nome de arquivo ou combinação de filtros.</p><button type="button" onClick={limparFiltros}>Limpar filtros</button></div>}
        </>}
    </main>;
}

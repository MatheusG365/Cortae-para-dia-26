import { FiArrowRight, FiGitMerge } from 'react-icons/fi';
import { rotaVinculada } from './helpCatalogo';
import styles from './HelpAdmin.module.css';

export default function VisaoRequisicoes({ requisicoes, rotas, onSelecionar }) {
    if (!requisicoes?.guias?.length) return null;
    return <section className={styles.mobile} aria-labelledby="help-requisicoes-titulo">
        <div className={styles.mobileTopo}>
            <div className={styles.mobileIcone}><FiGitMerge aria-hidden="true" /></div>
            <div><p className={styles.eyebrow}>REQUISIÇÕES · PASSO A PASSO</p><h2 id="help-requisicoes-titulo">{requisicoes.titulo}</h2><p>Entenda a sequência das chamadas, o que o servidor confere e onde investigar uma falha.</p></div>
        </div>
        <ul className={styles.imagensLista}>{(requisicoes.observacoes || []).map(item => <li key={item}>{item}</li>)}</ul>
        <div className={styles.fluxosGrade}>{requisicoes.guias.map(guia => <details key={guia.id} id={`help-fluxo-${guia.id}`} className={styles.guiaRequisicao}>
            <summary>{guia.titulo}</summary>
            <p>{guia.descricao}</p>
            <h3>Sequência da operação</h3>
            <ol className={styles.imagensLista}>{guia.etapas.map((etapa, indice) => <li key={indice}>{etapa}</li>)}</ol>
            <h3>Requisições e respostas</h3>
            {guia.requisicoes.map((req, indice) => <section className={styles.requisicao} key={`${req.metodo}:${req.rota}:${indice}`}>
                <h4><span className={styles.metodo}>{req.metodo}</span> <code>{req.rota}</code></h4>
                <p><strong>Recebe:</strong> {req.entrada}</p><p><strong>Retorna:</strong> {req.saida}</p>
                {req.corpo && <><p className={styles.nota}>Campos de exemplo; não executa a requisição.</p><pre tabIndex={0} aria-label={`Exemplo de campos para ${req.metodo} ${req.rota}`}><code>{JSON.stringify(req.corpo, null, 2)}</code></pre></>}
                {req.api_id && <button type="button" className={styles.abrirRequisicao} disabled={!rotaVinculada(rotas, req.api_id)} onClick={() => onSelecionar(req.api_id)}>Consultar contrato e código <FiArrowRight aria-hidden="true" /></button>}
            </section>)}
            <h3>Diagnóstico e limites</h3><ul className={styles.imagensLista}>{guia.diagnostico.map(item => <li key={item}>{item}</li>)}</ul>
        </details>)}</div>
    </section>;
}

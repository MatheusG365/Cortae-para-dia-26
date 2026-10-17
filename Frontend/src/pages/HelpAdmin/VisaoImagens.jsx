import { FiArrowRight, FiFileText, FiImage } from 'react-icons/fi';
import { rotaVinculada } from './helpCatalogo';
import styles from './HelpAdmin.module.css';

export default function VisaoImagens({ imagens, rotas, onSelecionar }) {
    // APIs anteriores continuam oferecendo o catálogo, mesmo sem este resumo.
    if (!imagens) return null;
    return <section className={styles.mobile} aria-labelledby="help-imagens-titulo">
        <div className={styles.mobileTopo}>
            <div className={styles.mobileIcone}><FiImage aria-hidden="true" /></div>
            <div><p className={styles.eyebrow}>IMAGENS · SITE E APLICATIVO</p><h2 id="help-imagens-titulo">{imagens.titulo}</h2><p>{imagens.descricao}</p></div>
        </div>
        {!!imagens.etapas?.length && <div className={styles.fluxos}><h3>Da seleção à exibição da imagem</h3><ol className={styles.imagensEtapas}>{imagens.etapas.map((etapa, indice) => <li key={indice}><span aria-hidden="true">{indice + 1}</span><p>{etapa}</p></li>)}</ol></div>}
        <div className={styles.fluxosGrade}>
            {!!imagens.tipos?.length && <details><summary>Onde as imagens são utilizadas</summary><ul className={styles.imagensLista}>{imagens.tipos.map((tipo, indice) => <li key={indice}>{tipo}</li>)}</ul></details>}
            {!!imagens.observacoes?.length && <details><summary>Permissões, limites e disponibilidade</summary><ul className={styles.imagensLista}>{imagens.observacoes.map((observacao, indice) => <li key={indice}>{observacao}</li>)}</ul></details>}
        </div>
        {!!imagens.apis?.length && <div className={styles.fluxos}><h3>Rotas e código das imagens</h3><p className={styles.nota}>Os botões abrem somente a documentação. Não enviam imagens nem executam as rotas descritas.</p><div className={styles.apisRelacionadas}>{imagens.apis.map(api => <button type="button" key={api.id} disabled={!rotaVinculada(rotas, api.id)} onClick={() => onSelecionar(api.id)}><span>{api.titulo || 'Consultar API'}</span><code>{api.metodos?.join(' / ')} {api.rota}</code><FiArrowRight aria-hidden="true" /></button>)}</div></div>}
        {!!imagens.arquivos?.length && <details className={`${styles.mobileFuncionamento} ${styles.imagensArquivos}`}><summary>Arquivos que implementam o armazenamento</summary><ul className={`${styles.arquivosResumo} ${styles.imagensLista}`}>{imagens.arquivos.map((arquivo, indice) => <li key={arquivo.id || indice}><FiFileText aria-hidden="true" /><span>{arquivo.caminho}</span></li>)}</ul></details>}
    </section>;
}

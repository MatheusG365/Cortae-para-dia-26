import { useEffect, useId, useRef } from 'react';
import { Upload } from 'lucide-react';
import { FotoProduto } from './MarketplaceUI';
import { fotosValidas } from './marketplaceState';
import { validarFotosProduto } from './produtoImagens';
import styles from './FotosProdutoEditor.module.css';

function FotoLocal({ arquivo, indice }) {
    const ref = useRef(null);
    useEffect(() => {
        const url = URL.createObjectURL(arquivo);
        if (ref.current) ref.current.src = url;
        return () => URL.revokeObjectURL(url);
    }, [arquivo]);
    return <img ref={ref} alt={`Nova foto ${indice + 1}`} />;
}

export default function FotosProdutoEditor({ links, setLinks, arquivos, setArquivos, ocupado, onErro }) {
    const ajudaId = useId();
    const existentes = fotosValidas(links);
    const total = existentes.length + arquivos.length;
    const desabilitado = ocupado || total >= 8;
    function adicionar(event) {
        const novos = [...arquivos, ...Array.from(event.target.files || [])];
        event.target.value = '';
        try { validarFotosProduto(existentes, novos); setArquivos(novos); onErro(''); }
        catch (error) { onErro(error.message); }
    }
    return <section className={styles.editor} aria-label="Fotos do produto">
        <div className={styles.cabecalho}>
            <div><h3>Fotos do produto</h3><p>Mostre os detalhes do produto. Fotos otimizadas automaticamente.</p></div>
            <span className={styles.contador} aria-live="polite">{total}/8 fotos</span>
        </div>
        <label className={styles.seletor} data-desabilitado={desabilitado}>
            <input className={styles.arquivoInput} aria-label="Selecionar fotos do produto" aria-describedby={ajudaId} type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple onChange={adicionar} disabled={desabilitado} />
            <span className={styles.iconeUpload}><Upload size={22} aria-hidden="true" /></span>
            <span className={styles.textoSeletor}><strong>Adicionar fotos</strong><span>Selecione imagens no seu dispositivo</span></span>
            <span className={styles.botaoSelecionar}>Selecionar fotos</span>
        </label>
        <div className={styles.informacoes}>
            <small id={ajudaId}>JPEG, PNG, WebP ou GIF · Até oito fotos de 10 MB cada. A primeira será a capa.</small>
            <p className={styles.selecaoStatus} role="status">{ocupado ? 'Aguarde o envio das fotos…' : total >= 8 ? 'Limite de oito fotos atingido.' : arquivos.length ? `${arquivos.length} ${arquivos.length === 1 ? 'nova foto selecionada' : 'novas fotos selecionadas'}` : 'Nenhuma nova foto selecionada.'}</p>
        </div>
        <div className={styles.galeria}>
            {existentes.map((url, index) => <figure key={`${url}:${index}`}><FotoProduto url={url} nome={`Foto ${index + 1}`} /><button type="button" disabled={ocupado} aria-label={`Remover foto ${index + 1}`} onClick={() => setLinks(existentes.filter((_, i) => i !== index).join('\n'))}>Remover</button></figure>)}
            {arquivos.map((arquivo, index) => <figure key={`${arquivo.name}:${index}`}><FotoLocal arquivo={arquivo} indice={index} /><button type="button" disabled={ocupado} aria-label={`Remover nova foto ${index + 1}`} onClick={() => setArquivos(arquivos.filter((_, i) => i !== index))}>Remover</button></figure>)}
        </div>
        <details><summary>Usar fotos por link</summary><label>Um link HTTPS por linha<textarea rows={3} value={links} onChange={event => setLinks(event.target.value)} disabled={ocupado} placeholder="https://exemplo.com/produto.jpg" /></label></details>
    </section>;
}

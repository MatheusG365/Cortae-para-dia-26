import { useEffect, useRef } from 'react';
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
    const existentes = fotosValidas(links);
    function adicionar(event) {
        const novos = [...arquivos, ...Array.from(event.target.files || [])];
        event.target.value = '';
        try { validarFotosProduto(existentes, novos); setArquivos(novos); onErro(''); }
        catch (error) { onErro(error.message); }
    }
    return <section className={styles.editor} aria-label="Fotos do produto"><div className={styles.cabecalho}><div><h3>Fotos do produto</h3><p>Mostre os detalhes do produto. Fotos otimizadas automaticamente.</p></div><span>{existentes.length + arquivos.length}/8 fotos</span></div><label className={styles.seletor}>Adicionar fotos<input aria-label="Selecionar fotos do produto" type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple onChange={adicionar} disabled={ocupado || existentes.length + arquivos.length >= 8} /></label><small>Até oito fotos, com no máximo 10 MB cada. A primeira será a capa.</small><div className={styles.galeria}>{existentes.map((url, index) => <figure key={`${url}:${index}`}><FotoProduto url={url} nome={`Foto ${index + 1}`} /><button type="button" disabled={ocupado} aria-label={`Remover foto ${index + 1}`} onClick={() => setLinks(existentes.filter((_, i) => i !== index).join('\n'))}>Remover</button></figure>)}{arquivos.map((arquivo, index) => <figure key={`${arquivo.name}:${index}`}><FotoLocal arquivo={arquivo} indice={index} /><button type="button" disabled={ocupado} aria-label={`Remover nova foto ${index + 1}`} onClick={() => setArquivos(arquivos.filter((_, i) => i !== index))}>Remover</button></figure>)}</div><details><summary>Usar fotos por link</summary><label>Um link HTTPS por linha<textarea rows={3} value={links} onChange={event => setLinks(event.target.value)} disabled={ocupado} placeholder="https://exemplo.com/produto.jpg" /></label></details></section>;
}

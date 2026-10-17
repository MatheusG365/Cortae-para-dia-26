import { useState } from 'react';
import { Star, X } from 'lucide-react';
import useDialog from '../useDialog';
import { apiFetch, mensagemDaApi } from '../../services/api';
import { momento } from '../../services/gestaoState';
import { erroAvaliacao } from '../../services/avaliacaoState';
import styles from './AvaliacaoAtendimento.module.css';

export function AvaliacaoResumo({ avaliacao }) {
    if (!avaliacao) return null;
    return <div className={styles.resumo}>
        <strong><Star size={16} fill="currentColor" aria-hidden="true" />{avaliacao.nota} / 5 <span>· Avaliação do atendimento</span></strong>
        {avaliacao.comentario && <p>{avaliacao.comentario}</p>}
        <small>Atualizada em {momento(avaliacao.atualizado_em || avaliacao.criado_em)}</small>
    </div>;
}

export default function AvaliacaoAtendimento({ agendamento, aoFechar, aoSalvar, focoAoFechar }) {
    const [nota, setNota] = useState(agendamento.avaliacao?.nota || 0);
    const [comentario, setComentario] = useState(agendamento.avaliacao?.comentario || '');
    const [erro, setErro] = useState('');
    const [processando, setProcessando] = useState(false);
    const dialogo = useDialog(true, aoFechar, processando, focoAoFechar);
    const salvar = async (evento) => {
        evento.preventDefault();
        if (processando) return;
        const falha = erroAvaliacao(nota, comentario);
        if (falha) { setErro(falha); return; }
        setErro(''); setProcessando(true);
        try {
            const resposta = await apiFetch(`/agendamentos/${agendamento.id_agendamento ?? agendamento.id}/avaliacao`, { method: 'PUT', body: JSON.stringify({ nota, comentario }) });
            aoSalvar(resposta);
        } catch (error) { setErro(mensagemDaApi(error)); }
        finally { setProcessando(false); }
    };
    return <div className={styles.overlay} onClick={() => !processando && aoFechar()}>
        <section className={styles.modal} ref={dialogo} role="dialog" aria-modal="true" aria-labelledby="titulo-avaliacao" tabIndex={-1} onClick={(evento) => evento.stopPropagation()}>
            <button type="button" className={styles.fechar} aria-label="Fechar avaliação" disabled={processando} onClick={aoFechar}><X size={20} /></button>
            <p className={styles.sobre}>SUA EXPERIÊNCIA</p><h2 id="titulo-avaliacao">{agendamento.avaliacao ? 'Editar avaliação' : 'Como foi seu atendimento?'}</h2>
            <div className={styles.contexto}><strong>{agendamento.barbearia || agendamento.barbearia_nome}</strong><span>{agendamento.servico || (agendamento.servicos_nomes || []).join(' + ')}</span><span>{momento(agendamento.inicio_em)}</span>{agendamento.funcionario_nome && <span>Profissional: {agendamento.funcionario_nome}</span>}</div>
            <form onSubmit={salvar}>
                <fieldset disabled={processando} className={styles.estrelas}><legend>Sua nota para o atendimento</legend><div>{[1, 2, 3, 4, 5].map((valor) => <label key={valor}>
                    <input type="radio" name="nota-atendimento" value={valor} checked={nota === valor} onChange={() => setNota(valor)} aria-label={`${valor} ${valor === 1 ? 'estrela' : 'estrelas'}`} />
                    <span className={valor <= nota ? styles.estrelaAtiva : ''}><Star size={30} fill={valor <= nota ? 'currentColor' : 'none'} aria-hidden="true" /><small>{valor}</small></span>
                </label>)}</div><p role="status">{nota ? `${nota} de 5 estrelas` : 'Selecione de 1 a 5 estrelas.'}</p></fieldset>
                <label className={styles.comentario}>Conte como foi (opcional)<textarea maxLength={1000} value={comentario} disabled={processando} onChange={(evento) => setComentario(evento.target.value)} rows={4} aria-describedby="limite-comentario" placeholder="O que você gostou? O que poderia melhorar?" /></label>
                <small id="limite-comentario" className={styles.limite}>{comentario.length} / 1.000 caracteres</small>
                <p className={styles.aviso}>Seu comentário poderá ser lido pelo profissional e pela gestão do estabelecimento.</p>
                {erro && <p role="alert" className={styles.erro}>{erro}</p>}
                <footer><button type="button" disabled={processando} onClick={aoFechar}>Voltar</button><button type="submit" disabled={processando || !nota}>{processando ? 'Salvando…' : 'Salvar avaliação'}</button></footer>
            </form>
        </section>
    </div>;
}

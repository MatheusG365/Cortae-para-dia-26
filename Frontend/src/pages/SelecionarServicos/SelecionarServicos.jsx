import { useEffect, useState } from 'react';
import { FiArrowLeft, FiScissors } from 'react-icons/fi';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import styles from './SelecionarServicos.module.css';

export default function SelecionarServicos() {
    const [params] = useSearchParams();
    const navigate = useNavigate();
    const idBarbearia = params.get('barbearia');
    const idFuncionario = params.get('funcionario') || params.get('id_funcionario');
    const [servicos, setServicos] = useState([]);
    const [selecionados, setSelecionados] = useState([]);
    const [carregando, setCarregando] = useState(Boolean(idBarbearia));
    const [erro, setErro] = useState('');
    const [modalServicosAberto, setModalServicosAberto] = useState(false);

    useEffect(() => {
        if (!idBarbearia) return;
        apiFetch(`/barbearia/servicos?id_usuario=${encodeURIComponent(idBarbearia)}`)
            .then((dados) => setServicos(dados.servicos || []))
            .catch((error) => setErro(mensagemDaApi(error)))
            .finally(() => setCarregando(false));
    }, [idBarbearia]);

    const alternar = (idServico) => setSelecionados((atuais) =>
        atuais.includes(idServico)
            ? atuais.filter((id) => id !== idServico)
            : [...atuais, idServico]
    );

    const continuar = () => {
        if (!selecionados.length) { setErro('Selecione pelo menos um serviço para continuar.'); return; }
        
        // Verifica se é APENAS "pintar cabelo" (sem corte, barba, nem outros tratamentos)
        const servicosSelecionados = servicos.filter(s => selecionados.includes(s.id_servico));
        const nomes = servicosSelecionados.map(s => s.nome.toLowerCase()).join(' ');
        
        const temPintar = nomes.includes('pintar') || nomes.includes('color') || nomes.includes('tinta');
        const temCorte = nomes.includes('corte') || nomes.includes('pezinho') || nomes.includes('degrade');
        const temBarba = nomes.includes('barba') || nomes.includes('bigode');
        const temTratamento = nomes.includes('progressiva') || nomes.includes('alisamento') || 
                             nomes.includes('mega hair') || nomes.includes('mega-hair') || nomes.includes('mega') ||
                             nomes.includes('hidratacao') || nomes.includes('cauterizacao') || 
                             nomes.includes('botox') || nomes.includes('reconstrucao') || 
                             nomes.includes('selagem') || nomes.includes('escova');
        
        // Só pintar cabelo = tem pintar mas NÃO tem corte, barba, nem outros tratamentos
        const soPintarCabelo = temPintar && !temCorte && !temBarba && !temTratamento;

        // Alvo da coloração: cabelo e/ou barba, conforme o nome dos serviços.
        const temPintarCabelo = temPintar && nomes.includes('cabelo');
        const temPintarBarba = temPintar && temBarba;
        
        const params = new URLSearchParams({
            barbearia: idBarbearia,
            servicos: selecionados.join(',')
        });
        if (idFuncionario) params.set('funcionario', idFuncionario);
        if (soPintarCabelo) {
            params.set('pular_analise', 'true');
        }
        // Passar se tem pintar cabelo para mostrar opção de cor
        if (temPintar) {
            params.set('tem_pintar', 'true');
        }
        // Alvo da tinta: só aparece a cor do que foi contratado.
        // Pintura genérica (sem "cabelo"/"barba" no nome) assume cabelo.
        if (temPintarCabelo || (!temPintarBarba && temPintar)) {
            params.set('pintar_cabelo', 'true');
        }
        if (temPintarBarba) {
            params.set('pintar_barba', 'true');
        }
        
        navigate(`/visagismo?${params.toString()}`);
    };

    return <main className={styles.pagina}>
        <section className={styles.cartao}>
            <button type="button" className={styles.voltar} onClick={() => navigate(-1)}><FiArrowLeft /> Voltar</button>
            <p className={styles.eyebrow}>AGENDAMENTO</p>
            <h1>Selecione os serviços</h1>
            <p className={styles.subtitulo}>Escolha tudo o que deseja fazer nesta visita. O tempo total será considerado ao buscar horários.</p>
            {erro && <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />}
            {carregando ? <p>Carregando serviços…</p> : <div className={styles.lista}>
                {servicos.slice(0, 5).map((servico) => {
                    const ativo = selecionados.includes(servico.id_servico);
                    return <button type="button" key={servico.id_servico} onClick={() => alternar(servico.id_servico)}
                        className={`${styles.servico} ${ativo ? styles.ativo : ''}`} aria-pressed={ativo}>
                        <FiScissors /><span><strong>{servico.nome}</strong><small>{servico.duracao ? `${servico.duracao} min` : '--'} · R$ {Number(servico.preco || 0).toFixed(2).replace('.', ',')}</small></span>
                        <b>{ativo ? '✓' : '+'}</b>
                    </button>;
                })}
                {servicos.length > 5 && <button type="button" className={styles.verMais} onClick={() => setModalServicosAberto(true)}>Ver mais {servicos.length - 5} serviço(s)</button>}
                {!servicos.length && <p>Esta barbearia ainda não cadastrou serviços.</p>}
            </div>}
            <button type="button" className={styles.continuar} disabled={!selecionados.length || carregando} onClick={continuar}>CONTINUAR</button>
        </section>
        {modalServicosAberto && (
            <div className={styles.modalOverlay} onClick={() => setModalServicosAberto(false)}>
                <div className={styles.modalServicos} onClick={(e) => e.stopPropagation()}>
                    <div className={styles.modalServicosHeader}>
                        <h3>Todos os serviços</h3>
                        <button type="button" onClick={() => setModalServicosAberto(false)} aria-label="Fechar">×</button>
                    </div>
                    <div className={styles.modalServicosLista}>
                        {servicos.map((servico) => {
                            const ativo = selecionados.includes(servico.id_servico);
                            return (
                                <button type="button" key={servico.id_servico} onClick={() => alternar(servico.id_servico)}
                                    className={`${styles.modalServicoItem} ${ativo ? styles.ativo : ''}`}>
                                    <FiScissors /><span><strong>{servico.nome}</strong><small>{servico.duracao ? `${servico.duracao} min` : '--'} · R$ {Number(servico.preco || 0).toFixed(2).replace('.', ',')}</small></span>
                                    <b>{ativo ? '✓' : '+'}</b>
                                </button>
                            );
                        })}
                    </div>
                </div>
            </div>
        )}
    </main>;
}

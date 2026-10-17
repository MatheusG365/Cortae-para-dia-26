import { barbeariasDaResposta } from '../../services/cadastroState';
import { useEffect, useState } from 'react';
import { LuSearch, LuMapPin, LuClock } from 'react-icons/lu';
import { IMaskInput } from 'react-imask';
import { useNavigate } from 'react-router-dom';
import styles from './BarbeariasDisponiveis.module.css';
import { apiFetch, urlDaApi, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';

export default function Barbearias() {
    const navigate = useNavigate();
    const [busca, setBusca] = useState('');
    const [barbearias, setBarbearias] = useState([]);
    const [carregando, setCarregando] = useState(true);
    const [erro, setErro] = useState('');

    useEffect(() => {
        async function carregarBarbearias() {
            try {
                setCarregando(true);
                setErro('');

                const dados = await apiFetch('/barbearias-disponiveis');
                setBarbearias(barbeariasDaResposta(dados));
            } catch (error) {
                setErro(mensagemDaApi(error));
                setBarbearias([]);
            } finally {
                setCarregando(false);
            }
        }

        carregarBarbearias();
    }, []);

    const barbeariasFiltradas = barbearias.filter((barbearia) =>
        String(barbearia.nome || '').toLowerCase().includes(busca.toLowerCase())
    );

    return (
        <div className={styles.container}>
            <main className={styles.main}>
                <div className={styles.headerBusca}>
                    <div className={styles.titulos}>
                        <h1 className={styles.titulo}>
                            Barbearias <span className={styles.destaque}>Disponíveis</span>
                        </h1>
                        <p className={styles.subtitulo}>
                            Encontre os melhores profissionais para o seu próximo estilo.
                        </p>
                    </div>

                    <div className={styles.caixaBusca}>
                        <LuSearch className={styles.iconeBusca} size={18} />
                        <IMaskInput
                            mask={/^[\s\S]*$/}
                            type="text"
                            aria-label="Buscar barbearia por nome"
                            placeholder="Ex: nome da barbearia"
                            value={busca}
                            onAccept={(value) => setBusca(value)}
                            className={styles.inputBusca}
                        />
                    </div>
                </div>

                {carregando && (
                    <p>Carregando barbearias...</p>
                )}

                {!carregando && erro && (
                    <MensagemCard mensagem={{ informacao: erro, tipo: 'erro' }} fechar={() => setErro('')} />
                )}

                {!carregando && !erro && barbeariasFiltradas.length === 0 && (
                    <p>Nenhuma barbearia personalizada encontrada.</p>
                )}

                {!carregando && !erro && barbeariasFiltradas.length > 0 && (
                    <div className={styles.grid}>
                        {barbeariasFiltradas.map((barbearia) => (
                            <article
                                key={barbearia.id}
                                className={styles.card}
                                style={
                                    barbearia.imagem
                                        ? {
                                            backgroundImage: `url("${urlDaApi(barbearia.imagem)}")`,
                                            backgroundSize: 'contain',
                                            backgroundPosition: 'center',
                                            backgroundRepeat: 'no-repeat',
                                            backgroundColor: '#fff'
                                        }
                                        : undefined
                                }
                            >
                                <div className={styles.cardOverlay}>
                                    <span className={styles.badgeDias}>{barbearia.dias}</span>

                                    <div className={styles.cardConteudo}>
                                        <h3 className={styles.cardNome}>{barbearia.nome}</h3>

                                        <div className={styles.infoLinha}>
                                            <LuMapPin className={styles.infoIcone} size={14} />
                                            <span>{barbearia.endereco || 'Endereço não informado'}</span>
                                        </div>

                                        <div className={styles.infoLinha}>
                                            <LuClock className={styles.infoIcone} size={14} />
                                            <span>
                                                Horário de Atendimento: {barbearia.horario || 'Não informado'}
                                            </span>
                                        </div>

                                        <button
                                            type="button"
                                            className={styles.btnAgendar}
                                            disabled={!barbearia.personalizada}
                                            onClick={() => navigate(`/estabelecimento?usuario=${barbearia.id}`)}
                                        >
                                            {barbearia.personalizada ? 'Ver estabelecimento' : 'Em configuração'}
                                        </button>
                                    </div>
                                </div>
                            </article>
                        ))}
                    </div>
                )}
            </main>
        </div>
    );
}


import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiFetch, mensagemDaApi } from '../../services/api';
import styles from './ListaEspera.module.css';

const rotulos = { aguardando: 'Aguardando disponibilidade', aviso_pendente: 'Horário liberado; envio do aviso pendente', aviso_falhou: 'Falha ao enviar o aviso por e-mail; consulte os horários', notificada: 'Aviso enviado por e-mail', cancelada: 'Inscrição cancelada' };

export default function ListaEspera() {
    const [entradas, setEntradas] = useState([]);
    const [carregando, setCarregando] = useState(true);
    const [erro, setErro] = useState('');
    const [processando, setProcessando] = useState(null);
    useEffect(() => {
        let ativo = true;
        apiFetch('/agendamentos/lista-espera').then((dados) => {
            if (ativo) setEntradas(dados.lista_espera || dados.entradas || []);
        }).catch((falha) => { if (ativo) setErro(mensagemDaApi(falha)); })
            .finally(() => { if (ativo) setCarregando(false); });
        return () => { ativo = false; };
    }, []);
    const sair = async (entrada) => {
        if (processando) return;
        const id = entrada.id_lista_espera || entrada.id;
        setProcessando(id); setErro('');
        try {
            await apiFetch(`/agendamentos/lista-espera/${id}`, { method: 'DELETE' });
            setEntradas((lista) => lista.filter((item) => (item.id_lista_espera || item.id) !== id));
        } catch (falha) { setErro(mensagemDaApi(falha)); }
        finally { setProcessando(null); }
    };
    return <section className={styles.secao} aria-label="Minha lista de espera">
        <h2>Minha lista de espera</h2>
        <p>Você recebe um e-mail quando o horário é liberado. O aviso não faz uma reserva; confirme um agendamento disponível.</p>
        {carregando && <p role="status">Consultando lista de espera…</p>}
        {erro && <p role="alert" className={styles.erro}>{erro}</p>}
        {!carregando && !erro && !entradas.length && <p>Você não está aguardando nenhum horário.</p>}
        <div className={styles.lista}>{entradas.map((entrada) => {
            const id = entrada.id_lista_espera || entrada.id;
            const data = entrada.data || String(entrada.inicio_em || '').split(/[T ]/)[0];
            const hora = entrada.horario || String(entrada.inicio_em || '').split(/[T ]/)[1]?.slice(0, 5);
            const servicos = entrada.ids_servicos || entrada.servicos || [];
            const destino = new URLSearchParams({ barbearia: entrada.id_barbearia, servicos: Array.isArray(servicos) ? servicos.join(',') : servicos });
            if (entrada.id_corte) destino.set('corte', entrada.id_corte);
            if (entrada.id_visagismo) destino.set('visagismo', entrada.id_visagismo);
            if (entrada.id_funcionario) destino.set('funcionario', entrada.id_funcionario);
            if (data) destino.set('data', data);
            return <article key={id}><h3>{entrada.barbearia_nome || `Barbearia #${entrada.id_barbearia}`}</h3>
                <p>{data?.split('-').reverse().join('/')} · {hora} {entrada.funcionario_nome ? `· ${entrada.funcionario_nome}` : ''}</p>
                <p><strong>{rotulos[entrada.status] || entrada.status}</strong></p>
                {['notificada', 'aviso_pendente', 'aviso_falhou'].includes(entrada.status) && <Link to={`/agendamento?${destino.toString()}`}>Consultar horários disponíveis</Link>}
                {entrada.status !== 'cancelada' && <button type="button" disabled={Boolean(processando)} onClick={() => sair(entrada)}>{processando === id ? 'Saindo…' : 'Sair da lista de espera'}</button>}
            </article>;
        })}</div>
    </section>;
}

import Select from '../../components/Select/Select';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight, BadgePercent, CalendarClock, Check, Clock3, Copy, Link2, Plus, Scissors, Settings2, Trash2, UsersRound, X } from 'lucide-react';
import { mensagemDaApi } from '../../services/api';
import { dataLocal } from '../../services/agendaState';
import { dinheiro, linkAgendamento } from '../../services/gestaoState';

const dias = [['segunda', 'Segunda-feira'], ['terca', 'Terça-feira'], ['quarta', 'Quarta-feira'], ['quinta', 'Quinta-feira'], ['sexta', 'Sexta-feira'], ['sabado', 'Sábado'], ['domingo', 'Domingo']];
const iniciais = (nome) => String(nome || '?').trim().split(/\s+/).slice(0, 2).map((parte) => parte.charAt(0)).join('').toUpperCase();

function Compartilhar({ styles, url, contexto }) {
    const [enderecoAberto, setEnderecoAberto] = useState(false);
    const [mensagem, setMensagem] = useState(''); const [falhou, setFalhou] = useState(false);
    const copiar = async () => {
        setMensagem(''); setFalhou(false);
        try { await navigator.clipboard.writeText(url); setMensagem('Link copiado.'); }
        catch { setEnderecoAberto(true); setFalhou(true); setMensagem('Selecione o endereço abaixo e copie para compartilhar.'); }
    };
    return <div className={styles.equipeCompartilhar}>
        <div className={styles.equipeLinks}>
            <a href={url} className={styles.equipeLink} aria-label={`Abrir agendamento de ${contexto}`}><ArrowUpRight size={17} aria-hidden="true" />Abrir agendamento</a>
            <button type="button" className={styles.equipeBotaoLeve} onClick={copiar} aria-label={`Copiar link de agendamento de ${contexto}`}><Copy size={16} aria-hidden="true" />Copiar link</button>
            <button type="button" className={styles.equipeBotaoLeve} aria-expanded={enderecoAberto} onClick={() => setEnderecoAberto((atual) => !atual)}><Link2 size={16} aria-hidden="true" />{enderecoAberto ? 'Ocultar endereço' : 'Ver endereço'}</button>
        </div>
        {enderecoAberto && <label className={styles.equipeEndereco}>Endereço de agendamento de {contexto}<input readOnly value={url} onFocus={(e) => e.currentTarget.select()} /></label>}
        {mensagem && <p className={styles.equipeFeedback} role={falhou ? 'alert' : 'status'}>{!falhou && <Check size={16} aria-hidden="true" />}{mensagem}</p>}
    </div>;
}

function Profissional({ funcionario, servicos, requisicao, styles, idSalao }) {
    const [config, setConfig] = useState(null); const [configAberta, setConfigAberta] = useState(false);
    const [erro, setErro] = useState(''); const [sucesso, setSucesso] = useState('');
    const [salvando, setSalvando] = useState(false); const [abrindo, setAbrindo] = useState(false);
    const abrir = async () => {
        if (configAberta) { setConfigAberta(false); return; }
        if (config) { setConfigAberta(true); return; }
        setErro(''); setAbrindo(true);
        try { const dados = await requisicao(`/profissionais/${funcionario.id_funcionario}/config`); setConfig({ ...dados, horarios: dados.horarios || [], precos: dados.precos || [] }); setConfigAberta(true); }
        catch (e) { setErro(mensagemDaApi(e)); } finally { setAbrindo(false); }
    };
    const salvar = async (e) => {
        e.preventDefault(); setErro(''); setSucesso(''); setSalvando(true);
        try { await requisicao(`/profissionais/${funcionario.id_funcionario}/config`, { method: 'PUT', body: JSON.stringify(config) }); setSucesso('Configuração salva. Atendimentos anteriores mantêm sua comissão registrada.'); }
        catch (e) { setErro(mensagemDaApi(e)); } finally { setSalvando(false); }
    };
    const alterarHorario = (indice, campo, valor) => setConfig((atual) => ({ ...atual, horarios: atual.horarios.map((item, i) => i === indice ? { ...item, [campo]: valor } : item) }));
    const preco = (id) => config.precos.find((p) => Number(p.id_servico) === Number(id))?.preco ?? '';
    const alterarPreco = (id, valor) => setConfig((atual) => ({ ...atual, precos: [...atual.precos.filter((p) => Number(p.id_servico) !== Number(id)), ...(valor === '' ? [] : [{ id_servico: id, preco: Number(valor) }])] }));
    const vinculados = servicos.filter((s) => (config?.ids_servicos_vinculados || []).some((id) => Number(id) === Number(s.id_servico)));
    return <article className={styles.equipeProfissional}>
        <header className={styles.equipeProfissionalTopo}>
            <div className={styles.equipeIdentidade}><span className={styles.equipeAvatar} aria-hidden="true">{iniciais(funcionario.nome)}</span><div><div className={styles.equipeNomeLinha}><h3>{funcionario.nome}</h3><span className={`${styles.equipeStatus} ${funcionario.ativo === false ? styles.equipeStatusInativo : ''}`}>{funcionario.ativo === false ? 'Inativo' : 'Ativo'}</span></div><p>Agenda, preços e comissão</p></div></div>
            <div className={styles.equipeProfissionalAcoes}><button type="button" className={styles.equipeBotaoPrimario} onClick={abrir} disabled={abrindo || salvando} aria-expanded={configAberta}>{configAberta ? <X size={17} aria-hidden="true" /> : <Settings2 size={17} aria-hidden="true" />}{abrindo ? 'Carregando…' : configAberta ? 'Fechar configuração' : 'Configurar profissional'}</button></div>
        </header>
        <div className={styles.equipeProfissionalLinks}><span className={styles.equipeFaixaLegenda}><Link2 size={16} aria-hidden="true" />Agendamento deste profissional</span><Compartilhar styles={styles} contexto={funcionario.nome} url={linkAgendamento(window.location.origin, idSalao, funcionario.id_funcionario)} /></div>
        {erro && <p role="alert" className={styles.erro}>{erro}</p>}{sucesso && <p role="status" className={styles.sucesso}>{sucesso}</p>}
        {config && configAberta && <form className={styles.equipeConfiguracao} onSubmit={salvar}>
            <section className={styles.equipeConfigSecao}><header className={styles.equipeConfigTitulo}><BadgePercent size={20} aria-hidden="true" /><div><h4>Comissão por atendimento</h4><p>Escolha o modelo de remuneração deste profissional.</p></div></header><div className={styles.equipeCampos}>
                <label>Tipo de comissão<Select value={config.comissao_tipo || 'percentual'} onChange={(e) => setConfig({ ...config, comissao_tipo: e.target.value })}><option value="percentual">Percentual por atendimento</option><option value="fixa">Valor fixo por atendimento</option></Select></label>
                <label>{config.comissao_tipo === 'fixa' ? 'Valor fixo (R$)' : 'Percentual (%)'}<input type="number" step="0.01" min="0" max={config.comissao_tipo === 'fixa' ? '1000000' : '100'} required value={config.comissao_valor ?? 0} onChange={(e) => setConfig({ ...config, comissao_valor: Number(e.target.value) })} /></label>
            </div></section>
            <section className={styles.equipeConfigSecao}><header className={styles.equipeConfigTitulo}><CalendarClock size={20} aria-hidden="true" /><div><h4>Turnos e intervalos</h4><p>Cadastre períodos separados para reservar o intervalo, dentro do expediente do salão. Sem turnos salvos, o profissional fica indisponível para novas reservas.</p></div></header>
                <div className={styles.equipeTurnos}>{config.horarios.map((h, i) => <div className={styles.equipeTurno} key={i}><label className={styles.equipeTurnoDia}>Dia<Select value={h.dia} onChange={(e) => alterarHorario(i, 'dia', e.target.value)}>{dias.map(([valor, nome]) => <option key={valor} value={valor}>{nome}</option>)}</Select></label><label>Entrada<input required type="time" value={h.inicio} onChange={(e) => alterarHorario(i, 'inicio', e.target.value)} /></label><label>Saída<input required type="time" value={h.fim} onChange={(e) => alterarHorario(i, 'fim', e.target.value)} /></label><button type="button" className={styles.equipeBotaoLeve} onClick={() => setConfig({ ...config, horarios: config.horarios.filter((_, index) => index !== i) })} aria-label={`Remover turno ${i + 1} de ${funcionario.nome}`}><Trash2 size={16} aria-hidden="true" />Remover</button></div>)}</div>
                {!config.horarios.length && <p className={styles.equipeVazio}>Nenhum turno cadastrado.</p>}<button type="button" className={styles.equipeBotaoSecundario} onClick={() => setConfig({ ...config, horarios: [...config.horarios, { dia: 'segunda', inicio: '08:00', fim: '12:00' }] })}><Plus size={17} aria-hidden="true" />Adicionar turno</button>
            </section>
            <section className={styles.equipeConfigSecao}><header className={styles.equipeConfigTitulo}><Scissors size={20} aria-hidden="true" /><div><h4>Preços por serviço</h4><p>Campo vazio usa o preço padrão. Apenas os serviços vinculados ao profissional aparecem aqui.</p></div></header><div className={styles.equipePrecos}>{vinculados.map((s) => <label className={styles.equipePrecoCampo} key={s.id_servico}><span>{s.nome}</span><small>Padrão do salão: {dinheiro(s.preco)}</small><input aria-label={`Preço de ${s.nome} para ${funcionario.nome}`} type="number" min="0.01" max="1000000" step="0.01" placeholder="Usar preço padrão" value={preco(s.id_servico)} onChange={(e) => alterarPreco(s.id_servico, e.target.value)} /></label>)}</div>{!vinculados.length && <p className={styles.equipeVazio}>Este profissional ainda não tem serviços vinculados. Ajuste o cadastro em Editar barbearia.</p>}</section>
            <footer className={styles.equipeSalvar}><span>Alterações valem para os próximos atendimentos.</span><button type="submit" className={styles.equipeBotaoPrimario} disabled={salvando}><Check size={17} aria-hidden="true" />{salvando ? 'Salvando…' : 'Salvar profissional'}</button></footer>
        </form>}
    </article>;
}

export default function EquipeGestao({ requisicao, styles, idSalao, tipo }) {
    const [dados, setDados] = useState(null); const [erro, setErro] = useState(''); const [sucesso, setSucesso] = useState(''); const [atualizando, setAtualizando] = useState(null);
    const carregar = useCallback(async () => { try { setDados(await requisicao('/agenda', {}, { inicio: dataLocal(), fim: dataLocal() })); } catch (e) { setErro(mensagemDaApi(e)); } }, [requisicao]);
    useEffect(() => { queueMicrotask(carregar); }, [carregar]);
    const servicos = dados?.servicos || []; const profissionais = dados?.funcionarios || [];
    const ativos = servicos.filter((s) => s.ativo !== false).length;
    const alternarServico = async (s) => {
        setErro(''); setSucesso(''); setAtualizando(s.id_servico);
        try { await requisicao(`/servicos/${s.id_servico}/ativo`, { method: 'PUT', body: JSON.stringify({ ativo: s.ativo === false }) }); await carregar(); setSucesso('Status do serviço atualizado.'); }
        catch (e) { setErro(mensagemDaApi(e)); } finally { setAtualizando(null); }
    };
    return <div className={styles.equipePagina}>
        <header className={styles.equipeCabecalho}>
            <div className={styles.equipeTituloLinha}><div><p className={styles.equipeEyebrow}>SEU ESTABELECIMENTO</p><h2>Equipe, serviços e links</h2><p>Organize o catálogo e os profissionais do seu salão.</p></div><Link className={styles.equipeBotaoPrimario} to={`/editarbarbearia${tipo === 0 ? `?usuario=${idSalao}` : ''}`}><Settings2 size={18} aria-hidden="true" />Editar cadastro e serviços</Link></div>
            {dados && <div className={styles.equipeResumo} aria-label="Resumo da equipe e serviços"><article><Scissors size={19} aria-hidden="true" /><div><strong>{ativos}</strong><span>Serviços ativos</span></div></article><article><UsersRound size={19} aria-hidden="true" /><div><strong>{profissionais.filter((p) => p.ativo !== false).length}</strong><span>Profissionais ativos</span></div></article><article><CalendarClock size={19} aria-hidden="true" /><div><strong>{servicos.length - ativos}</strong><span>Serviços inativos</span></div></article></div>}
        </header>
        {erro && <p role="alert" className={styles.erro}>{erro}</p>}{sucesso && <p role="status" className={styles.sucesso}>{sucesso}</p>}{!dados && !erro && <p role="status">Carregando equipe e serviços…</p>}
        <div className={styles.equipeLayout}>
            <div className={styles.equipePrincipal}>
                <section className={styles.equipeSecao}>
                    <header className={styles.equipeSecaoTitulo}><div><h3>Serviços do salão</h3><p>Ative ou pause serviços preservando o histórico.</p></div>{dados && <span className={styles.equipeContagem}>{servicos.length} cadastrado{servicos.length === 1 ? '' : 's'}</span>}</header>
                    <div className={styles.equipeServicos}>{servicos.map((s) => <article className={styles.equipeServico} key={s.id_servico}>
                        <div className={styles.equipeServicoTopo}><h4>{s.nome}</h4><span className={`${styles.equipeStatus} ${s.ativo === false ? styles.equipeStatusInativo : ''}`}>{s.ativo === false ? 'Inativo' : 'Ativo'}</span></div>
                        <dl className={styles.equipeServicoInfo}><div><dt>Preço padrão</dt><dd>{dinheiro(s.preco)}</dd></div><div><dt>Duração</dt><dd><Clock3 size={16} aria-hidden="true" />{s.duracao} min</dd></div></dl>
                        <footer className={styles.equipeServicoRodape}><button type="button" className={styles.equipeBotaoSecundario} disabled={atualizando !== null} onClick={() => alternarServico(s)}>{atualizando === s.id_servico ? 'Atualizando…' : s.ativo === false ? 'Ativar serviço' : 'Desativar serviço'}</button></footer>
                    </article>)}</div>
                    {dados && !servicos.length && <p className={styles.equipeVazio}>Nenhum serviço cadastrado. Adicione o primeiro em Editar cadastro e serviços.</p>}
                </section>
                <section className={styles.equipeSecao}>
                    <header className={styles.equipeSecaoTitulo}><div><h3>Profissionais</h3><p>Configure comissão, turnos e preços de cada profissional.</p></div>{dados && <span className={styles.equipeContagem}>{profissionais.length} na equipe</span>}</header>
                    <div className={styles.equipeProfissionais}>{profissionais.map((f) => <Profissional key={f.id_funcionario} funcionario={f} servicos={servicos} requisicao={requisicao} styles={styles} idSalao={idSalao} />)}</div>
                    {dados && !profissionais.length && <p className={styles.equipeVazio}>Sua equipe ainda não tem profissionais cadastrados.</p>}
                </section>
            </div>
            <aside className={styles.equipeLateral} aria-label="Compartilhamento do salão">
                <section className={styles.equipeLinkSalao}><div className={styles.equipeLinkTitulo}><span className={styles.equipeIcone}><Link2 size={20} aria-hidden="true" /></span><div><h3>Agendamento do salão</h3><p>Um link direto para compartilhar com seus clientes.</p></div></div><Compartilhar styles={styles} contexto="seu salão" url={linkAgendamento(window.location.origin, idSalao)} /></section>
            </aside>
        </div>
    </div>;
}

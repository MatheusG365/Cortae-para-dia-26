import { useEffect, useMemo, useState } from 'react';
import { Image as ImageIcon, Plus, Scissors, Trash2, Upload, Users, Pencil, CreditCard, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { urlDaApi, apiFetch, mensagemDaApi } from '../../services/api';
import MensagemCard from '../../components/MensagemCard/MensagemCard';
import ModalAdicionarServico from '../../components/ModalAdicionarServico/ModalAdicionarServico';
import ModalConfirmacao from '../../components/ModalConfirmacao/ModalConfirmacao';
import SeletorIdentidadeVisual from '../../components/SeletorIdentidadeVisual/SeletorIdentidadeVisual';
import TabelaHorarios from '../../components/TabelaHorarios/TabelaHorarios';
import MaskedInput from '../../components/MaskedInput/MaskedInput';
import styles from './PersonalizacaoBarbearia.module.css';
import { anexarFuncionario, erroFuncionario } from '../../services/agendaState';
import { useAuth } from '../../contexts/useAuth';

const DIAS = [['segunda', 'Segunda'], ['terca', 'Terça'], ['quarta', 'Quarta'], ['quinta', 'Quinta'], ['sexta', 'Sexta'], ['sabado', 'Sábado'], ['domingo', 'Domingo']];
const criarDias = () => DIAS.map(([chave, nome]) => ({ chave, nome, fechado: true, manhaInicio: '08:00', manhaFim: '12:00', tardeInicio: '14:00', tardeFim: '18:00' }));
const novoFuncionario = () => ({ id: crypto.randomUUID(), id_funcionario: null, nome: '', descricao: '', email: '', telefone: '', comissao_percentual: 0, dias: [], servicos: [] });
const CORES_INICIAIS = { primaria: '#FF9C08', secundaria: '#000000', terciaria: '#FFFFFF', textoPrimario: '#000000', textoSecundario: '#FFFFFF' };
const normalizarHora = (valor) => valor ? String(valor).slice(0, 5) : '';

export default function PersonalizacaoBarbearia({ modoEdicao = false }) {
    const { usuario } = useAuth();
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const idUsuarioAlvo = searchParams.get('usuario');
    const sufixoUsuario = idUsuarioAlvo ? `?id_usuario=${encodeURIComponent(idUsuarioAlvo)}` : '';
    const [historia, setHistoria] = useState('');
    const [localizacao, setLocalizacao] = useState('');
    const [contatos, setContatos] = useState({ telefone: '', email: '', instagram: '' });
    const [chavePix, setChavePix] = useState('');
    const [arkheClientId, setArkheClientId] = useState('');
    const [arkheClientSecret, setArkheClientSecret] = useState('');
    const [mostrarSecret, setMostrarSecret] = useState(false);
    const [cores, setCores] = useState(CORES_INICIAIS);
    const [dias, setDias] = useState(criarDias);
    const [funcionarios, setFuncionarios] = useState([novoFuncionario()]);
    const [servicos, setServicos] = useState([]);
    const [logo, setLogo] = useState(null);
    const [fotos, setFotos] = useState([]);
    const [previewLogo, setPreviewLogo] = useState(null);
    const [previewsFotos, setPreviewsFotos] = useState([]);
    const [modalAberto, setModalAberto] = useState(false);
    const [servicoEditando, setServicoEditando] = useState(null);
    const [carregando, setCarregando] = useState(true);
    const [salvando, setSalvando] = useState(false);
    const [convites, setConvites] = useState([]);
    const [personalizacaoSalva, setPersonalizacaoSalva] = useState(false);
    const [linkCopiado, setLinkCopiado] = useState('');
    const [mensagem, setMensagem] = useState(null);
    const [modalServicosAberto, setModalServicosAberto] = useState(false);
    const [servicoRemovendo, setServicoRemovendo] = useState(null);
    const [removendo, setRemovendo] = useState(false);
    const [servicoFuncionarioAberto, setServicoFuncionarioAberto] = useState(null);
    const diasAbertos = useMemo(() => dias.filter((dia) => !dia.fechado), [dias]);

    useEffect(() => {
        async function carregar() {
            try {
                const [dados, dadosServicos] = await Promise.all([apiFetch(`/barbearia/personalizacao${sufixoUsuario}`), apiFetch(`/barbearia/servicos${sufixoUsuario}`)]);
                setServicos(dadosServicos.servicos || []);
                if (!dados.personalizado) {
                    // Ao ADM abrir uma barbearia ainda sem personalização, o
                    // ID alvo precisa sobreviver à troca para a tela de criação.
                    if (modoEdicao) navigate(`/personalizacaobarbearia${sufixoUsuario}`, { replace: true });
                    return;
                }
                const personalizacao = dados.personalizacao;
                setHistoria(personalizacao.historia || '');
                setLocalizacao(personalizacao.localizacao || '');
                setCores({
                    primaria: personalizacao.cor_primaria || CORES_INICIAIS.primaria,
                    secundaria: personalizacao.cor_secundaria || CORES_INICIAIS.secundaria,
                    terciaria: personalizacao.cor_terciaria || CORES_INICIAIS.terciaria,
                    textoPrimario: personalizacao.cor_texto_primario || CORES_INICIAIS.textoPrimario,
                    textoSecundario: personalizacao.cor_texto_secundario || CORES_INICIAIS.textoSecundario,
                });
                setContatos({ telefone: personalizacao.contato_telefone || '', email: personalizacao.contato_email || '', instagram: personalizacao.instagram || '' });
                setChavePix(personalizacao.chave_pix || '');
                setArkheClientId(personalizacao.arkhe_client_id || '');
                setArkheClientSecret(personalizacao.arkhe_client_secret || '');
                setLogo(dados.logo || null);
                setFotos(dados.fotos || []);
                setPreviewLogo(dados.logo ? urlDaApi(dados.logo) : null);
                setPreviewsFotos((dados.fotos || []).map((foto) => urlDaApi(foto.url)));
                const diasComChave = (dados.dias_servico || []).map((dia, indice) => ({ ...dia, chave: dia.dia || DIAS[indice]?.[0] }));
                const diasDaApi = new Map(diasComChave.map((dia) => [dia.chave, dia]));
                setDias(criarDias().map((dia) => {
                    const salvo = diasDaApi.get(dia.chave);
                    return salvo ? { ...dia, fechado: false, manhaInicio: normalizarHora(salvo.entrada_manha), manhaFim: normalizarHora(salvo.saida_manha), tardeInicio: normalizarHora(salvo.entrada_tarde), tardeFim: normalizarHora(salvo.saida_tarde) } : dia;
                }));
                const equipe = (dados.funcionarios || []).map((funcionario) => ({ ...funcionario, id: funcionario.id_funcionario, id_funcionario: funcionario.id_funcionario, nome: funcionario.nome || '', descricao: funcionario.descricao || '', email: funcionario.email || '', telefone: funcionario.telefone || '', comissao_percentual: funcionario.comissao_percentual ?? 0, dias: (funcionario.dias || [funcionario.id_dias]).map((idDia) => diasComChave.find((dia) => dia.id_dia === idDia)?.chave).filter(Boolean), servicos: funcionario.servicos || [] }));
                setFuncionarios(equipe.length ? equipe : [novoFuncionario()]);
                if (!modoEdicao) navigate(`/editarbarbearia${sufixoUsuario}`, { replace: true });
            } catch (erro) {
                if (erro.status !== 401) setMensagem({ informacao: mensagemDaApi(erro), tipo: 'erro' });
            } finally { setCarregando(false); }
        }
        carregar();
    }, [modoEdicao, navigate, sufixoUsuario]);

    const atualizarFuncionario = (indice, campo, valor) => setFuncionarios((lista) => lista.map((funcionario, i) => i === indice ? { ...funcionario, [campo]: valor } : funcionario));
    const reenviarConvite = async (funcionario) => {
        if (salvando) return;
        setSalvando(true);
        try {
            const idBarbearia = idUsuarioAlvo || usuario?.id_usuario;
            const resposta = await apiFetch(`/barbearias/${idBarbearia}/funcionarios/${funcionario.id_funcionario}/convite`, { method: 'POST' });
            setConvites(resposta.convites || []);
            setMensagem(resposta.mensagem);
        } catch (falha) { setMensagem({ informacao: mensagemDaApi(falha), tipo: 'erro' }); }
        finally { setSalvando(false); }
    };
    const alternarServicoFuncionario = (indice, idServico) => setFuncionarios((lista) => lista.map((funcionario, i) => i === indice ? { ...funcionario, servicos: funcionario.servicos.includes(idServico) ? funcionario.servicos.filter((id) => id !== idServico) : [...funcionario.servicos, idServico] } : funcionario));
    const alternarDiaFuncionario = (indice, chaveDia) => setFuncionarios((lista) => lista.map((funcionario, i) => i === indice ? { ...funcionario, dias: funcionario.dias.includes(chaveDia) ? funcionario.dias.filter((dia) => dia !== chaveDia) : [...funcionario.dias, chaveDia] } : funcionario));

    async function salvarServico(servico) {
        try {
            const editando = Boolean(servicoEditando);
            const endpoint = editando
                ? `/barbearia/servicos/${servicoEditando.id_servico}${sufixoUsuario}`
                : `/barbearia/servicos${sufixoUsuario}`;

            const resposta = await apiFetch(
                endpoint,
                {
                    method: editando ? 'PUT' : 'POST',
                    body: JSON.stringify(servico)
                }
            );

            if (editando) {
                setServicos((lista) => lista.map((item) =>
                    item.id_servico === servicoEditando.id_servico
                        ? resposta.servico
                        : item
                ));
            } else {
                setServicos((lista) => [...lista, resposta.servico]);
            }

            setServicoEditando(null);
            setModalAberto(false);
            setMensagem(resposta.mensagem);
        } catch (erro) {
            setMensagem({
                informacao: mensagemDaApi(erro),
                tipo: 'erro'
            });
        }
    }

    function abrirAdicionarServico() {
        setServicoEditando(null);
        setModalAberto(true);
    }

    function abrirEditarServico(servico) {
        setServicoEditando(servico);
        setModalAberto(true);
    }

    function removerServico(servico) {
        // Abre o modal de confirmação (substitui o window.confirm nativo)
        setServicoRemovendo(servico);
    }

    async function confirmarRemocaoServico() {
        if (!servicoRemovendo) return;
        setRemovendo(true);
        try {
            const resposta = await apiFetch(`/barbearia/servicos/${servicoRemovendo.id_servico}${sufixoUsuario}`, { method: 'DELETE' });
            setServicos((lista) => lista.filter((item) => item.id_servico !== servicoRemovendo.id_servico));
            setFuncionarios((lista) => lista.map((funcionario) => ({ ...funcionario, servicos: funcionario.servicos.filter((id) => id !== servicoRemovendo.id_servico) })));
            setMensagem(resposta.mensagem);
            setServicoRemovendo(null);
        } catch (erro) { setMensagem({ informacao: mensagemDaApi(erro), tipo: 'erro' }); }
        finally { setRemovendo(false); }
    }

    function montarFormulario() {
        const formulario = new FormData();
        if (idUsuarioAlvo) formulario.append('id_usuario', idUsuarioAlvo);
        [['cor_primaria', cores.primaria], ['cor_secundaria', cores.secundaria], ['cor_terciaria', cores.terciaria], ['cor_texto_primario', cores.textoPrimario], ['cor_texto_secundario', cores.textoSecundario], ['historia', historia.trim()], ['localizacao', localizacao.trim()], ['contato_telefone', contatos.telefone.trim()], ['contato_email', contatos.email.trim()], ['instagram', contatos.instagram.trim()], ['chave_pix', chavePix.trim()], ['arkhe_client_id', arkheClientId.trim()], ['arkhe_client_secret', arkheClientSecret.trim()]].forEach(([campo, valor]) => formulario.append(campo, valor));
        dias.forEach((dia) => {
            if (!dia.fechado) [['entrada_manha', dia.manhaInicio], ['saida_manha', dia.manhaFim], ['entrada_tarde', dia.tardeInicio], ['saida_tarde', dia.tardeFim]].forEach(([campo, valor]) => formulario.append(`${dia.chave}_${campo}`, valor));
        });
        const equipe = funcionarios.filter((funcionario) => funcionario.nome.trim());
        formulario.append('num_funcionarios', equipe.length);
        equipe.forEach((funcionario, indice) => {
            anexarFuncionario(formulario, funcionario, indice);
        });
        if (logo instanceof File) formulario.append('logo', logo);
        fotos.forEach((foto, indice) => { if (foto instanceof File) formulario.append(`foto${indice + 1}`, foto); });
        return formulario;
    }

    async function salvar(evento) {
        evento.preventDefault();
        if (salvando) return;
        const erroEquipe = funcionarios.map(erroFuncionario).find(Boolean);
        if (erroEquipe) return setMensagem({ informacao: erroEquipe, tipo: 'erro' });
        if (!diasAbertos.length) return setMensagem({ informacao: 'Informe ao menos um dia de atendimento.', tipo: 'erro' });
        if (!funcionarios.some((funcionario) => funcionario.nome.trim())) return setMensagem({ informacao: 'Cadastre pelo menos um barbeiro na equipe.', tipo: 'erro' });
        if (funcionarios.some((funcionario) => funcionario.nome.trim() && !funcionario.dias.length)) return setMensagem({ informacao: 'Vincule pelo menos um dia de serviço para cada funcionário.', tipo: 'erro' });
        if (![chavePix, arkheClientId, arkheClientSecret].every((valor) => valor.trim())) return setMensagem({ informacao: 'Informe a chave PIX, o Client ID e o Client Secret da Arkhé para receber pagamentos.', tipo: 'erro' });
        setSalvando(true);
        try {
            const resposta = await apiFetch('/barbearia/personalizacao', { method: modoEdicao || personalizacaoSalva ? 'PUT' : 'POST', body: montarFormulario() });
            setPersonalizacaoSalva(true);
            if (resposta.convites?.length) {
                setConvites(resposta.convites);
                setFuncionarios((lista) => lista.map((funcionario) => {
                    const convite = resposta.convites.find((item) => item.email?.toLowerCase() === funcionario.email?.trim().toLowerCase());
                    return convite?.id_funcionario ? { ...funcionario, id_funcionario: convite.id_funcionario, possui_login: true } : funcionario;
                }));
                setMensagem(resposta.mensagem || { informacao: 'Dados salvos. Confira os convites de acesso abaixo.', tipo: 'sucesso' });
                return;
            }
            setMensagem(resposta.mensagem);
            navigate(idUsuarioAlvo ? `/estabelecimento?usuario=${idUsuarioAlvo}` : '/estabelecimento', { replace: true });
        } catch (erro) { setMensagem({ informacao: mensagemDaApi(erro), tipo: 'erro' }); } finally { setSalvando(false); }
    }

    return <main className={styles.page}>
        <MensagemCard mensagem={mensagem} fechar={() => setMensagem(null)} />
        {convites.length > 0 && <section className={styles.convites} aria-label="Convites de acesso dos barbeiros">
            <h2>Acesso dos barbeiros</h2><p>Cada barbeiro define sua senha pelo convite. O link é pessoal; compartilhe somente com o destinatário.</p>
            {convites.map((convite) => <article key={convite.id_funcionario || convite.email}>
                <h3>{convite.email}</h3><p>{convite.email_enviado ? 'Convite enviado por e-mail.' : 'O e-mail não foi enviado. Copie o link abaixo e entregue ao barbeiro.'}</p>
                {convite.link_ativacao && <><label>Link de ativação<input readOnly value={convite.link_ativacao} onFocus={(evento) => evento.target.select()} /></label>
                    <button type="button" className={styles.secundario} onClick={async () => {
                        try { await navigator.clipboard.writeText(convite.link_ativacao); setLinkCopiado(convite.email); }
                        catch { setMensagem({ informacao: 'Selecione o link e copie manualmente.', tipo: 'erro' }); }
                    }}>Copiar convite</button></>}
                {linkCopiado === convite.email && <p role="status">Link copiado.</p>}
            </article>)}
            <button type="button" className={styles.secundario} onClick={() => navigate(idUsuarioAlvo ? `/estabelecimento?usuario=${idUsuarioAlvo}` : '/estabelecimento')}>Ver barbearia</button>
        </section>}
        <form className={styles.container} onSubmit={salvar}>
            <div className={`${styles.span2} ${styles.cabecalhoPagina}`}><p className={styles.eyebrow}>{modoEdicao ? 'GESTÃO DO ESTABELECIMENTO' : 'PRIMEIROS PASSOS'}</p><h1 className={styles.titulo}>{modoEdicao ? 'Editar barbearia' : 'Personalize sua barbearia'}</h1><p className={styles.subtitulo}>Organize sua vitrine, equipe, serviços, horários e identidade visual em um só lugar.</p><div /></div>
            {carregando ? <p className={styles.carregando}>Carregando dados da barbearia…</p> : <>
                <section className={`${styles.section} ${styles.span2}`}><div className={styles.sectionHead}><span className={styles.dot}><Scissors size={16} /></span>Serviços disponíveis</div><div className={styles.tags}>{servicos.slice(0, 5).map((servico) => <span className={styles.tag} key={servico.id_servico}><span>{servico.nome}</span><span className={styles.acoesServico}><button type="button" onClick={() => abrirEditarServico(servico)} aria-label={`Editar ${servico.nome}`}><Pencil size={13} /></button><button type="button" onClick={() => removerServico(servico)} aria-label={`Remover ${servico.nome}`}><Trash2 size={13} /></button></span></span>)}<button type="button" className={styles.tagAdd} onClick={abrirAdicionarServico}><Plus size={13} />Adicionar serviço</button>{servicos.length > 5 && <button type="button" className={styles.tagAdd} onClick={() => setModalServicosAberto(true)}><Plus size={13} />Ver mais ({servicos.length - 5})</button>}</div></section>
                <section className={`${styles.section} ${styles.span2}`}><TabelaHorarios dias={dias} onToggleDia={(nome) => setDias((lista) => lista.map((dia) => dia.nome === nome ? { ...dia, fechado: !dia.fechado } : dia))} onChangeHorario={(nome, campo, valor) => setDias((lista) => lista.map((dia) => dia.nome === nome ? { ...dia, [campo]: valor } : dia))} /></section>
                <section className={styles.section}><div className={styles.sectionHead}><span className={styles.dot}><Users size={16} /></span>Equipe <small>(ao menos um barbeiro obrigatório)</small></div>
                    {funcionarios.map((funcionario, indice) => <div className={styles.funcionario} key={funcionario.id}>
                        <div className={styles.funcionarioCabecalho}><strong>Funcionário {indice + 1}</strong>{funcionarios.length > 1 && <button type="button" onClick={() => setFuncionarios((lista) => lista.filter((_, i) => i !== indice))}><Trash2 size={15} /> Remover</button>}</div>
                        <label className={styles.label}>Nome<MaskedInput className={styles.input} mask={/^[A-Za-zÀ-ÿ ]*$/} value={funcionario.nome} onAccept={(valor) => atualizarFuncionario(indice, 'nome', valor)} /></label>
                        <label className={styles.label}>Descrição / especialidade<MaskedInput className={styles.input} value={funcionario.descricao} onAccept={(valor) => atualizarFuncionario(indice, 'descricao', valor)} placeholder="Ex.: Barbeiro especialista" /></label>
                        <label className={styles.label}>E-mail para acesso<input className={styles.input} type="email" maxLength={150} readOnly={Boolean(funcionario.possui_login)} value={funcionario.email} required={!funcionario.id_funcionario} onChange={(evento) => atualizarFuncionario(indice, 'email', evento.target.value)} autoComplete="off" /></label>
                        {funcionario.possui_login && <small>O e-mail de uma conta vinculada permanece fixo neste formulário.</small>}
                        <label className={styles.label}>Telefone com DDD<MaskedInput className={styles.input} mask="(00) 0000[0]-0000" type="tel" value={funcionario.telefone} onAccept={(valor) => atualizarFuncionario(indice, 'telefone', valor)} required={!funcionario.id_funcionario || Boolean(funcionario.email)} /></label>
                        <label className={styles.label}>Comissão percentual (%)<input className={styles.input} type="number" min="0" max="100" step="0.01" value={funcionario.comissao_percentual} onChange={(evento) => atualizarFuncionario(indice, 'comissao_percentual', evento.target.value)} /></label>
                        {!funcionario.id_funcionario && <small>Ao salvar, será gerado um convite para definir a senha. Nenhuma senha será enviada por e-mail.</small>}
                        {funcionario.id_funcionario && !funcionario.email && <small>Cadastro existente preservado. Informe e-mail e telefone para configurar o acesso.</small>}
                        {funcionario.id_funcionario && funcionario.email && <button type="button" className={styles.secundario} disabled={salvando} onClick={() => reenviarConvite(funcionario)}>Reenviar convite de acesso</button>}
                        <span className={styles.label}>Dias de serviço vinculados</span><div className={styles.checks}>{diasAbertos.map((dia) => <label key={dia.chave} className={styles.check}><input type="checkbox" checked={funcionario.dias.includes(dia.chave)} onChange={() => alternarDiaFuncionario(indice, dia.chave)} />{dia.nome}</label>)}</div>
                        <span className={styles.label}>Serviços que realiza</span><div className={styles.checks}>{servicos.length ? <>{servicos.slice(0, 5).map((servico) => <label key={servico.id_servico} className={styles.check}><input type="checkbox" checked={funcionario.servicos.includes(servico.id_servico)} onChange={() => alternarServicoFuncionario(indice, servico.id_servico)} />{servico.nome}</label>)}{servicos.length > 5 && <button type="button" className={styles.verMaisCheck} onClick={() => setServicoFuncionarioAberto(indice)}>Ver mais ({servicos.length - 5})</button>}</> : <small>Cadastre serviços abaixo para vinculá-los.</small>}</div>
                    </div>)}
                    <button type="button" className={styles.secundario} onClick={() => setFuncionarios((lista) => [...lista, novoFuncionario()])}><Plus size={16} /> Adicionar funcionário</button>
                </section>
                <section className={styles.section}><div className={styles.sectionHead}><span className={styles.dot}><Scissors size={16} /></span>História da empresa</div><label className={styles.label}>Conte sua história<textarea className={styles.textarea} value={historia} onChange={(e) => setHistoria(e.target.value)} /></label><label className={styles.label}>Localização<MaskedInput className={styles.input} value={localizacao} onAccept={setLocalizacao} placeholder="Rua, número, bairro e cidade" /></label></section>
                <section className={styles.section}><div className={styles.sectionHead}><span className={styles.dot}><ImageIcon size={16} /></span>Contatos da barbearia</div><label className={styles.label}>Telefone / WhatsApp<MaskedInput className={styles.input} mask="(00) 0000[0]-0000" value={contatos.telefone} onAccept={(telefone) => setContatos({ ...contatos, telefone })} placeholder="(00) 00000-0000" /></label><label className={styles.label}>E-mail de contato<MaskedInput className={styles.input} mask={/^[\w.+-@]*$/} type="email" value={contatos.email} onAccept={(email) => setContatos({ ...contatos, email })} placeholder="contato@barbearia.com" /></label><label className={styles.label}>Instagram<MaskedInput className={styles.input} mask={/^@?[A-Za-z0-9._]*$/} value={contatos.instagram} onAccept={(instagram) => setContatos({ ...contatos, instagram })} placeholder="@sua_barbearia" /></label></section>
                <section className={styles.section}><div className={styles.sectionHead}><span className={styles.dot}><CreditCard size={16} /></span>Integração de Pagamento (PIX / Arkhé) <small>(obrigatória)</small></div><div className={styles.avisoPix}><AlertCircle size={16} /><span>Para receber pagamentos via PIX, configure sua chave PIX do banco Arkhé. <strong>Se não tiver conta no Arkhé, crie em <a href="https://arkhe-frontend.zbbquj.easypanel.host/" target="_blank" rel="noopener noreferrer">arkhe.com.br</a></strong> e insira o Client ID e Client Secret abaixo.</span></div><label className={styles.label}>Chave PIX<MaskedInput className={styles.input} value={chavePix} onAccept={(valor) => setChavePix(valor)} placeholder="Ex.: sua-chave-pix@email.com" required /></label><label className={styles.label}>Arkhé Client ID<MaskedInput className={styles.input} value={arkheClientId} onAccept={(valor) => setArkheClientId(valor)} placeholder="Seu Client ID da Arkhé" required /></label><label className={styles.label}>Arkhé Client Secret<span className={styles.campoSenha}><MaskedInput className={styles.input} type={mostrarSecret ? 'text' : 'password'} value={arkheClientSecret} onAccept={(valor) => setArkheClientSecret(valor)} placeholder="Seu Client Secret da Arkhé" required /><button type="button" className={styles.botaoOlho} onClick={() => setMostrarSecret((v) => !v)} aria-label={mostrarSecret ? 'Ocultar senha' : 'Mostrar senha'} title={mostrarSecret ? 'Ocultar senha' : 'Mostrar senha'}>{mostrarSecret ? <EyeOff size={18} /> : <Eye size={18} />}</button></span></label></section>
                <section className={`${styles.section} ${styles.sectionHead}`}><SeletorIdentidadeVisual value={cores} onChange={setCores} /></section>
                <section className={`${styles.section} ${styles.span2}`}><div className={styles.sectionHead}><span className={styles.dot}><ImageIcon size={16} /></span>Imagens da empresa</div><div className={styles.row2}><label className={styles.upload}><Upload size={18} />{logo ? 'Trocar logo' : 'Upload do logo'}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => { const arquivo = e.target.files?.[0] || null; setLogo(arquivo); setPreviewLogo(arquivo ? URL.createObjectURL(arquivo) : null); }} /></label><label className={styles.upload}><Upload size={18} />Adicionar fotos<input type="file" multiple accept="image/png,image/jpeg,image/webp" onChange={(e) => { const arquivos = Array.from(e.target.files || []).slice(0, 5); setFotos(arquivos); setPreviewsFotos(arquivos.map((arquivo) => URL.createObjectURL(arquivo))); }} /></label></div>{(previewLogo || previewsFotos.length > 0) && <div className={styles.previews}>{previewLogo && <figure className={styles.previewLogo}><img src={previewLogo} alt="Prévia do logo" /><figcaption>Logo</figcaption></figure>}{previewsFotos.map((url, indice) => <figure className={styles.previewFoto} key={url}><img src={url} alt={`Prévia da foto ${indice + 1}`} /><figcaption>Foto {indice + 1}</figcaption></figure>)}</div>}</section>
                <div className={styles.span2}><button className={styles.btnPrimario} disabled={salvando}>{salvando ? 'SALVANDO…' : modoEdicao ? 'SALVAR ALTERAÇÕES' : 'CRIAR BARBEARIA'}</button></div>
            </>}
        </form>
        <ModalAdicionarServico open={modalAberto} onClose={() => { setModalAberto(false); setServicoEditando(null); }} onAdd={salvarServico} servicoEditando={servicoEditando} />
        {modalServicosAberto && (
            <div className={styles.modalOverlay} onClick={() => setModalServicosAberto(false)}>
                <div className={styles.modalServicos} onClick={(e) => e.stopPropagation()}>
                    <div className={styles.modalServicosHeader}>
                        <h3>Todos os serviços ({servicos.length})</h3>
                        <button type="button" onClick={() => setModalServicosAberto(false)} aria-label="Fechar">×</button>
                    </div>
                    <div className={styles.modalServicosLista}>
                        {servicos.map((servico) => (
                            <div key={servico.id_servico} className={styles.modalServicoItem}>
                                <span className={styles.modalServicoNome}>{servico.nome}</span>
                                <span className={styles.modalServicoPreco}>R$ {Number(servico.preco || 0).toFixed(2).replace('.', ',')}</span>
                                <span className={styles.modalServicoAcoes}>
                                    <button type="button" onClick={() => { abrirEditarServico(servico); setModalServicosAberto(false); }} aria-label={`Editar ${servico.nome}`}><Pencil size={13} /></button>
                                    <button type="button" onClick={() => removerServico(servico)} aria-label={`Remover ${servico.nome}`}><Trash2 size={13} /></button>
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        )}
        {servicoFuncionarioAberto !== null && funcionarios[servicoFuncionarioAberto] && (
            <div className={styles.modalOverlay} onClick={() => setServicoFuncionarioAberto(null)}>
                <div className={styles.modalServicos} onClick={(e) => e.stopPropagation()}>
                    <div className={styles.modalServicosHeader}>
                        <h3>Serviços do funcionário {servicoFuncionarioAberto + 1}</h3>
                        <button type="button" onClick={() => setServicoFuncionarioAberto(null)} aria-label="Fechar">×</button>
                    </div>
                    <div className={styles.modalServicosLista}>
                        <div className={styles.checks}>
                            {servicos.map((servico) => (
                                <label key={servico.id_servico} className={styles.check}>
                                    <input type="checkbox"
                                        checked={funcionarios[servicoFuncionarioAberto].servicos.includes(servico.id_servico)}
                                        onChange={() => alternarServicoFuncionario(servicoFuncionarioAberto, servico.id_servico)} />
                                    {servico.nome}
                                </label>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        )}

        <ModalConfirmacao
            aberto={!!servicoRemovendo}
            titulo="Remover serviço"
            mensagem={`Deseja remover o serviço “${servicoRemovendo?.nome || ''}”?`}
            detalhe="Ele deixará de estar disponível para agendamentos e para a equipe."
            textoConfirmar="Remover"
            textoCancelar="Voltar"
            perigo
            processando={removendo}
            aoConfirmar={confirmarRemocaoServico}
            aoCancelar={() => setServicoRemovendo(null)}
        />
    </main>;
}


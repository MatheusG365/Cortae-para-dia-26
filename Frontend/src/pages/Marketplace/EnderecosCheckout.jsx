import { useEffect, useEffectEvent, useRef, useState } from 'react';
import Select from '../../components/Select/Select';
import { estadosBrasil } from '../../services/cadastroState';
import { aplicarResultadoCep, enderecoSalvo, mudarCep, normalizarCep, novoEndereco } from '../../services/cepEnderecoState';
import { mensagemDaApi } from '../../services/api';
import { json, marketplace } from './marketplaceApi';
import styles from './EnderecosCheckout.module.css';
import { pendenciasEndereco } from './checkoutState';

const campos = [['nome', 'Nome completo'], ['email', 'E-mail'], ['telefone', 'Telefone'], ['documento', 'CPF ou CNPJ'], ['cep', 'CEP'], ['logradouro', 'Rua'], ['numero', 'Número'], ['complemento', 'Complemento'], ['bairro', 'Bairro'], ['cidade', 'Cidade']];

export default function EnderecosCheckout({ endereco, atualizar, usuario, ocupado }) {
    const [lista, setLista] = useState(null);
    const [erroLista, setErroLista] = useState('');
    const [tentativa, setTentativa] = useState(0);
    const [selecionado, setSelecionado] = useState('');
    const [modo, setModo] = useState('novo');
    const [apelido, setApelido] = useState('Casa');
    const [padrao, setPadrao] = useState(false);
    const [salvando, setSalvando] = useState(false);
    const [erro, setErro] = useState('');
    const [sucesso, setSucesso] = useState('');
    const [consultaCep, setConsultaCep] = useState({});
    const tocado = useRef(false);
    const camposEditados = useRef(new Set());
    const ignorarCep = useRef('');
    const controllerCep = useRef(null);
    const controllerSalvar = useRef(null);
    const formulario = useRef(null);
    const cep = normalizarCep(endereco.cep);
    const bloqueado = ocupado || salvando;

    function usar(salvo) {
        controllerCep.current?.abort();
        camposEditados.current.clear();
        ignorarCep.current = normalizarCep(salvo.dados?.cep);
        setConsultaCep({});
        setSelecionado(String(salvo.id_endereco));
        setModo(pendenciasEndereco(salvo.dados).length ? 'editar' : 'usar');
        setApelido(salvo.apelido || 'Casa');
        setPadrao(Boolean(salvo.padrao));
        setErro('');
        setSucesso('');
        atualizar(enderecoSalvo(salvo.dados));
    }
    const receberLista = useEffectEvent(dados => {
        if (!Array.isArray(dados.enderecos)) throw new Error('Não foi possível carregar seus endereços.');
        setLista(dados.enderecos);
        setErroLista('');
        const inicial = dados.enderecos.find(item => item.padrao) || dados.enderecos[0];
        if (!tocado.current && inicial) usar(inicial);
    });
    useEffect(() => {
        const controller = new AbortController();
        marketplace('/enderecos', { signal: controller.signal })
            .then(dados => { if (!controller.signal.aborted) receberLista(dados); })
            .catch(falha => { if (!controller.signal.aborted) setErroLista(mensagemDaApi(falha)); });
        return () => controller.abort();
    }, [tentativa]);

    const receberCep = useEffectEvent((dados, consultado) => {
        if (!dados.endereco) throw new Error('Não foi possível consultar este CEP. Preencha o endereço manualmente.');
        atualizar(aplicarResultadoCep(endereco, dados.endereco, consultado, [...camposEditados.current]));
        setConsultaCep({ cep: consultado, texto: 'CEP encontrado. Confira o endereço e informe número e complemento.', tipo: 'sucesso' });
    });
    useEffect(() => {
        if (cep.length !== 8 || ignorarCep.current === cep) return undefined;
        const controller = new AbortController();
        controllerCep.current = controller;
        const timer = setTimeout(() => {
            setConsultaCep({ cep, texto: 'Buscando endereço pelo CEP…', tipo: 'buscando' });
            marketplace(`/cep/${cep}`, { signal: controller.signal })
                .then(dados => { if (!controller.signal.aborted) receberCep(dados, cep); })
                .catch(falha => {
                    if (!controller.signal.aborted) setConsultaCep({ cep, texto: falha.status === 404 ? 'CEP não encontrado. Confira os dígitos ou preencha o endereço manualmente.' : 'A consulta de CEP está indisponível. Você pode preencher o endereço manualmente.', tipo: 'aviso' });
                });
        }, 350);
        return () => { clearTimeout(timer); controller.abort(); };
    }, [cep]);
    useEffect(() => () => { controllerCep.current?.abort(); controllerSalvar.current?.abort(); }, []);

    function mudar(campo, valor) {
        tocado.current = true;
        setSucesso('');
        setErro('');
        if (campo === 'cep') {
            if (normalizarCep(valor) !== cep) {
                controllerCep.current?.abort();
                camposEditados.current.clear();
                ignorarCep.current = '';
                setConsultaCep({});
            }
            atualizar(mudarCep(endereco, valor));
        } else {
            camposEditados.current.add(campo);
            atualizar({ ...endereco, [campo]: valor });
        }
    }
    function adicionar() {
        tocado.current = true;
        controllerCep.current?.abort();
        ignorarCep.current = '';
        camposEditados.current.clear();
        setSelecionado('');
        setModo('novo');
        setApelido('Casa');
        setPadrao(false);
        setErro('');
        setSucesso('');
        setConsultaCep({});
        atualizar(novoEndereco(usuario));
    }
    async function salvar() {
        const camposInvalidos = [...formulario.current.querySelectorAll('input')].find(input => !input.checkValidity());
        if (camposInvalidos) { camposInvalidos.reportValidity(); return; }
        const controller = new AbortController();
        controllerSalvar.current = controller;
        const id = modo === 'editar' ? selecionado : '';
        const snapshot = { ...endereco };
        setSalvando(true);
        setErro('');
        setSucesso('');
        try {
            const dados = await marketplace(id ? `/enderecos/${id}` : '/enderecos', { ...json(id ? 'PUT' : 'POST', { apelido: apelido.trim() || 'Casa', endereco: snapshot, padrao }), signal: controller.signal });
            if (controller.signal.aborted) return;
            if (!dados.endereco?.id_endereco) throw new Error('O servidor não confirmou o endereço salvo. Tente novamente.');
            const salvo = dados.endereco;
            tocado.current = true;
            setLista(anteriores => [...(anteriores || []).filter(item => String(item.id_endereco) !== String(salvo.id_endereco)).map(item => salvo.padrao ? { ...item, padrao: false } : item), salvo]);
            usar(salvo);
            setSucesso('Endereço salvo na sua conta para as próximas compras.');
            // O servidor pode promover outro padrão quando este é desmarcado.
            setTentativa(valor => valor + 1);
        } catch (falha) {
            if (!controller.signal.aborted) setErro(mensagemDaApi(falha));
        } finally { if (!controller.signal.aborted) setSalvando(false); }
    }
    const salvoAtual = lista?.find(item => String(item.id_endereco) === selecionado);
    const alterado = salvoAtual && JSON.stringify(enderecoSalvo(salvoAtual.dados)) !== JSON.stringify(endereco);
    return <section className={styles.secao} aria-label="Endereço de entrega">
        <h3>Dados de entrega</h3>
        {lista === null && !erroLista && <p role="status">Carregando endereços salvos… Você já pode preencher os dados abaixo.</p>}
        {erroLista && <div className={styles.aviso} role="alert"><p>Não foi possível carregar seus endereços salvos. {erroLista}</p><button type="button" disabled={bloqueado} onClick={() => { setErroLista(''); setTentativa(valor => valor + 1); }}>Tentar novamente</button><p>Você pode preencher e usar o endereço manualmente.</p></div>}
        {lista?.length > 0 && <label>Endereços salvos<Select value={selecionado} disabled={bloqueado} onChange={evento => { tocado.current = true; const salvo = lista.find(item => String(item.id_endereco) === evento.target.value); if (salvo) usar(salvo); }}><option value="">Selecione um endereço salvo</option>{lista.map(item => <option key={item.id_endereco} value={String(item.id_endereco)}>{item.apelido}{item.padrao ? ' · Padrão' : ''} · {item.dados?.logradouro}, {item.dados?.numero} · {item.dados?.cidade}/{item.dados?.uf}</option>)}</Select></label>}
        {lista?.length === 0 && <p>Salve um endereço na sua conta para agilizar sua próxima compra.</p>}
        {modo === 'usar' && <div className={styles.enderecoResumo}>
            <span className={styles.identificacao}>{salvoAtual?.apelido || 'Endereço desta compra'}{salvoAtual?.padrao ? ' · Padrão' : ''}</span>
            {alterado && <small>Alterações válidas só para esta compra.</small>}<strong>{endereco.nome}</strong><p>{endereco.logradouro}, {endereco.numero}{endereco.complemento ? ` · ${endereco.complemento}` : ''}</p>
            <p>{endereco.bairro} · {endereco.cidade}/{endereco.uf} · CEP {endereco.cep}</p><small>{endereco.email} · {endereco.telefone}</small>
        </div>}
        <div className={styles.acoes}>{modo === 'usar' && alterado && <button type="button" disabled={bloqueado} onClick={() => usar(salvoAtual)}>Restaurar endereço salvo</button>}{modo === 'usar' && <button type="button" disabled={bloqueado} onClick={() => { tocado.current = true; setModo(selecionado ? 'editar' : 'novo'); setSucesso(''); }}>Editar endereço</button>}<button type="button" disabled={bloqueado} onClick={adicionar}>Adicionar novo endereço</button></div>
        {modo !== 'usar' && <fieldset ref={formulario} disabled={bloqueado} className={styles.campos}>
            <legend className={styles.legenda}>Contato e endereço</legend>
            {campos.map(([campo, label]) => <label key={campo}><span>{label}{campo === 'complemento' && <span className={styles.opcional}> (opcional)</span>}</span><input type={campo === 'email' ? 'email' : campo === 'telefone' ? 'tel' : 'text'} value={endereco[campo]} onChange={evento => mudar(campo, evento.target.value)} required={campo !== 'complemento'} inputMode={['cep', 'documento', 'telefone'].includes(campo) ? 'numeric' : undefined} autoComplete={ { nome: 'name', email: 'email', telefone: 'tel', cep: 'postal-code', logradouro: 'address-line1', complemento: 'address-line2', cidade: 'address-level2', uf: 'address-level1' }[campo] || 'off'} maxLength={campo === 'cep' ? 9 : campo === 'documento' ? 18 : 160} pattern={campo === 'cep' ? '[0-9]{5}-?[0-9]{3}' : undefined} placeholder={campo === 'cep' ? '00000-000' : campo === 'complemento' ? 'Apartamento, bloco, referência…' : undefined} aria-describedby={campo === 'cep' ? 'checkout-cep-ajuda' : undefined} />{campo === 'cep' && <span id="checkout-cep-ajuda" className={styles.ajudaCep} role="status">{consultaCep.cep === cep ? consultaCep.texto : 'Digite o CEP para buscar rua, bairro, cidade e UF automaticamente.'}</span>}</label>)}
            <label>UF<Select value={endereco.uf} onChange={evento => mudar('uf', evento.target.value)} disabled={bloqueado} required><option value="">Selecione</option>{estadosBrasil.map(uf => <option key={uf}>{uf}</option>)}</Select></label>
            {modo !== 'usar' && <><label>Nome deste endereço<input value={apelido} onChange={evento => setApelido(evento.target.value)} placeholder="Casa, trabalho…" maxLength={60} /></label><label className={styles.padrao}><input type="checkbox" checked={padrao} onChange={evento => setPadrao(evento.target.checked)} />Usar como endereço padrão</label></>}
        </fieldset>}
        {modo !== 'usar' && <div className={styles.acoes}><button type="button" disabled={bloqueado} onClick={salvar}>{salvando ? 'Salvando endereço…' : 'Salvar endereço'}</button><button type="button" disabled={bloqueado || pendenciasEndereco(endereco).length > 0} onClick={() => setModo('usar')}>Usar só nesta compra</button><small>{modo === 'editar' ? 'Salvar atualiza o cadastro. “Usar só nesta compra” mantém o endereço salvo como está.' : 'Salvar guarda o endereço para as próximas compras.'}</small></div>}
        {erro && <p className={styles.aviso} role="alert">{erro}</p>}{sucesso && <p className={styles.sucesso} role="status">{sucesso}</p>}
    </section>;
}

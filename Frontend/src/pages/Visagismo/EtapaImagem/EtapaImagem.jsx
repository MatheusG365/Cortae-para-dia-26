import { useEffect, useRef, useState } from 'react';

import {
    FiCamera,
    FiSun,
    FiSmile,
    FiArrowLeft,
    FiImage,
    FiRefreshCw,
    FiX
} from 'react-icons/fi';

import styles from './EtapaImagem.module.css';

function EtapaImagem({
                          imagem,
                          arquivo,
                          setImagem,
                          setArquivo,
                          voltar,
                          pularVisagismo,
                          carregando,
                          avancarEtapa,
                          apenasCor = false,
                          pintarObrigatorio = false
                     }) {
    const inputRef = useRef(null);
    const cameraRef = useRef(null);
    const videoRef = useRef(null);
    const streamRef = useRef(null);
    const [arrastando, setArrastando] = useState(false);
    const [origemFoto, setOrigemFoto] = useState('arquivo');
    const [cameraAtiva, setCameraAtiva] = useState(false);
    const [cameraErro, setCameraErro] = useState('');
    const [modoCamera, setModoCamera] = useState('user'); // user = frontal | environment = traseira

    const selecionarImagem = (arquivo) => {
        if (!arquivo || carregando) return;

        if (!arquivo.type.startsWith('image/')) {
            return;
        }

        const url = URL.createObjectURL(arquivo);
        setImagem(url);
        setArquivo(arquivo);
    };

    const handleInput = (event) => {
        selecionarImagem(event.target.files[0]);
    };

    const handleDrop = (event) => {
        event.preventDefault();
        setArrastando(false);

        const arquivo = event.dataTransfer.files[0];
        selecionarImagem(arquivo);
    };

    const abrirSeletor = () => {
        if (carregando) return;
        if (origemFoto === 'camera') {
            abrirCamera();
        } else {
            inputRef.current?.click();
        }
    };

    const pararCamera = () => {
        streamRef.current?.getTracks().forEach((faixa) => faixa.stop());
        streamRef.current = null;
        if (videoRef.current) videoRef.current.srcObject = null;
        setCameraAtiva(false);
    };

    const abrirCamera = () => {
        if (carregando) return;
        setCameraErro('');
        setOrigemFoto('camera');
        // Sem acesso direto à câmera (ex.: HTTP sem localhost), cai no
        // seletor com capture, que no celular oferece a câmera.
        if (!navigator.mediaDevices?.getUserMedia) {
            cameraRef.current?.click();
            return;
        }
        setCameraAtiva(true);
    };

    useEffect(() => {
        if (!cameraAtiva) return undefined;
        let vivo = true;
        let fluxo = null;
        (async () => {
            try {
                fluxo = await navigator.mediaDevices.getUserMedia({
                    video: { facingMode: modoCamera }, audio: false
                });
                if (!vivo) {
                    fluxo.getTracks().forEach((faixa) => faixa.stop());
                    return;
                }
                streamRef.current = fluxo;
                if (videoRef.current) {
                    videoRef.current.srcObject = fluxo;
                    await videoRef.current.play().catch(() => {});
                }
            } catch {
                if (vivo) {
                    setCameraErro('Não foi possível acessar a câmera. Verifique a permissão ou use "Enviar foto".');
                    setCameraAtiva(false);
                }
            }
        })();
        return () => {
            vivo = false;
            fluxo?.getTracks().forEach((faixa) => faixa.stop());
            if (streamRef.current === fluxo) streamRef.current = null;
        };
    }, [cameraAtiva, modoCamera]);

    useEffect(() => () => {
        streamRef.current?.getTracks().forEach((faixa) => faixa.stop());
    }, []);

    const trocarCamera = () => {
        setModoCamera((atual) => (atual === 'user' ? 'environment' : 'user'));
    };

    const capturarFoto = () => {
        const video = videoRef.current;
        if (!video || !video.videoWidth) {
            setCameraErro('Aguarde a câmera iniciar para capturar.');
            return;
        }
        const tela = document.createElement('canvas');
        tela.width = video.videoWidth;
        tela.height = video.videoHeight;
        tela.getContext('2d').drawImage(video, 0, 0);
        tela.toBlob((bloco) => {
            if (!bloco) {
                setCameraErro('Não foi possível capturar. Tente de novo.');
                return;
            }
            selecionarImagem(new File([bloco], 'foto-camera.jpg', { type: 'image/jpeg' }));
            pararCamera();
        }, 'image/jpeg', 0.92);
    };

    const titulo = apenasCor 
        ? 'Coloque uma foto para testar a cor do cabelo'
        : 'Coloque uma imagem para<br />ser feito o visagismo.';
    
    const textoBotao = apenasCor 
        ? 'Continuar para cor'
        : 'Analisar Meu Rosto com IA';
    
    const textoPular = apenasCor 
        ? 'Voltar'
        : 'PULAR';

    return (
        <section className={styles.etapa}>
            <div className={styles.topo}>
                <button type="button" className={styles.botaoVoltar} onClick={voltar} disabled={carregando}>
                    <FiArrowLeft />
                    VOLTAR
                </button>
            </div>

            <div className={styles.areaPrincipal}>
                <div className={styles.tituloArea}>
                    <h1 dangerouslySetInnerHTML={{ __html: titulo }} />

                    <p>
                        Escolha se quer tirar uma foto agora ou enviar uma foto
                        para nossa inteligência artificial analisar.
                    </p>
                    {pintarObrigatorio && (
                        <p className={styles.avisoObrigatorio}>
                            Para serviços de pintura o teste é obrigatório: envie a foto e conclua a simulação para agendar.
                        </p>
                    )}
                </div>

                <div className={styles.origensFoto} role="group" aria-label="Origem da foto">
                    <button type="button" className={origemFoto === 'camera' ? styles.origemAtiva : ''}
                        disabled={carregando} onClick={abrirCamera}><FiCamera /> Tirar foto</button>
                    <button type="button" className={origemFoto === 'arquivo' ? styles.origemAtiva : ''}
                        disabled={carregando} onClick={() => { setOrigemFoto('arquivo'); inputRef.current?.click(); }}><FiImage /> Enviar foto</button>
                </div>

                <input
                    ref={inputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/webp"
                    onChange={handleInput}
                    disabled={carregando}
                    className={styles.inputArquivo}
                />

                <input
                    ref={cameraRef}
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/webp"
                    capture="user"
                    onChange={handleInput}
                    disabled={carregando}
                    className={styles.inputArquivo}
                />

                {cameraAtiva && (
                    <div className={styles.cameraArea}>
                        <video ref={videoRef} className={styles.videoCamera} playsInline muted autoPlay />
                        {cameraErro && <p className={styles.erroCamera}>{cameraErro}</p>}
                        <div className={styles.botoesCamera}>
                            <button type="button" className={styles.botaoAnalise} onClick={capturarFoto}><FiCamera /> Capturar foto</button>
                            <button type="button" className={styles.botaoPular} onClick={trocarCamera}><FiRefreshCw /> Trocar câmera</button>
                            <button type="button" className={styles.botaoPular} onClick={pararCamera}><FiX /> Fechar</button>
                        </div>
                    </div>
                )}
                {!cameraAtiva && (
                <div
                    className={`${styles.areaUpload} ${
                        arrastando ? styles.arrastando : ''
                    } ${imagem ? styles.comImagem : ''}`}
                    onDragOver={(event) => {
                        event.preventDefault();
                        setArrastando(true);
                    }}
                    onDragLeave={() => setArrastando(false)}
                    onDrop={handleDrop}
                    onClick={abrirSeletor}
                    role="button"
                    tabIndex={carregando ? -1 : 0}
                    aria-label="Escolher ou trocar foto"
                    aria-disabled={carregando}
                    onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                            event.preventDefault();
                            abrirSeletor();
                        }
                    }}
                >
                    {imagem ? (
                        <div className={styles.preview}>
                            <img src={imagem} alt="Pré-visualização" />

                            <div className={styles.overlayImagem}>
                                <FiImage />
                                <span>Clique para trocar a imagem</span>
                            </div>
                        </div>
                    ) : (
                        <>
                            <div className={styles.iconeUpload}>
                                <FiCamera />
                            </div>

                            <strong>
                                {apenasCor 
                                    ? 'Clique ou arraste uma foto do seu rosto para testar cores'
                                    : origemFoto === 'camera'
                                        ? 'Clique para abrir a câmera e tirar sua foto'
                                        : 'Arraste e solte a sua foto aqui ou clique para navegar'}
                            </strong>

                            <span>
                                {apenasCor 
                                    ? 'A foto será usada para simular a cor do cabelo'
                                    : '(Formatos suportados: PNG, JPG)'}
                            </span>
                        </>
                    )}
                </div>
                )}

                {!apenasCor && (
                    <div className={styles.dicas}>
                        <div className={styles.dica}>
                            <div className={styles.iconeDica}>
                                <FiCamera />
                            </div>

                            <strong>Olhe Para Frente</strong>
                        </div>

                        <div className={styles.dica}>
                            <div className={styles.iconeDica}>
                                <FiSun />
                            </div>

                            <strong>Boa Iluminação</strong>
                        </div>

                        <div className={styles.dica}>
                            <div className={styles.iconeDica}>
                                <FiSmile />
                            </div>

                            <strong>Sem Acessórios</strong>
                        </div>
                    </div>
                )}

                <div className={styles.botoes}>
                    <button 
                        type="button" 
                        className={apenasCor ? styles.botaoPrincipal : styles.botaoAnalise}
                        onClick={avancarEtapa} 
                        disabled={carregando || !imagem || !arquivo}
                    >
                        {carregando ? (apenasCor ? 'Processando…' : 'Analisando…') : textoBotao}
                    </button>

                    {!apenasCor && !pintarObrigatorio && (
                        <button 
                            type="button" 
                            className={styles.botaoPular}
                            onClick={pularVisagismo}
                            disabled={carregando}
                        >
                            {textoPular}
                        </button>
                    )}
                </div>
            </div>
        </section>
    );
}

export default EtapaImagem;

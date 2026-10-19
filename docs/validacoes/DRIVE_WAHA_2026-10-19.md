# Drive central e WAHA — 19/10/2026

## Drive

A conta conectada ao Drive no Codex conseguiu listar a pasta principal Cortaê,
as seis subpastas diretas e as três subpastas de visagismo. A leitura pelo
backend falhou: a renovação da credencial existente retornou `deleted_client`.
O cliente OAuth antigo foi excluído. Essa é uma falha de autorização no servidor,
não de instalação de credenciais nos aparelhos.

O backend agora aceita a autorização completa em
`GOOGLE_DRIVE_CREDENTIALS_JSON`, no ambiente privado da hospedagem. Mantém o
arquivo externo como opção legada. O JSON tem prioridade, limite de 64 KiB,
validação do provedor e cache identificado por SHA-256; uma configuração inválida
não usa silenciosamente a credencial antiga. O configurador permite selecionar
explicitamente um arquivo mesmo quando existir segredo no ambiente.

O mapa das pastas existentes foi incluído em `Backend/google_drive_folders.json`.
Somente os IDs foram publicados. Nenhum Client Secret, refresh token ou arquivo
de autorização entrou no Git. Site e aplicativo continuam acessando as imagens
pela API central, com as permissões já existentes.

Foi iniciado consentimento para o novo cliente de teste fornecido pelo usuário,
em arquivo privado fora do projeto. A autorização expirou sem conclusão e nenhum
novo refresh token foi salvo. O cliente antigo e seu arquivo foram preservados.
A leitura das imagens pelo backend real continua pendente desse consentimento;
a conexão do Codex ao Drive não comprova a autorização do backend. Não houve
upload, alteração de compartilhamento ou remoção de imagens reais.

Passaram 7 testes novos da configuração central, 14 testes do configurador e
8 testes do transporte Drive: 29 testes focados, sem chamadas reais ao Google.

## WhatsApp

Cliente WAHA, CLI de estado/pareamento/envio explícito e compose persistente
foram adicionados. A chave fica no servidor, o serviço começa desativado,
HTTP remoto é recusado e não há envio ou retry automático. A CLI permite obter
QR privado sem carregar a aplicação ou abrir bancos de negócio.

Passaram 15 testes novos com transporte simulado. Docker não estava disponível;
nenhum contêiner foi iniciado, número pareado ou mensagem real enviada.
Instalação do serviço, chave e pareamento pelo responsável ainda são necessários.
Não foram adicionadas notificações automáticas de agenda ou marketplace.

## Revisão e alcance

Esses testes usaram Python 3.12.10 de 32 bits. A suíte completa e o aplicativo
não foram executados novamente nesta etapa, conforme a instrução do usuário.
A revisão manual independente não encontrou bloqueadores. O revisor local
`qwen2.5-coder:14b` retornou `APPROVED`; contexto 4096, reserva projetada de
10,6 GB, modelo descarregado ao terminar. OpenCode estava indisponível.

O GitHub recebe o código e a documentação; não hospeda automaticamente a API,
o Firebird ou o WAHA. Para acesso externo, o site e o aplicativo precisam apontar
para a mesma API HTTPS hospedada, com os segredos configurados nesse servidor.

[Configuração do Drive](../integracoes/GOOGLE_DRIVE_IMAGENS.md) ·
[Configuração do WAHA](../integracoes/WHATSAPP_WAHA.md) ·
[Aplicativo Android](MOBILE_ANDROID_PYTHON32_2026-10-19.md).

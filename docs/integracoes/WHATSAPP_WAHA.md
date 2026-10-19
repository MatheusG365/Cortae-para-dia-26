# WhatsApp pelo WAHA gratuito

O backend dispõe de um cliente WAHA e de uma CLI administrativa. A integração começa desativada e não modifica o envio de emails, a agenda, o marketplace ou os workers existentes. Nenhuma mensagem é enviada durante configuração, consulta de estado ou obtenção do QR.

A documentação oficial informa que, desde a versão 2026.6.1, o WAHA é gratuito e open source, com os recursos anteriormente separados como Plus incorporados ao Core. O contêiner continua exigindo hospedagem própria e um número WhatsApp pareado. Consulte a [FAQ oficial](https://waha.devlike.pro/docs/overview/faq/#is-waha-free).

## Configuração exclusivamente no servidor

| Variável | Padrão | Uso |
| --- | --- | --- |
| `WAHA_ENABLED` | `false` | Habilita as operações explicitamente. |
| `WAHA_BASE_URL` | `http://127.0.0.1:3000` | Origem do serviço, sem caminho, query ou credenciais embutidas. |
| `WAHA_API_KEY` | vazio | Chave privada original enviada em `X-Api-Key`. |
| `WAHA_SESSION` | `default` | Nome da sessão administrada. |
| `WAHA_TIMEOUT` | `20` | Tempo de leitura entre 1 e 120 segundos; conexão limitada a 5 segundos. |

Use HTTPS para um serviço remoto. HTTP é aceito somente em loopback literal ou `localhost`. O cliente ignora proxies e credenciais de ambiente, não segue redirecionamentos e limita respostas a 2 MiB. Não coloque a chave no aplicativo mobile, frontend, linha de comando ou Git.

## Serviço privado persistente

Instale Docker com contêineres Linux. Na raiz do projeto, execute:

```powershell
docker compose --env-file 'C:\segredos\cortae-waha.env' -f compose.waha.yaml up -d
```

O arquivo externo deve fornecer `WAHA_API_KEY`. A mesma chave original deve estar disponível no ambiente do backend. `WAHA_IMAGE` permite fixar uma versão ou digest da imagem `devlikeapro/waha` após validar sua disponibilidade; o padrão é `devlikeapro/waha:latest`.

O compose publica apenas `127.0.0.1:3000`, desativa Dashboard, Swagger e impressão de QR nos logs, e mantém sessões e mídias em volumes Docker. O contêiner usa a arquitetura suportada pelo Docker; ele se comunica por HTTP com o backend Python de 32 bits. Não apague os volumes ao reiniciar. Veja [instalação](https://waha.devlike.pro/docs/how-to/install/), [armazenamento e configuração](https://waha.devlike.pro/docs/how-to/config/) e [segurança](https://waha.devlike.pro/docs/how-to/security/).

## Pareamento e estado

Na raiz, com as variáveis do backend configuradas:

```powershell
.\Backend\.venv\Scripts\python.exe .\Backend\configurar_whatsapp.py criar
.\Backend\.venv\Scripts\python.exe .\Backend\configurar_whatsapp.py iniciar
.\Backend\.venv\Scripts\python.exe .\Backend\configurar_whatsapp.py status
.\Backend\.venv\Scripts\python.exe .\Backend\configurar_whatsapp.py qr --arquivo 'C:\segredos\cortae-qr.png'
```

`criar` usa `POST /api/sessions` com `start=false`. Se a sessão já existe, consulte seu estado e use `iniciar`. Obtenha o QR quando o estado solicitar pareamento; abra o arquivo local e leia-o em WhatsApp, **Dispositivos conectados**. O QR expira; para atualizar, escolha outro arquivo. A CLI restringe o acesso ao QR ao usuário local e não sobrescreve arquivos existentes. Remova a imagem após o pareamento.

`status` informa `connected=true` somente para `WORKING`. `parar` interrompe a sessão preservando seu vínculo. Os endpoints de sessão e `GET /api/{session}/auth/qr` seguem o [contrato oficial de sessões](https://waha.devlike.pro/docs/how-to/sessions/).

## Envio explícito

Somente o comando `enviar-texto --destino <telefone internacional> --texto <mensagem>` e chamadas explícitas a `WahaClient.send_text()` enviam mensagens. O destino usa DDI e DDD, sem pontuação; o cliente não adivinha nem altera números brasileiros. O texto admite até 4096 caracteres. O contrato utiliza `POST /api/sendText` com sessão, `chatId` terminado em `@c.us` e texto, conforme o [exemplo oficial](https://waha.devlike.pro/docs/overview/quick-start/#step-6-send-a-text-message).

Uma resposta aceita pelo WAHA não comprova entrega. Em timeout, o envio pode ter ocorrido; confira no WhatsApp antes de repetir. Não existe retry automático, fila WhatsApp, webhook ou substituição automática de emails nesta implementação.

## Estado da validação

Foram executados apenas os 15 testes novos `test_waha_client.py`, com Python 3.12.10 de 32 bits e transporte simulado. Eles cobrem contrato, isolamento da CLI, chave, destino, timeout, redirects, respostas grandes, QR e preservação de arquivos. Não houve envio real.

Docker não está disponível nesta máquina durante esta implementação. O contêiner não foi iniciado e nenhum número foi pareado. A conexão real depende de instalar/iniciar o serviço e ler o QR; esta entrega não declara WhatsApp conectado.

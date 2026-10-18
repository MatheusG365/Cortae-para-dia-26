# Cortaê - Backend

## Documentação interativa

Faça login com uma conta de administrador e abra `/api/docs` pela mesma origem do frontend (por exemplo, `http://127.0.0.1:5173/api/docs`). Também funciona diretamente em [http://localhost:5000/docs](http://localhost:5000/docs), com a sessão ADM nessa origem. A interface Swagger mostra métodos, corpos, parâmetros, respostas e permite testar rotas respeitando suas permissões. Ela inclui busca e não persiste credenciais no navegador.

O contrato `/api/openapi.json` pelo proxy, ou `/openapi.json` no backend direto, também exige administrador. `/docs` e `/openapi.json`, inclusive `HEAD`, retornam `401` sem sessão válida e `403` para outros perfis. A conta precisa estar ativa e confirmada; perfil/bloqueio são recarregados no banco em cada consulta. As respostas autorizadas e negadas usam `private, no-store`, `Vary: Cookie, Authorization` e `nosniff`.

`api_docs.py` mantém os contratos anteriores; `docs_contracts.py` acrescenta os módulos comerciais, metas, avaliações, termos e ajuda técnica. `contrato_atual()` alinha nomes dos parâmetros com as regras registradas no Flask e publica somente métodos existentes. `/help`, acessível por URL com sessão ADM, reúne todas as páginas e endpoints, explicações, consultas/corpos, dependências locais e código por ID opaco; configurações/dados são excluídos e credenciais literais são ocultadas.

## Autenticação

`POST /login` salva o JWT no cookie HTTP `access_token`; o backend também aceita `Authorization: Bearer <JWT>`. Os perfis são `0` administrador, `1` cliente, `2` barbearia e `3` profissional vinculado. Publicar a documentação é exclusivo do ADM; cada endpoint descrito aplica sua própria permissão e seu próprio escopo.

## Rotas por área

| Área | Rotas |
| --- | --- |
| Acesso | `POST /cadastro`, `POST /verificar-codigo`, `POST /login`, `POST /logout`, `POST /recuperar-senha` |
| Usuários | `GET /listar_usuarios`, `GET /dados-perfil/{id}`, `PUT /editar-usuario/{id}`, `PUT /usuarios/{id}/status`, `DELETE /excluir-foto-perfil/{id}` |
| Barbearias | `GET /barbearias-disponiveis`, `GET/POST/DELETE /barbearia/servicos`, `GET/POST/PUT /barbearia/personalizacao` |
| Visagismo | `GET/POST /visagismo/cortes`, `PUT/DELETE /visagismo/cortes/{id}`, `POST /visagismo/analisar`, `POST /visagismo/{id}/simular` |
| Agenda | `GET /agendamentos/horarios`, `POST /agendamentos` |
| Arquivos | `GET /fotos-perfil/{arquivo}`, `GET /uploads/perfil/{arquivo}`, `GET /uploads/barbearia/{arquivo}`, `GET /uploads/visagismo/{tipo}/{arquivo}` |

### Módulos comerciais e metas

| Área | Rotas e comportamento |
| --- | --- |
| Vitrine pública | `/marketplace/produtos`, `/marketplace/barbearias/{id}/perfil`, `/marketplace/barbearias/{id}`, `/marketplace/produtos/{id}`. A loja individual React fica em `/estabelecimento?usuario=ID#loja-barbearia`, com as cores do salão; `/marketplace` reúne todas as lojas. |
| Produtos e fornecedores | `/gestao/marketplace/produtos`, `/fornecedores`: CRUD por loja, ativação, custo privado e margem. Promoções com datas inclusivas e preço menor; destaque de lançamento por data. |
| Variações e estoque | `/gestao/marketplace/produtos/{id}/variacoes` e `/estoque`, incluindo estoque por variação. SKU exclusivo na loja; preço/quantidade por tamanho, cor ou volume. Entradas idempotentes. |
| Cliente | `/marketplace/favoritos`, `/lista-desejos`, `/carrinho`, `/pedidos`: listas independentes, carrinho individual com variações e pedidos agrupados por loja. Avaliação de produto só após compra entregue. |
| Cupons | `/gestao/marketplace/cupons`: fixo/percentual, validade, limite de usos por loja. Checkout confere o código no servidor; desconto em mercadorias, nunca no frete. Uso reservado ao criar pedido e liberado no cancelamento permitido. |
| Checkout e entrega | `/marketplace/frete`, `/pedidos/resumo`, `/pedidos/{id}/pix`, `/pagamento`. Cotação e rastreio Melhor Envio; emissão/compra de etiquetas permanece desabilitada por padrão. O resumo usa `confirmacao_resumo`; não se deve confiar em totais do cliente. |
| Vendas | `/gestao/marketplace/relatorios` e `/relatorios.csv`: período pela criação do pedido, faturamento de mercadorias pagas, ticket médio, frete separado e custos históricos. Custos ausentes resultam em lucro não calculado. |
| Ranking e avaliações | `/gestao/ranking`, `/gestao/avaliacoes`; avaliação do próprio atendimento por `/agendamentos/{id}/avaliacao`, exclusiva do cliente. |
| Metas | `/gestao/metas` permite CRUD do dono/ADM; `/painel-barbeiro/metas` consulta somente as próprias metas. Progresso por atendimentos concluídos ou valor histórico dos serviços, separado do caixa. |
| Termos e taxas | `/termos-uso`, `/termos-uso/aceite`, `/gestao/taxas-plataforma`. Rascunho não exige aceite; esta atualização não ativa cobrança nem publicação. |

Os caminhos completos, métodos efetivamente registrados, campos e restrições estão no OpenAPI autenticado; os prefixos abreviados da tabela pertencem à área indicada.

### Verificação da documentação

```powershell
$env:WAITLIST_WORKER='false'
.\.venv\Scripts\python.exe -m unittest tests.test_api_docs tests.test_admin_help -v
```

Os testes usam JWTs reais com conta simulada e verificam bloqueios imediatos, mudança de perfil, credenciais inválidas/expiradas, proteção de GET/HEAD, cobertura dos métodos e rotas atuais, parâmetros reais, IDs únicos e atualização do catálogo Help. Não acessam provedores externos nem escrevem em banco real.

## Visagismo e agenda

Os cortes são cadastrados por administradores ou barbearias com nome, descrição,
categoria e imagem opcional enviada pelo formulário. Referências da internet
usam `imagem_url` HTTPS pública, de até 255 caracteres. O banco armazena a URL;
ela não é baixada permanentemente para o projeto. URLs privadas, credenciais,
portas alternativas e redirecionamentos internos são bloqueados. Na simulação,
a conexão usa o IP público validado com a verificação TLS do hostname original.

`POST /visagismo/analisar` recebe multipart com `imagem`, `id_barbearia` e
`ids_servicos` (CSV ou JSON). O conteúdo precisa ser JPEG, PNG ou WEBP de até
10 MB; o MIME é reconhecido pelo conteúdo, não pela extensão. A Responses API
usa JSON Schema estrito e uma recomendação única de corte ativo compatível
com os serviços. A resposta contém `id_visagismo`, `foto_url`, `versao_analise: 2`,
`categoria`, `observacoes`, `cabelo_atual`, `caracteristicas` e `recomendacoes`.

`caracteristicas` contém `formato_rosto`, `textura_cabelo`, `comprimento_cabelo`,
`densidade_cabelo`, `linha_frontal` e `barba`. Cada recomendação contém o ID e
nome reais do catálogo, motivo personalizado e
`compativel_com_cabelo_existente: true`. Partes não observáveis são declaradas
como não visíveis. A análise não infere identidade, traços sensíveis ou diagnóstico.

Sem pessoa/rosto visível ou corte viável, a API retorna 422. Sem integração
configurada retorna 503; resposta inválida ou falha do provedor retorna 502.
Nenhum desses casos cria uma sessão ou devolve escolhas aleatórias do catálogo.

`POST /visagismo/{id}/simular` aceita somente o corte recomendado pela análise.
Revalida sessão, proprietário, corte ativo e compatibilidade atual com os serviços.
Análises antigas exigem nova análise (409). O fluxo de escolha manual no catálogo
continua disponível: `POST /visagismo/salvar-foto` registra `modo: manual`;
antes de simular, a IA verifica o corte escolhido contra a foto. Sessões destinadas
somente à pintura registram `modo: cor` e não permitem trocar o corte.

A edição envia primeiro a foto do cliente e, quando disponível, a referência
cadastrada como segunda imagem. Referências HTTPS são lidas apenas em memória.
O prompt orienta a preservar pessoa, rosto, cenário, linha frontal, densidade e
cobertura real; para um serviço somente de barba, restringe a edição aos pelos
faciais. A coloração é validada para cabelo, barba ou ambos conforme os serviços
escolhidos. A fidelidade visual deve ser conferida no resultado gerado.

A resposta da simulação inclui `imagem_url`, `referencia_utilizada` e `aviso`.
Sem referência acessível, usa nome e descrição do corte e informa que a
fidelidade à referência visual não foi verificada. O catálogo devolve
`imagem_url: null` para arquivos locais ausentes.

Configure `OPENAI_API_KEY`, `VISAGISMO_ANALYSIS_MODEL`, `VISAGISMO_IMAGE_MODEL`
e `VISAGISMO_IMAGE_QUALITY` no ambiente do servidor. A qualidade aceita `medium`
ou `high`, com padrão `medium`. Para `gpt-image-2`, `input_fidelity` é omitido;
para `gpt-image-1`/`gpt-image-1.5`, usa `high`, conforme a
[documentação oficial da API](https://developers.openai.com/api/reference/resources/images/methods/edit).
Os testes usam provedores e bancos simulados; não comprovam a qualidade visual
real de uma geração paga.

### Referências externas do catálogo

O histórico das referências do catálogo está em `docs/referencias/catalogo_cortes.json`.
Ele registra as URLs e páginas de origem; não é uma configuração carregada pelo sistema.
Cadastre ou edite referências pela administração. Fotos enviadas continuam usando o armazenamento configurado.
Os scripts antigos de preenchimento por manifesto e recuperação de sessões foram retirados após a migração.

`GET /agendamentos/horarios` recebe `id_barbearia`, `ids_servicos` e `data`
(`AAAA-MM-DD`). Ela usa a duração somada dos serviços, os turnos cadastrados da
barbearia e os intervalos já reservados. O `POST /agendamentos` repete todas as
validações dentro de uma trava da barbearia, impedindo sobreposição mesmo em
requisições simultâneas.

## E-mails

`funcoes.enviando_email` usa um único template HTML. Códigos de confirmação de seis dígitos recebem uma caixa destacada; comunicados administrativos e futuros avisos de barbearia recebem apenas texto formatado. A função `enviar_aviso_email` é o ponto de reutilização para esses comunicados.

## Execução local

```bash
pip install -r requirements.txt
python main.py
```

## Banco já preparado

O servidor e as rotas não executam criação de tabelas nem alterações de estrutura.
`/health` consulta a conexão, os campos obrigatórios e a largura do campo de origem financeira; se faltar estrutura, informa indisponibilidade sem tentar alterá-la.

Na pasta Backend:

```powershell
# Somente conferência, sem escrita.
.\.venv\Scripts\python.exe -m migrations

# Operação manual de atualização: faça backup antes.
.\.venv\Scripts\python.exe -m migrations --aplicar
```

`migrations/` reúne as atualizações de esquema e seu manifesto de campos obrigatórios.
Ele é usado em atualizações/restaurações e nos testes isolados; não é importado pelas rotas.
A ferramenta exige um banco base existente, não cria um arquivo Firebird vazio do zero.
A variável antiga `STARTUP_MIGRATIONS` foi retirada; ela não reativa alterações automáticas.
`WAITLIST_WORKER` continua controlando somente a fila de e-mails.

`.venv` contém as dependências do backend, `templates/ativacao.html` é usado nos e-mails, `.env` guarda a configuração privada e os arquivos FDB contêm os dados. Esses itens continuam necessários.

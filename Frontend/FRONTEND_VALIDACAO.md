# Validação do frontend — 10/10/2026

## Correções

- API padrão na mesma origem `/api`; proxy local para `127.0.0.1:5000`; variável `VITE_API_URL` aceita espaços e barras finais.
- Requisições JSON, FormData e gráficos binários compartilham cookies e tratamento de falhas de rede, HTTP e resposta inválida.
- Mensagens não mostram HTML bruto ou objetos de erro; imagens relativas e absolutas usam `urlDaApi`.
- Logout chama o backend antes de remover a sessão local; respostas antigas de perfil não restauram uma conta encerrada.
- Rotas de estabelecimento e seleção de serviços exigem login e preservam o destino com parâmetros.
- Tokens visuais, foco visível, contraste, redução de animações e controles comuns padronizados.
- Diálogos comuns têm foco inicial, Tab/Shift+Tab, Escape e retorno do foco. Login retorna ao botão Entrar.
- Links reais no rodapé, incluindo telas pequenas. Imagens de fundo corrigidas em Home, Login e cadastros.
- Rotas carregadas sob demanda; aviso de dependência do efeito de horários corrigido; logs de depuração removidos.

## Verificações executadas

- `npm test`: 12 testes aprovados, 0 falhas.
- `npm run lint`: 0 erros e 0 avisos, com `--max-warnings 0`.
- `npm run build`: concluído sem avisos. Maior arquivo JavaScript: 251,91 kB (78,10 kB gzip).

Os testes isolados verificam o contrato da camada HTTP. A validação de banco, integrações externas, fluxos autenticados e navegador pertence à verificação integrada do projeto.

## Visagismo — atualização

- Análise exige uma recomendação cadastrada, motivo específico, compatibilidade explícita e foto salva; o corte já fica selecionado.
- Características observadas, cabelo atual e motivo aparecem em blocos próprios. Campos ausentes mostram “Não informado na análise”; limites de observação informados pelo servidor são preservados.
- Foto, referência e resultado usam imagem inteira (`object-fit: contain`). Referências ausentes ou com erro têm placeholder.
- Nova foto, reanálise, corte, cor e categoria invalidam resultados. Trocar os parâmetros da rota remonta o fluxo. Respostas antigas são descartadas; somente a assinatura atual pode ser agendada.
- Corte com pintura exige corte e cor. Pintura sem corte preserva o fluxo próprio; catálogo manual continua oferecendo opções.
- Modal da simulação usa foco, Tab, Escape e retorno do foco compartilhados.
- Administração aceita arquivo ou URL HTTPS de referência e mostra fallback em caso de imagem ausente.
- `npm test`: 19 testes aprovados. Lint e build sem avisos.
- O harness temporário de QA foi removido após a verificação visual; não há dados fictícios no aplicativo entregue.

## Lista de espera e painel do barbeiro — atualização

- Horários ocupados elegíveis oferecem uma ação própria para entrar na lista de espera. Alterações de data, serviço, funcionário ou simulação invalidam a seleção anterior.
- Meus agendamentos mostra a fila, permite sair e informa os estados de aviso, incluindo falha de envio. O aviso por e-mail não reserva um horário.
- Funcionários mantêm o identificador persistido, e-mail, telefone e percentual de comissão. Novos funcionários exigem contato válido; os antigos podem manter o cadastro sem acesso até a configuração do convite.
- Convites mostram o link de ativação e o resultado do envio de e-mail. A ativação exige senha forte; nenhuma senha é enviada por e-mail.
- Perfil 3 acessa o próprio painel, com filtros de período, agendamentos e ações autorizadas pelo servidor. Valores de atendimentos concluídos, pagamentos recebidos e comissões calculadas aparecem separadamente.
- Contagem de remarcados representa agendamentos com remarcação, sem somar cada alteração. Comissões calculadas não indicam transferência bancária.
- Atendimento antigo sem preço registrado exige o valor efetivo no painel do administrador antes da conclusão. O barbeiro não pode informar ou alterar esse preço.
- Telefone do cadastro público continua obrigatório e valida DDD com 10 ou 11 dígitos. O novo perfil aparece nos filtros administrativos; a criação pública não oferece esse papel.
- `npm test`: 24 testes aprovados (HTTP, estado do visagismo, identidade de funcionário, validações, elegibilidade e conclusão de atendimento). Lint e build executados sem avisos.

Os fluxos autenticados, SMTP e persistência são verificados na integração com o backend. O frontend não implementa pagamentos externos de comissão.

## Comissões da barbearia e recebimentos presenciais — 11/10/2026

- `/comissoes-barbearia`, restrita ao proprietário e administrador, mostra o período, totais, profissionais e detalhes históricos de base, percentual e comissão. O administrador seleciona a barbearia; o proprietário consulta a própria equipe.
- O relatório apresenta valores calculados para pagamento manual, sem declarar comissão paga ou repasse automático. A interface não grava comissões externas na Arkhé.
- Escolher pagar no local cria uma intenção pendente de confirmação. O cliente não força status recebido nem recebe mensagem de pagamento confirmado.
- Cards do cliente e da barbearia consultam cobranças pelo identificador exato do agendamento. O perfil de barbeiro não faz consultas financeiras.
- O proprietário/admin confirma dinheiro recebido em ação própria, com valor e confirmação explícita. A operação só aparece para intenção presencial pendente, sem confirmação anterior e com preço conhecido.
- O modal de confirmação usa o padrão de foco, Tab e Escape; durante envio impede fechar ou reenviar.
- Cada recarga da lista do cliente ou proprietário atualiza também as cobranças, mesmo quando os identificadores dos agendamentos não mudam. Pagamento confirmado em qualquer método bloqueia uma nova confirmação presencial.
- `npm test`: 27 testes aprovados. `npm run lint`: nenhum erro ou aviso. `npm run build`: concluído sem avisos; maior JavaScript 253,49 kB.
- Nenhum pagamento real foi executado nas verificações do frontend. Persistência e idempotência são verificadas nos testes isolados do backend e na QA integrada.

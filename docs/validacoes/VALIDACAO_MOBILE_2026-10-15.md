# Validação do Cortaê Mobile — 15/10/2026

Aplicativo React Native implementado em `Cortae_mobile-main`, usando Expo SDK 57, Expo Router e a API Flask existente. As áreas são cliente e proprietário da barbearia; não há telas de administrador ou de profissional no app. Instruções: [README do aplicativo](../../Cortae_mobile-main/README.md).

## Entrega

São 42 telas funcionais: seis públicas, quinze do cliente e vinte e uma da barbearia. Existem também três layouts, um redirecionamento inicial e a tela de rota desconhecida, totalizando 47 arquivos de rotas.

O visual usa a referência mobile do Figma: base escura, laranja, Montserrat e navegação inferior. Estabelecimentos e produtos aplicam o destaque configurado pela barbearia. Componentes de formulário, seleção, senha visível, feedback, imagens, estados vazios e carregamento são compartilhados. Listagens de descoberta e produtos usam renderização virtualizada.

| Área | Implementação |
|---|---|
| Conta | Login, cadastro, código de confirmação, recuperação, perfil com telefone e senha visível, termos, configuração da API |
| Cliente e agenda | Descoberta, estabelecimento, serviços, profissional, horários, resumo, reserva, espera, cancelamento, remarcação, histórico e avaliação elegível |
| Visagismo | Selfie/galeria, análise, uma recomendação com motivo e características, simulação opcional, catálogo e escolha do corte no atendimento |
| Compras | Loja geral e integrada ao salão, produto e variações, favoritos, desejos, carrinho por loja, cupom, endereço, cotação, resumo, pedido e histórico |
| Barbearia | Dashboard, agenda, bloqueios, criação de atendimento, equipe/serviços, preços, turnos, clientes e observações |
| Gestão | Caixa, despesas, categorias, recebimentos divididos, comissões manuais, ranking, avaliações, metas e relatórios |
| Loja do proprietário | Produtos, imagens por URL, estoque, variações, fornecedores, cupons, promoções, lançamentos, pedidos, vendas, remetente e rastreio |

## Backend e sessão

- Login com `X-Cortae-Client: mobile` retorna Bearer somente para cliente e proprietário. O login web mantém o cookie HttpOnly. Administrador e profissional não podem usar o login mobile.
- Token nativo fica no SecureStore. Perfil armazenado só libera a área privada após validação no servidor. Respostas atrasadas de login, perfil, persistência e 401 não podem restaurar uma sessão encerrada ou apagar uma nova sessão.
- Imagens privadas de visagismo recebem Authorization apenas na origem e nos caminhos protegidos da API configurada. URLs externas não recebem o token.
- Novas operações de perfil público e equipe são restritas ao estabelecimento autenticado. A edição pública não recebe credenciais financeiras nem substitui a equipe completa.
- A consulta de cobrança restaura o código original do provedor. Antes de confirmar um pagamento localmente, valida identificação e valor finito/positivo contra o histórico. A tela reapresenta cobrança existente por GET e evita gerar novamente uma cobrança integral após recebimento parcial.
- Contratos explícitos das cinco novas operações foram acrescentados ao OpenAPI restrito ao administrador. O Help continua descobrindo os handlers registrados. As restrições de acesso à documentação foram preservadas.

## Testes automatizados executados

| Verificação | Resultado final |
|---|---|
| `npm run lint` | Aprovado |
| `npm run typecheck` | Aprovado |
| `npm test` | 29 aprovados, zero falhas |
| Prettier em `src` e `tests` | Aprovado |
| `npx expo-doctor` | 21/21 verificações aprovadas |
| Exportação Android | Aprovada; bundle Hermes de aproximadamente 3,9 MB |
| Backend: `python -m unittest discover -s tests` | 321 casos: 280 aprovados, 41 ignorados, zero falhas |

Os 29 testes mobile incluem nove regras de escolha de corte/estoque/pagamento, quatro regressões de recuperação de QR e dezesseis regressões da sessão. Incluem respostas atrasadas, persistência concorrente e logout sem conexão: no nativo, a limpeza local conclui mesmo se o servidor falhar; na web, a falha de remoção do cookie continua sendo reportada. A suíte backend inclui 32 novos testes específicos de login, perfil, equipe e consulta de cobrança. Os testes ignorados incluem integrações Firebird que exigem ativação explícita e condições específicas do Windows; não representam operações aprovadas.

A primeira execução geral encontrou ausência dos contratos das cinco novas operações no OpenAPI. Os contratos foram implementados e a suíte completa foi repetida com o resultado acima. Mensagens de falha simulada de provedor, auditoria e autenticação nos logs são produzidas pelos casos negativos dos testes.

## Integração HTTP com banco isolado

Foi usado um clone externo do Firebird, API em `127.0.0.1:5002`, contas sintéticas `example.invalid`, worker de notificações desativado, SMTP bloqueado e provedores financeiros/frete simulados. Nenhum pagamento real, crédito de IA, envio de etiqueta ou mensagem foi executado.

- Gestão: consultas de agenda, equipe, clientes, caixa, comissões, ranking, metas, relatórios, pedidos e perfil; operações sintéticas de produto, fornecedor, variação, estoque, cupom, despesa, recebimento manual e perfil. Evidências em `owner-api-qa.json` e `owner-commercial-qa.json`.
- Cliente: consultas protegidas, bloqueio de perfil alheio, catálogo, favoritos/desejos, carrinho, resumo e pedido sintético criado/cancelado. O teste inicial teve 33/34 verificações aprovadas: a verificação restante esperava revogação de JWT no logout, que o backend atual não implementa. Esse limite é descrito abaixo, sem ocultar o resultado inicial.
- Agenda positiva adicional: 15/15 operações HTTP aprovadas. Reserva persistida, tentativa conflitante recusada com 409, entrada na espera, cancelamento, transição para aviso pendente e saída da espera. A entrega do e-mail não foi testada. Houve ajustes no script de QA para enviar JSON vazio em DELETE com Content-Type JSON e limpar uma inscrição sintética anterior; não foi necessário alterar o produto para esses ajustes.

## Android

Verificação em emulador do Android Studio, AVD Medium_Phone, usando Expo Go SDK 57 e o código React Native. A API de teste foi selecionada pela própria tela Configurar conexão. O aplicativo não usa uma página web embutida como substituto da interface nativa.

Confirmados visualmente: conexão com a API, login de cliente, descoberta, agenda, loja, seletor de estabelecimento, imagens de produtos, detalhes, preço, seleção de variação e estoque, perfil com telefone e senha visível, logout retornando ao login e login da barbearia com dashboard próprio. No proprietário, também foram abertas agenda com filtros, loja com custo/margem/estoque, menu de gestão e equipe/serviços. As imagens externas que não carregam apresentam um estado de imagem indisponível.

Esta verificação é uma amostra dos fluxos no dispositivo. A existência das 42 telas e os testes HTTP não significam que cada combinação de interação foi executada manualmente. Não foi gerado APK de distribuição nem feita publicação na Play Store. iOS e aparelho físico não foram testados.

## Limites e pendências externas

- Pagamento real, entrega de e-mail, geração por IA e postagem física permanecem sem validação real nesta etapa.
- `ARKHEPIX:` é código interno Arkhé; um QR com esse conteúdo não equivale a Pix bancário interoperável. O app explicita essa diferença. Outras falhas financeiras preexistentes do POST de cobrança, registradas na auditoria de 14/10, não são consideradas resolvidas por esta entrega. As proteções do aplicativo não substituem validações no servidor.
- O logout elimina a sessão e o token do aplicativo. JWT anteriormente emitido continua válido no backend até sua expiração de duas horas; revogação imediata exige suporte adicional no servidor.
- A política de termos/taxa depende dos dados e da configuração do responsável no backend. Política em rascunho não é exibida como taxa ativa.
- Melhor Envio depende de token, endereço, conta e permissões. Não há compra automática de etiquetas. WhatsApp permanece fora do escopo.
- `npm audit` final: 29 alertas na árvore de dependências, sendo 19 altos e 10 moderados, zero críticos. Foram aplicadas correções compatíveis. As sugestões restantes envolvem dependências sem correção disponível ou mudanças incompatíveis do SDK; não foi usado `--force`. Expo Doctor aprovado não equivale a ausência de vulnerabilidades. Resolver esses alertas e validar o build de distribuição é necessário antes de publicar.
- Produção exige API HTTPS e URL pública do site configurada para compartilhamento de links. Segredos de Figma, pagamento e banco não são incluídos no aplicativo.

## Evidências e preservação

Evidências locais: `C:\Users\mathe\Documents\Backups-Cortae\mobile-20261015`. Incluem backup original `mobile-original.zip`, hashes, dez arquivos antigos arquivados em `legacy-source`, testes HTTP, logs, auditoria npm, exportação Android, capturas e revisão independente `FINAL_MOBILE_REVIEW.md`.

O emulador de demonstração foi conectado ao clone de QA na porta 5002. Esse ambiente contém contas e produtos fictícios; não é o banco de uso normal. Para usar os próprios dados, inicie a API atualizada e altere Configurar conexão para `http://10.0.2.2:5000`. A troca encerra a sessão local. Os processos da demonstração foram registrados em `qa-processes.json` na pasta de evidências, com PID, comando e data de criação.

Os arquivos substituídos foram movidos para backup externo, sem exclusão irreversível. Os testes de integração com escrita usaram exclusivamente os bancos descartáveis externos. A implementação não utilizou as credenciais Figma enviadas na conversa.

# Aplicativo Android com backend Python de 32 bits — 19/10/2026

O aplicativo foi executado no Expo Go, no emulador Android 17/API 37
`Medium_Phone`. O backend real usou Python 3.12.10 x86, na porta 5001,
com Firebird principal e auditoria isolados. Nenhum dado de cliente real foi
copiado: as bases receberam somente estrutura e cadastros sintéticos.

## Resultado observado

- Login de cliente e de proprietário, sessão, navegação e logout funcionaram.
- Foram percorridas 15 rotas de cliente e 21 de proprietário autenticados,
  com capturas e inspeção de UI; nenhum erro fatal foi encontrado.
- Compra de produto, aplicação de cupom de 10%, leitura e aceite dos termos
  e confirmação criaram um pedido de R$ 26,91, aguardando pagamento.
- Agendamento de serviço de R$ 40,00 criou atendimento na agenda do proprietário.
- Reposição de uma unidade de estoque foi registrada e confirmada pela interface.
- Cancelamento do atendimento foi confirmado pela interface.
- As 17 verificações HTTP iniciais responderam como esperado. A inspeção dos
  bancos confirmou pedido, reserva de estoque, cupom e auditoria após a compra.
- Os e-mails ficaram pendentes; pagamentos, SMTP e outras conexões externas
  estavam bloqueados no ambiente isolado. Não houve cobrança nem mensagem real.

## Erro corrigido

A agenda do proprietário mostrava o profissional sem o nome do serviço.
A API retorna `servicos` como IDs e `servicos_nomes` como textos. A tela tentava
ler propriedades `nome` dos IDs. Agora apresenta `servicos_nomes`, conforme o
contrato da API e a tela de agendamentos do cliente.

Essa última alteração não foi executada novamente no emulador: o usuário
interrompeu a repetição dos testes e pediu publicação no GitHub. As capturas
registram o defeito antes da correção. Os resultados anteriores de 76 testes,
lint e análise de 90 fontes do mobile estão no relatório de Python de 32 bits.

## Limites e evidências

Esta execução usou Expo Go, não um APK de produção assinado. Cadastro e
recuperação de senha tiveram inspeção de interface; não houve recuperação real
por e-mail. As imagens sintéticas eram locais ao ambiente de QA; a conexão real
com o Drive foi investigada separadamente.

As capturas, dumps de UI, logs e scripts ficam fora do Git em
`C:/Users/mathe/Documents/Backups-Cortae/mobile-python32-20261019`.
`routes-client-real.json` e `routes-owner-real.json` contêm as rotas finais.
`owner-auth-driver-preliminary.json` é uma tentativa inválida do driver de
digitação; não integra os resultados aprovados.

[Validação do runtime Python de 32 bits](PYTHON_32_BITS_2026-10-19.md).

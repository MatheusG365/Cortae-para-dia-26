# Documentação do Cortaê

Esta pasta reúne documentação de integração e relatórios históricos. A aplicação não depende desses arquivos para executar.

## Auditoria mais recente

[Imagens em outra instalação — 20/10/2026](validacoes/IMAGENS_PORTAVEIS_2026-10-20.md): 64 imagens públicas com leitura sem OAuth, 27 referências privadas protegidas e verificação visual numa cópia separada do projeto.

[Firebird 4.0.4.3010 — 19/10/2026](validacoes/FIREBIRD_4_0_4_2026-10-19.md): dois bancos restaurados no motor exato de 32 bits, regras recompiladas, dados preservados e snapshots ODS 13.0.

[Cartão virtual Arkhé — 19/10/2026](validacoes/ARKHE_CARTAO_2026-10-19.md): agendamentos e marketplace no site/aplicativo, migração compatível com ODS 13.0, bloqueio de cobrança repetida e snapshots sem credenciais. Inclui limites da validação e situação da revogação anterior.

[Drive central e WAHA — 19/10/2026](validacoes/DRIVE_WAHA_2026-10-19.md): autorização Drive renovada, 19 imagens reais restauradas, 44 testes focados e instalação WSL/Docker aguardando reinício Windows para iniciar WAHA.

[Android com Python de 32 bits — 19/10/2026](validacoes/MOBILE_ANDROID_PYTHON32_2026-10-19.md): execução real no emulador, compra e agendamento isolados, 36 rotas autenticadas e correção da agenda.

[Python de 32 bits — 19/10/2026](validacoes/PYTHON_32_BITS_2026-10-19.md): validação obrigatória de arquitetura, instalação limpa, testes de backend/Firebird, frontend e mobile.

[Help e documentação da API — 17/10/2026](validacoes/HELP_DRIVE_2026-10-17.md): novo guia de imagens no Help, contratos de upload e mídia, mobile e validação do acesso ADM.

[Migração completa de imagens — 17/10/2026](validacoes/GOOGLE_DRIVE_IMAGENS_COMPLETA_2026-10-17.md): 77 arquivos no Drive, remoção das pastas locais, verificações HTTP, site e aplicativo.

[Armazenamento de imagens no Google Drive — 16/10/2026](validacoes/GOOGLE_DRIVE_IMAGENS_2026-10-16.md): implementação inicial e primeira ativação.

[Help administrativo com mobile — 15/10/2026](validacoes/HELP_MOBILE_2026-10-15.md): catálogo de telas, fluxos, fontes TS/TSX, vínculos com a API e verificações de acesso exclusivo do ADM.

[Confirmações e conexão automática mobile — 15/10/2026](validacoes/MOBILE_CONEXAO_DIALOGOS_2026-10-15.md): diálogos visuais, detecção do servidor, acesso pela rede e resultados da nova rodada de testes.

[Validação do aplicativo mobile — 15/10/2026](validacoes/VALIDACAO_MOBILE_2026-10-15.md): implementação React Native, testes automatizados, verificação no emulador Android e limites das integrações.

[Auditoria de rotas e pagamentos — 14/10/2026](validacoes/AUDITORIA_ROTAS_2026-10-14.md): cobertura das rotas, funcionalidades verificadas, falhas reproduzidas, integrações parciais e evidências. Os resultados descrevem a versão e o ambiente auditados nessa data.

## Integrações

- [Imagens no Google Drive](integracoes/GOOGLE_DRIVE_IMAGENS.md): OAuth do servidor, estrutura de pastas, verificação e migração das imagens locais.
- [WhatsApp pelo WAHA](integracoes/WHATSAPP_WAHA.md): serviço privado, configuração central, QR e CLI de envio explícito.
- [Arkhé](integracoes/ARKHE_INTEGRACAO.md): documentação da integração e do escopo de comissões. Consulte também os limites de pagamento registrados na auditoria mais recente.

## Histórico de validações

Esses relatórios registram etapas anteriores de implementação. Testes aprovados em uma etapa não comprovam que todas as integrações reais ou casos extremos estejam funcionando. A auditoria acima registra os problemas descobertos posteriormente.

| Área | Relatório |
|---|---|
| Validação inicial | [Validação](validacoes/VALIDACAO.md) |
| Agenda e equipe | [Agenda e equipe](validacoes/AGENDA_EQUIPE_VALIDACAO.md) |
| Gestão do backend | [Gestão — backend](validacoes/GESTAO_BACKEND_VALIDACAO.md) |
| Gestão completa | [Gestão completa](validacoes/GESTAO_COMPLETA_VALIDACAO.md) |
| Marketplace | [Marketplace](validacoes/MARKETPLACE_VALIDACAO.md) |
| Recursos comerciais | [Comercial](validacoes/COMERCIAL_VALIDACAO.md) |
| Ranking e avaliações | [Ranking e avaliações](validacoes/RANKING_AVALIACOES_VALIDACAO.md) |
| Termos e taxa | [Termos e taxa](validacoes/TERMOS_TAXA_VALIDACAO.md) |
| Visagismo | [Visagismo](validacoes/VISAGISMO_VALIDACAO.md) |
| Limpeza do código | [Limpeza](validacoes/LIMPEZA_VALIDACAO.md) |
| Documentação e administração | [Documentação ADM](validacoes/ADMIN_DOCUMENTACAO_VALIDACAO.md) |

[Voltar às instruções do projeto](../README.md).

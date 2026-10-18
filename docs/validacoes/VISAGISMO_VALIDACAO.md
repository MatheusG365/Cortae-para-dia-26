# Validação do visagismo

Verificação concluída em 10/10/2026.

## Comportamento corrigido

- A análise retorna exatamente um corte ativo do catálogo, mantendo ID e nome cadastrados.
- O resultado apresenta motivo específico, cabelo atual e seis características observáveis: formato do rosto, textura, comprimento, densidade, linha frontal e barba. Características encobertas são descritas como não visíveis.
- Respostas inválidas, foto inadequada, ausência de corte viável e integração indisponível não produzem recomendações aleatórias nem sessões de sucesso.
- A geração envia a foto do cliente primeiro e a referência do corte depois, quando acessível. O prompt distingue a pessoa do estilo e restringe as alterações ao serviço contratado.
- Trocar foto, cor, corte ou serviços invalida a simulação anterior. Respostas atrasadas de outro fluxo são ignoradas. Corte com pintura exige corte e cor; pintura isolada continua disponível.
- Categorias antigas masculino/feminino continuam editáveis. URLs externas também funcionam na exibição dos agendamentos. Substituir uma referência por URL preserva o arquivo anterior.

## Catálogo e preservação

As 46 referências ativas foram conferidas no navegador e pelo transporte HTTPS usado em produção. O manifesto `docs/referencias/catalogo_cortes.json` contém URL e página de origem; os arquivos de referência não foram adicionados ao projeto.

Foram revisadas visualmente as associações e ajustadas as referências de Flattop, Afro e French Bob. Cada nova URL coube no campo IMAGEM_ROTA.

A atualização alterou apenas IMAGEM_ROTA. Comparação de todas as outras colunas das 47 linhas do catálogo confirmou valores idênticos antes e depois. A segunda execução de conferência encontrou zero alterações pendentes.

Diário com valores anteriores:
`C:\Users\mathe\Documents\Backups-Cortae\referencias-cortes-20261010-224648-578648.json`.

Snapshot do código anterior:
`C:\Users\mathe\Documents\Backups-Cortae\visagismo-antes-20261010.zip`.

## Evidências

- Backend: 75 testes aprovados, incluindo 48 testes independentes de visagismo e duas regressões adicionais para categorias antigas e referências de agendamentos. Os testes automatizados usam dados sintéticos e provedores simulados.
- Frontend: 19 testes aprovados; lint sem avisos; build de produção concluído.
- Navegador: recomendação única, motivo e características, foto e referência, simulação, aviso de referência ausente, troca de cor invalidando o resultado, coloração isolada, resposta vazia rejeitada, Escape e retorno de foco.
- Layout em largura de 375 px: sem rolagem horizontal no resultado conferido.
- Integração real: uma análise com catálogo e foto públicos retornou um único corte e seis características. Outra análise e edição real aplicaram o corte Militar (Buzz Cut), ID 41, usando descrição cadastrada e duas imagens distintas. PNG 1024 × 1024 conferido visualmente: corte curto aplicado ao cliente, preservando sua pessoa, barba e cenário, sem copiar a pessoa da referência.
- Nenhuma foto privada ou sessão pessoal foi usada nas chamadas reais de teste. Os artefatos de teste ficaram fora do projeto, em `C:\Users\mathe\MegaBrain\.mega_brain\tasks\visagismo-live-check`.
- Reinício final concluído: API pronta, banco principal e banco de auditoria disponíveis, frontend HTTP 200 e catálogo servido com 46 referências HTTPS. Sistema deixado em execução em `http://127.0.0.1:5173/`.

## Revisão e limites

A revisão independente forneceu os testes de comportamento. A revisão local adicional questionou duas proteções intencionais: recusar substituição de referências existentes e retornar HTTP 422 quando não há corte viável. O coordenador verificou ambas contra o contrato e manteve as proteções. A aprovação corresponde ao escopo testado.

A aparência de uma geração depende da foto, da referência e do modelo; um caso real aprovado não garante resultados idênticos para todas as pessoas. URLs de terceiros podem mudar; o sistema informa a ausência da referência. SMTP real e implantação pública não fizeram parte desta verificação.

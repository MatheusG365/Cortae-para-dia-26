# Help administrativo com documentação mobile

Data: 15/10/2026.

## Entrega

A página `/help` do site reúne agora o aplicativo React Native, além do site e da API. O administrador continua usando o site; não foi criado painel administrativo no aplicativo.

O catálogo atual contém 36 páginas web, 147 rotas da API e 43 rotas mobile: 41 telas funcionais, o redirecionamento inicial e a página não encontrada. Layouts e dependências aparecem entre os arquivos, sem contar como telas adicionais. As rotas mobile são identificadas pela origem e não confundidas com URLs do site.

A visão geral explica navegação, sessão, conexão automática e cinco jornadas: acesso, agendamento do cliente, compra por loja, atendimento/equipe e operação comercial da barbearia. Cada tela informa funcionamento, parâmetros, perfil autorizado, arquivos TS/TSX e APIs relacionadas. Os filtros incluem origem, área do aplicativo, método e busca textual. Os vínculos de API abrem documentos dentro do Help, sem executar operações de negócio.

O catálogo lê os caminhos existentes em `Cortae_mobile-main/src/app`. A documentação das funcionalidades fica em `Backend/mobile_help.py`; novas telas recebem descrição básica até que seus detalhes sejam cadastrados nesse mapa. O próprio Help também explica essa organização.

## Acesso e fontes

O backend mantém a verificação de administrador antes de consultar catálogo ou código. Fontes mobile permitidas ficam dentro de `src`, são solicitadas por IDs cadastrados e retornadas como texto, sem cache. Configurações, dados, assets, dependências instaladas e caminhos por links não são disponibilizados. A sanitização de credenciais foi ampliada para declarações TypeScript, inclusive valores após comentários e em múltiplas linhas.

Não foi adicionada opção de configurar conexão ao aplicativo. O Help explica a conexão automática durante o desenvolvimento e a configuração pela equipe na publicação.

## Validação

| Verificação | Resultado |
|---|---|
| Backend completo: `python -m unittest discover -s tests` | 337 testes: 296 aprovados, 41 ignorados; nenhuma falha |
| Help no backend: `tests.test_admin_help` e `tests.test_admin_help_mobile` | 26 testes: 25 aprovados e 1 ignorado por indisponibilidade de symlink no Windows |
| Frontend: `npm test` | 98 aprovados |
| Frontend: `npm run lint` | Aprovado |
| Frontend: `npm run build` | Aprovado |
| Revisão independente | 5 testes aprovados, sem achados pendentes |
| Navegador com sessão ADM de teste | Filtros cliente/barbearia, fonte TSX, dependência de implementação, vínculo para documentação da API e visão geral conferidos; nenhum erro de console observado |

Os testes novos cobrem a árvore real de telas, rotas futuras, dependências TS/TSX, vínculos com handlers existentes, autorização, restrições de leitura e sanitização. A revisão identificou e corrigiu omissão de subpastas no catálogo, redação de credenciais após comentários e descrições divergentes das funcionalidades existentes.

A conferência visual utilizou banco clonado fora do projeto e usuário sintético. Não foram realizados pagamentos, reservas, compras de etiquetas, geração de imagens ou envios de e-mail. Esta entrega documenta a implementação; não certifica a operação de serviços externos. Nenhum código do aplicativo foi alterado nesta etapa.

Evidências locais: `C:\Users\mathe\Documents\Backups-Cortae\help-mobile-20261015` contém o relatório independente, resultados dos testes e `help-mobile.png`.

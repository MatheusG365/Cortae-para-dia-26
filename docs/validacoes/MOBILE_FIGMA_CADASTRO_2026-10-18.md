# Mobile: referência Figma e cadastro exclusivo de cliente — 18/10/2026

Complementa a conversão JavaScript descrita em `MOBILE_JAVASCRIPT_2026-10-18.md`.

## Layout

Referência consultada visualmente: página APP do [Figma Cortaê](https://www.figma.com/design/RdmKbXJ0E6dKOeZwq52aQv/Corta%C3%AA?node-id=399-1398), incluindo os quadros [Login Screen](https://www.figma.com/design/RdmKbXJ0E6dKOeZwq52aQv/Corta%C3%AA?node-id=417-3111) e [Signup Screen](https://www.figma.com/design/RdmKbXJ0E6dKOeZwq52aQv/Corta%C3%AA?node-id=417-3163).

- Login reconstruído com foto, logo transparente, legenda, campos compactos, recuperação à direita, botão laranja e cadastro contornado. Retirados o cabeçalho promocional e o cartão grande que não estavam no quadro de referência.
- Cadastro usa o mesmo componente de composição fotográfica, título sobre a foto e formulário sem cartão externo. Usa os recursos existentes na API; a foto atual é reutilizada entre login e cadastro. Confirmação de senha e termos permanecem para cumprir as regras do sistema. Gênero é opcional e continua editável no perfil do cliente.
- Lista de barbearias passou a usar título, busca e cards fotográficos compactos conforme a referência; serviços usam cards selecionáveis com preço e ícone de seleção.
- Paleta compartilhada usa preto/cinza neutros e laranja; títulos, botões e cartões das páginas adicionais ficaram mais compactos. Cores específicas dos estabelecimentos continuam nos fluxos correspondentes.
- `AuthScreen.jsx` usa `expo-linear-gradient` compatível com SDK 57. Na conferência nativa foi corrigida a propriedade de preenchimento absoluto para `StyleSheet.absoluteFill`, disponível no React Native instalado. Há regressão automatizada para foto e degradê cobrirem o quadro.
- Fotos e logo continuam em `/midia/mobile/*`, servidos pelo Drive através da API. Nenhuma chave, ID do Drive ou nova foto local foi adicionada ao aplicativo.
- Há 90 fontes JS/JSX, incluindo o novo componente compartilhado de autenticação; nenhuma fonte TypeScript em `src`.

As telas foram adaptadas à implementação existente, com campos extras exigidos pelo site. Não se declara cópia integral de todas as páginas nem identidade de todas as imagens do arquivo Figma; as páginas comerciais/gestão adicionais não possuem todos os quadros correspondentes nesse modelo.

## Permissões

- O cadastro mobile envia sempre `tipo: 1`, mesmo se um objeto de entrada tentar fornecer outro perfil. Não existe seletor de cliente/barbearia.
- `POST /cadastro` agora exige administrador autenticado para criar barbearia (`tipo: 2`) ou administrador (`tipo: 0`). A autorização ocorre antes de abrir a conexão de cadastro, gravar usuário ou enviar e-mail. A validação da sessão pode consultar o banco para revalidar a conta.
- A rota web `/cadastrobarbearia` está protegida por `RequireAuth tipos={[0]}`.
- Login mobile continua somente para cliente e barbearia já cadastrada. Administrador e profissional são recusados, sem Bearer e sem sessão mobile. Nenhuma tela ADM foi adicionada ao app.
- Help mobile, Help do site, documentação OpenAPI e README atualizados. OpenAPI passou a 2.3.0.

## Verificação final

| Verificação | Resultado |
|---|---|
| Mobile: testes de regras, sessão, pagamento, cadastro e fundo nativo | 70 aprovados |
| Mobile: lint e `typecheck` (alias de análise JS/JSX/imports) | Aprovados |
| Expo Doctor | 21/21 aprovados |
| Exportação Android/Hermes | Aprovada |
| Backend completo | 508 executados: 463 aprovados, 45 ignorados por requisitos específicos/opt-in |
| Site: testes | 129 aprovados |
| Site: lint e build | Aprovados |
| API em execução: cadastro público tipos 0 e 2 | 403, com dados fictícios; nenhum usuário criado |
| API em execução: health / OpenAPI sem login | 200 / 401 |

O teste de contexto de visagismo de outra conta dependia indevidamente de os termos locais estarem em rascunho: com termos publicados, retornava 428 antes de alcançar a validação em teste. Foi isolada a pré-condição de aceite nesse teste. A implementação continua exigindo aceite; os testes próprios de termos permanecem ativos.

No emulador Android foram conferidos login, carregamento da foto/logo pela API e cadastro sem seleção de perfil. Não foi criado cadastro real nem registrado aceite jurídico para produzir as capturas. A engrenagem flutuante é uma ferramenta do Expo Go, exterior às telas do Cortaê; não é acesso ADM.

Os 29 alertas de dependências relatados na validação JavaScript permanecem registrados naquele documento; passar nos testes ou no Expo Doctor não significa ausência de vulnerabilidades. Não foram executados pagamentos reais nem builds iOS/assinatura de APK nesta etapa.

Evidências: `C:\Users\mathe\Documents\Backups-Cortae\mobile-figma-20261018`, incluindo capturas Android, logs e exportação Hermes. Credenciais e bancos permanecem fora do Git.

# Frontend Cortaê

Interface React para cadastro, autenticação, barbearias, visagismo, agendamentos e administração.

## Executar

```powershell
npm ci
npm run dev
```

Abra `http://localhost:5173`. O backend deve estar na porta 5000.
O Vite encaminha `/api` para `http://127.0.0.1:5000`, incluindo imagens em `/api/uploads`.

## Configuração

A configuração padrão usa a mesma origem (`/api`). Se necessário, copie `.env.example` para `.env.local` e ajuste `VITE_API_URL` para a URL do backend. Reinicie o Vite após mudar variáveis de ambiente. Uma origem diferente exige a configuração correspondente de CORS e cookies no backend.

Em produção, publique `dist` com fallback das rotas para `index.html` e encaminhe `/api` para o backend, removendo o prefixo `/api`. `npm run preview` permite verificar o build local e herda o proxy de desenvolvimento; mantenha o backend na porta 5000.

## Verificar

```powershell
npm test
npm run lint
npm run build
```

Os testes verificam JSON, FormData, cookies, cancelamento, respostas binárias e falhas de rede/HTTP/resposta. O lint rejeita avisos. O build divide as páginas em arquivos carregados sob demanda.

## Convenções

- Requisições passam por `src/services/api.js`; mensagens de erro usam `mensagemDaApi` e imagens usam `urlDaApi`.
- `apiFetch(endpoint, options)` lê JSON; o terceiro argumento `'blob'` retorna arquivos binários e mantém o tratamento de erros HTTP.
- Variáveis visuais compartilhadas ficam em `src/index.css`; os módulos CSS preservam a aparência de cada página.
- `MensagemCard` e `ModalConfirmacao` compartilham foco, Tab, Escape e retorno do foco por `useDialog`.


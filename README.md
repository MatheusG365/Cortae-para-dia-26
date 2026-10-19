# Cortaê · JOHN

Frontend React/Vite e API Flask com Firebird principal e banco separado de auditoria.

## Organização dos arquivos

- `Backend/`: API, configuração e banco de dados local.
- `Frontend/`: interface do sistema.
- `Cortae_mobile-main/`: [aplicativo React Native para cliente e barbearia](Cortae_mobile-main/README.md), com instruções de execução no Android Studio.
- `docs/`: [índice da documentação](docs/README.md), integrações e relatórios de validação.
- `.runtime/`: logs e registro dos processos iniciados pelos atalhos; conteúdo local, ignorado pelo Git.
- `.gitignore`: regras para não publicar dependências, segredos, bancos e arquivos gerados.

Os três comandos de uso ficam na raiz: `Configurar-Cortae.cmd`, `Iniciar-Cortae.cmd` e `Parar-Cortae.cmd`. Cada `.cmd` abre o `.ps1` de mesmo nome, que contém a implementação. Os pares não são cópias redundantes e precisam permanecer juntos.

Os relatórios não são necessários para executar a aplicação. Foram mantidos em `docs/validacoes/` como histórico. Consulte a [auditoria de 14/10/2026](docs/validacoes/AUDITORIA_ROTAS_2026-10-14.md) para os problemas e limites encontrados nessa execução; validações anteriores não substituem esse resultado.

## Iniciar no Windows

Requisitos: **Python 3.12 ou superior de 32 bits (Windows x86)**, Node.js 22+ e servidor Firebird 5 disponível. Os arquivos `Backend/CORTAE.FDB` e `Backend/LOG_CORTAE.FDB` precisam estar acessíveis ao Firebird.

1. Execute `Configurar-Cortae.cmd` para instalar as dependências nas versões verificadas.
2. Preencha `Backend/.env` a partir de `.env.example` se ainda não existir. Informe banco, senha, chave da aplicação e credenciais das integrações utilizadas.
3. Execute `Iniciar-Cortae.cmd`.

O instalador conserva um `Backend/.venv` válido de 32 bits. Ao criar ou substituir o ambiente,
prefere `py -3.12-32`, verifica os outros interpretadores disponíveis e rejeita Python de 64 bits.
Para indicar o executável instalado, execute na raiz:

```powershell
.\Configurar-Cortae.ps1 -PythonPath 'C:\caminho\Python312-32\python.exe'
.\Backend\.venv\Scripts\python.exe .\Backend\runtime_check.py
```

Um ambiente incompatível é preservado em `.runtime/python-environments/venv-backup-*`, com o
caminho informado no terminal. Se a criação falhar, o instalador restaura o ambiente anterior;
tentativas incompletas permanecem nessa mesma pasta para inspeção. Não altera Python global,
configurações existentes nem bancos. Os iniciadores e a aplicação recusam um processo de 64 bits,
inclusive ao executar `main.py` manualmente ou importar a aplicação WSGI.
As dependências completas, incluindo imagens e Google Drive, ficam em `Backend/requirements-lock.txt`;
o instalador executa `pip check` após a instalação.

Acesse [Cortaê](http://127.0.0.1:5173), [saúde da API](http://127.0.0.1:5000/health) e [documentação](http://127.0.0.1:5000/docs).

O administrador encontra a central técnica em `/help`, digitando o endereço no site. Ela documenta as páginas web, as rotas da API e o aplicativo mobile: telas públicas, cliente, gestão da barbearia, fluxos e código associado. O mobile utiliza a mesma API e não possui painel de administrador; sua documentação é consultada pelo ADM no site. O catálogo e a leitura de código continuam exigindo sessão de administrador no backend.

As fotos enviadas pelo site e pelo aplicativo usam o armazenamento compartilhado do backend: conversão para WebP, referência no Firebird e arquivo privado no Google Drive. A ativação exige autorização OAuth no servidor; uma chave de API sozinha não autoriza imagens privadas. A hospedagem pode guardar a autorização completa em `GOOGLE_DRIVE_CREDENTIALS_JSON`, sem caminhos locais de credenciais nos aparelhos. Consulte o [guia de configuração e migração](docs/integracoes/GOOGLE_DRIVE_IMAGENS.md). O provedor Drive não usa arquivos locais como alternativa.

O [WhatsApp pelo WAHA](docs/integracoes/WHATSAPP_WAHA.md) dispõe de cliente e CLI no backend, com instalação em `compose.waha.yaml`. Configure a chave privada no servidor e faça o pareamento pelo QR. Começa desativado; notificações automáticas não foram adicionadas.

Para encerrar, execute `Parar-Cortae.cmd`. Ele encerra apenas os processos registrados deste projeto, verificando o comando e a data de início. Portas ocupadas por outros processos geram aviso na inicialização. Os registros de execução ficam em `.runtime/`. Uma instância ainda ativa deste projeto impede outra inicialização, mesmo em outras portas. Registros residuais após uma interrupção são preservados em `.runtime/processes-anterior-*.json`, sem bloquear uma nova execução nem encerrar processos de outro programa.

## Comandos manuais

Backend, a partir de `Backend/`:

```powershell
.\.venv\Scripts\python.exe main.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Frontend, a partir de `Frontend/`:

```powershell
npm run dev
npm run lint
npm test
npm run build
```

Por padrão, a API usa a porta 5000 e o frontend a 5173. O iniciador respeita `PORT` e `API_HOST` do ambiente ou de `Backend/.env`. O frontend envia `/api` pelo proxy Vite ao backend; o iniciador ajusta esse proxy à porta da API. Configure `VITE_API_URL` para outra implantação.

## Acesso na mesma rede

O backend e o frontend escutam em `0.0.0.0` por padrão. Assim, trocar o IP do computador não exige alterar o código: abra `http://<IP-atual-do-computador>:5173` no navegador do outro dispositivo. O proxy mantém as requisições do site na mesma origem. O celular e o computador precisam estar na mesma rede, com as portas permitidas pelo firewall do sistema; o iniciador não altera o firewall.

O aplicativo em desenvolvimento identifica o computador que executa o Expo. Inicie o Expo em modo LAN, com a API disponível na porta 5000; consulte os detalhes no [README do aplicativo](Cortae_mobile-main/README.md). Um aplicativo publicado usa um domínio público estável, configurado na compilação. Links enviados por e-mail continuam usando `PUBLIC_FRONTEND_URL`, que precisa ser um endereço acessível aos destinatários.

Para outras portas, use `PORT` em `Backend/.env` ou os parâmetros do iniciador:

```powershell
.\Iniciar-Cortae.ps1 -ApiPort 5001 -FrontendPort 5174
```

Para restringir explicitamente ao próprio computador, configure `API_HOST=127.0.0.1` e execute `Iniciar-Cortae.ps1 -FrontendHost 127.0.0.1`. A mudança de rede não altera a autenticação nem as permissões da API.

## Configuração e auditoria

As credenciais ficam em `Backend/.env`, ignorado pelo controle de versão. Variáveis do ambiente prevalecem sobre o arquivo. Os nomes padrão dos bancos são relativos ao backend, permitindo mover a pasta do projeto.

Cada campo efetivamente alterado gera um histórico em `LOG_ALTERACAO`, com usuário, IP, ação, registro, valores anterior e posterior. Senhas, tokens e segredos são substituídos por `[PROTEGIDO]`.

`/health` verifica o banco principal e a tabela de auditoria. `LOG_OBRIGATORIO=false` permite que a operação continue quando o log estiver indisponível; essa falha é registrada no servidor. Com `true`, a falha é propagada. Como são dois bancos, o log e a gravação principal não formam uma transação atômica: uma falha no log após o commit não desfaz a operação principal.

A API usa o banco já preparado: iniciar o servidor e consultar rotas não cria tabelas, altera campos nem realinha sequences. `/health` confere os campos exigidos sem escrever; estrutura incompleta retorna 503. Na pasta Backend, `python -m migrations` apenas confere o banco. Atualizações futuras são manuais, após backup, com `python -m migrations --aplicar`; a ferramenta fica separada em `Backend/migrations/`. Restaure primeiro o banco base em uma instalação nova.

E-mail, pagamentos Arkhé e análise/geração OpenAI exigem credenciais válidas dos serviços. A suíte de regressão usa simulações dessas integrações e não cobra nem envia mensagens. Os testes de banco devem usar cópias restauradas via `gbak`; nunca use dados reais para testes que alteram registros.

## Agenda, lista de espera e equipe

O cliente pode selecionar um horário ocupado elegível e entrar na lista de espera. Cancelamentos e remarcações registram avisos em `EMAIL_OUTBOX`, na mesma transação que libera o horário. Antes do envio, o sistema verifica novamente expediente, serviços, duração e disponibilidade. O aviso não reserva o horário: o cliente precisa concluir um novo agendamento. As inscrições e seus estados aparecem em Meus agendamentos.

`WAITLIST_WORKER=true` habilita o processamento automático a cada 30 segundos. Falhas de SMTP permanecem no banco, com até oito tentativas e intervalo crescente de até 60 minutos; depois, a inscrição mostra falha no aviso. Reiniciar a aplicação preserva mensagens pendentes. Para processamento manual, use `Backend/.venv/Scripts/python.exe Backend/agenda_equipe.py --limite 20`. Esse comando envia mensagens reais e deve ser usado com a configuração de produção correta. SMTP não garante exatamente um envio se o processo cair entre a aceitação da mensagem pelo servidor e o commit local.

Ao cadastrar um novo barbeiro, informe e-mail, telefone e percentual de comissão. O sistema cria uma conta exclusiva (perfil 3) e envia um convite para definir senha. Configure `PUBLIC_FRONTEND_URL` com o endereço acessível ao destinatário; `127.0.0.1` serve apenas para desenvolvimento local. O convite expira em 48 horas e só pode ser usado uma vez. Caso o SMTP falhe, o proprietário pode copiar o link ou reenviar o convite. Contas já ativadas usam recuperação de senha.

A edição da equipe preserva IDs, vínculos e histórico. Remover alguém da equipe desativa o acesso. Antes disso, agendamentos futuros ativos precisam ser reassociados ou cancelados. O painel do barbeiro mostra somente seus próprios agendamentos e permite registrar conclusão ou falta após o fim do horário, cancelar e remarcar conforme as permissões.

O banco Firebird mantém o histórico e uma comissão por atendimento concluído, com valor-base, percentual e valor calculado fixados no registro. Alterar o percentual não recalcula comissões antigas. O percentual inicial é zero: o proprietário deve definir o acordo de cada barbeiro. Agendamentos novos guardam preço e duração; registros antigos sem preço precisam receber o valor efetivo pelo proprietário, sem estimativa automática.

No painel, realizados, cancelados, faltas e valores seguem a data do agendamento. Remarcados contam agendamentos distintos com evento de remarcação no período. Valor dos serviços concluídos, recebimentos confirmados e comissão calculada são indicadores separados. Comissão calculada não confirma repasse bancário. A comissão é calculada e armazenada no Cortaê; a barbearia consulta os valores por profissional e realiza o pagamento. A integração Arkhé continua responsável pelas cobranças e pagamentos dos clientes.

O proprietário acessa **COMISSÕES** no menu e consulta um período para ver o valor devido a cada profissional e os atendimentos que compõem o cálculo. Profissionais inativos continuam no histórico. O controle de pagamentos manuais fica em **GESTÃO > Caixa e comissões**; ambos os relatórios usam a mesma comissão histórica. Configure o acordo individual em **GESTÃO > Equipe e serviços**.

Escolher pagar no local cria um pagamento pendente. Depois de receber o dinheiro, o proprietário confirma **Confirmar dinheiro recebido** no cartão do agendamento. Só então o valor passa a contar como recebido. A confirmação atualiza a tela imediatamente e registra somente o saldo restante, descontando recebimentos parciais anteriores. Após quitação, repetir a confirmação não duplica o recebimento. As cobranças usam o preço registrado na reserva, mesmo após alterar o catálogo de serviços.

## Gestão do estabelecimento

O menu **GESTÃO** abre `/gestao`. Proprietários acessam apenas o próprio salão; o administrador seleciona o estabelecimento. Profissionais acessam somente sua própria agenda. A aba **Auditoria** é exclusiva do administrador e consulta o banco separado de logs, com filtros e paginação.

- **Agenda:** visualização diária, semanal e mensal, reserva para clientes já cadastrados, busca por e-mail exato, bloqueios do salão ou profissional e regras de antecedência. Reservas novas exigem profissional quando existe equipe ativa, mostrando o preço individual antes da confirmação. Bloqueios não podem sobrepor reservas existentes. Cancelamento e reagendamento pelo cliente respeitam os prazos; a equipe pode administrar exceções.
- **Equipe e serviços:** turnos semanais individuais, intervalos entre turnos, preços por serviço e comissão fixa ou percentual. Turnos precisam respeitar o expediente do salão e os atendimentos futuros. Desativar um serviço impede novas reservas e preserva o histórico. Os links do salão e do profissional mantêm a escolha durante cadastro e login.
- **Clientes:** observações e preferências específicas do salão, frequência, faltas, histórico de atendimentos e pagamentos. Nenhum salão recebe a ficha ou o financeiro de outro estabelecimento.
- **Caixa e comissões:** receitas, despesas, categorias, vencimentos, pendências, recebimentos confirmados e histórico. Aceita dividir um atendimento entre dinheiro, cartão físico e Pix manual até o saldo devido. Esses registros não criam cobranças externas. Uma chave de idempotência impede duplicar uma tentativa repetida.
- **Relatórios:** atendimentos, serviços, profissionais, horários procurados, clientes frequentes e inativos. O caixa fornece série diária, semanal ou mensal, gráfico e comparação com o período anterior de igual duração. Recebido e valor dos serviços realizados são indicadores separados.

A comissão fixa é por atendimento concluído. A regra usada e o valor calculado ficam imutáveis no histórico, mesmo após editar o profissional. O registro de pagamento manual aceita valores parciais até o saldo devido e cria uma despesa local na mesma transação. Essa despesa vinculada não pode ser editada para evitar divergência com a comissão paga. O sistema não transfere dinheiro ao profissional.

Confirmações, cancelamentos, reagendamentos e lembretes usam a fila persistida de e-mail. O trabalhador de `WAITLIST_WORKER` também processa esses eventos e verifica se o horário/status continua válido antes de enviar. Lembretes têm antecedência configurável por salão; zero os desativa. Alterar ou cancelar a reserva invalida avisos antigos. Instalar a atualização não envia confirmações retroativas das reservas existentes. SMTP e `PUBLIC_FRONTEND_URL` válidos são necessários para a entrega real.

WhatsApp e mudanças na integração Arkhé foram excluídos deste módulo conforme o escopo solicitado. As integrações anteriores continuam disponíveis. O startup aplica migrações aditivas de gestão; faça backup dos dois bancos antes de atualizar.

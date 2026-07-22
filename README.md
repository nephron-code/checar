# Monitor de convocação HUL-UFS → Telegram

App leve que checa a página de convocações do HUL-UFS de hora em hora e te
avisa no Telegram quando um novo edital é publicado. Roda de graça no GitHub
Actions, sem precisar de servidor.

Página monitorada:
https://www.gov.br/hubrasil/pt-br/acesso-a-informacao/agentes-publicos/concursos-e-selecoes/concursos/2026/convocacoes/hul-ufs

## Como funciona

O script baixa a página, pega **apenas os PDFs de edital que pertencem a essa
página** (o menu do site tem outros PDFs, que são ignorados) e compara com o
que já viu antes, guardado no `state.json`. Quando surge um edital novo, você
recebe a mensagem no Telegram com o link direto do PDF.

## Estrutura

```
monitor-concurso/
├── check.py                     # script que checa a página e notifica
├── requirements.txt             # dependências (requests, beautifulsoup4)
├── state.json                   # criado automaticamente (memória do que já viu)
└── .github/workflows/check.yml  # agendamento de hora em hora
```

## Passo a passo (uns 10 minutos)

### 1. Criar o bot do Telegram
1. No Telegram, fale com o **@BotFather**.
2. Envie `/newbot` e siga as instruções (nome + username).
3. Ele te dá um **token** parecido com `123456:ABC-DEF...`. Guarde.

### 2. Descobrir seu chat_id
1. Envie qualquer mensagem (ex.: "oi") para o **seu** bot recém-criado.
2. Abra no navegador (troque `SEU_TOKEN`):
   `https://api.telegram.org/botSEU_TOKEN/getUpdates`
3. Procure por `"chat":{"id":123456789,...}`. Esse número é o **chat_id**.

### 3. Subir para o GitHub
1. Crie um repositório novo (pode ser privado).
2. Suba estes arquivos mantendo a pasta `.github/workflows/`.

### 4. Configurar os segredos
No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
Crie dois:
- `TELEGRAM_TOKEN` → o token do BotFather
- `TELEGRAM_CHAT_ID` → o número do passo 2

### 5. Ligar e testar
1. Aba **Actions** → habilite os workflows (se pedir).
2. Abra "Monitor concurso" → **Run workflow** (rodada manual).
   - A **primeira** rodada só memoriza os editais que já estão na página
     (hoje: 82, 84, 84.1, 99 e 99.1/2026) e **não** notifica. Isso é proposital.
3. Faça um segundo teste: envie `/start` no bot e confirme que o token/chat_id
   estão certos (se a rodada não der erro na aba Actions, está tudo ok).
4. Pronto. A partir daí ele roda sozinho de hora em hora e só te avisa quando
   surgir uma convocação nova.

## Observações

- **Horário:** o cron usa UTC. `0 * * * *` = todo minuto 0 de cada hora.
  O GitHub pode atrasar alguns minutos em horários de pico — normal.
- **Custo:** dentro do nível gratuito com folga (uma rodada de ~30s por hora).
- **Para monitorar OUTRO hospital:** basta trocar a `URL` no topo do `check.py`
  pela página de convocações correspondente. O filtro se adapta sozinho, porque
  usa o próprio endereço da página como base.
- **Se o gov.br bloquear o acesso:** raro, mas se aparecer erro 403 nos logs do
  Actions, me avise que ajusto os cabeçalhos da requisição.

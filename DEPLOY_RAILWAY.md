# 🚂 Deploy no Railway

Guia passo a passo para colocar o BTC Signal Monitor rodando 24/7 no Railway.

## 📋 Pré-requisitos

- Conta no [Railway](https://railway.app) (tem plano gratuito)
- Conta no [GitHub](https://github.com)

---

## 🚀 Método 1: Deploy via GitHub (Recomendado)

### Passo 1: Suba o código para o GitHub

```bash
# Crie um repositório no GitHub, depois:
cd btc-signal-monitor
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/SEU_USER/btc-signal-monitor.git
git push -u origin main
```

### Passo 2: Conecte ao Railway

1. Acesse [railway.app](https://railway.app)
2. Clique em **"New Project"**
3. Selecione **"Deploy from GitHub repo"**
4. Autorize o Railway a acessar seu GitHub
5. Selecione o repositório `btc-signal-monitor`

### Passo 3: Configure as Variáveis de Ambiente

No dashboard do Railway:

1. Clique no seu serviço
2. Vá na aba **"Variables"**
3. Clique em **"+ New Variable"** ou **"RAW Editor"**

Adicione estas variáveis:

```env
# Obrigatórias
SYMBOL=BTCUSD-PERP
TIMEFRAME=1h
EXCHANGE=binance
CHECK_INTERVAL=60
SIGNAL_COOLDOWN=3600

# Trade Config
ENTRY_ZONE_MIN=94200
ENTRY_ZONE_MAX=94500
STOP_LOSS=93000
TP1=95800
TP2=97000
TP3=98500
MIN_CONDITIONS=4
MIN_CONFIDENCE=60

# Notificações (configure pelo menos uma)
TELEGRAM_TOKEN=seu_token_aqui
TELEGRAM_CHAT_ID=seu_chat_id_aqui

# Ou Discord
DISCORD_WEBHOOK=https://discord.com/api/webhooks/...

# Ou Webhook genérico
WEBHOOK_URL=https://seu-servidor.com/webhook

# Ou n8n
N8N_WEBHOOK=https://seu-n8n.com/webhook/btc-signal
```

### Passo 4: Deploy!

O Railway fará o deploy automaticamente. Você verá os logs em tempo real.

---

## 🚀 Método 2: Deploy via CLI

### Passo 1: Instale a CLI do Railway

```bash
# macOS
brew install railway

# Linux/WSL
curl -fsSL https://railway.app/install.sh | sh

# npm (qualquer sistema)
npm install -g @railway/cli
```

### Passo 2: Login e Deploy

```bash
cd btc-signal-monitor

# Login
railway login

# Criar projeto
railway init

# Deploy
railway up
```

### Passo 3: Configure Variáveis

```bash
# Via CLI
railway variables set SYMBOL=BTCUSD-PERP
railway variables set TIMEFRAME=1h
railway variables set EXCHANGE=binance
railway variables set TELEGRAM_TOKEN=seu_token
railway variables set TELEGRAM_CHAT_ID=seu_chat_id
# ... adicione as outras variáveis

# Ou abra o dashboard
railway open
```

---

## 📊 Monitorando no Railway

### Ver Logs em Tempo Real

No dashboard, clique no serviço e vá em **"Logs"**.

Você verá algo como:
```
2026-01-14 03:00:00 | INFO | 📊 BTCUSD-PERP @ $95,200.00
2026-01-14 03:00:00 | INFO |    Condições: 3 | Confiança: 45%
2026-01-14 03:01:00 | INFO | 📊 BTCUSD-PERP @ $94,850.00
2026-01-14 03:01:00 | INFO |    Condições: 4 | Confiança: 65%
2026-01-14 03:01:00 | INFO | 🚨 SINAL DETECTADO!
```

### Verificar Status

Via CLI:
```bash
railway logs
railway status
```

---

## 💰 Custos do Railway

| Plano | Preço | Limite |
|-------|-------|--------|
| **Trial** | Grátis | $5 de crédito, 500h/mês |
| **Hobby** | $5/mês | 8GB RAM, execução 24/7 |
| **Pro** | $20/mês | Ilimitado |

Para um monitor leve como este, o **plano Hobby ($5/mês)** é suficiente para rodar 24/7.

---

## 🔧 Troubleshooting

### "Build failed"

Verifique se todos os arquivos estão no repositório:
```bash
ls -la
# Deve mostrar: main.py, requirements.txt, Procfile, etc.
```

### "No module named 'src'"

Certifique-se que a pasta `src/` e o arquivo `src/__init__.py` existem.

### "Connection refused" nos logs

A exchange pode estar bloqueando. Tente trocar:
```env
EXCHANGE=bybit
# ou
EXCHANGE=cryptocom
```

### Não recebo notificações

1. Verifique se as variáveis estão corretas no Railway
2. Teste o Telegram/Discord manualmente
3. Veja os logs para erros de envio

---

## 🔄 Atualizando o Código

Qualquer push no GitHub faz deploy automático:

```bash
git add .
git commit -m "Atualização"
git push
```

O Railway detecta e faz redeploy automaticamente.

---

## 🛑 Parando o Serviço

No dashboard:
1. Clique no serviço
2. Vá em **Settings**
3. Clique em **"Remove Service"** ou pause com **"Sleep"**

Via CLI:
```bash
railway down
```

---

## ✅ Checklist Final

- [ ] Código no GitHub
- [ ] Projeto criado no Railway
- [ ] Variáveis de ambiente configuradas
- [ ] Pelo menos uma notificação configurada (Telegram/Discord/Webhook)
- [ ] Deploy realizado
- [ ] Logs mostrando verificações
- [ ] Teste: envie sinal manualmente para verificar notificações

---

Pronto! Seu monitor estará rodando 24/7 🚀

# 🚀 BTC Signal Monitor

Monitor automatizado de sinais de trading para BTC Futures com detecção de padrões de candle e notificações em tempo real.

## 📋 Features

- ✅ Monitoramento em tempo real de BTCUSD-PERP
- ✅ Detecção automática de padrões de candle (Martelo, Engolfo, Pinbar, Doji)
- ✅ Cálculo de indicadores técnicos (SMA, RSI, Fibonacci)
- ✅ Sistema de confiança com múltiplas condições
- ✅ Notificações para: Webhook, Telegram, Discord, n8n
- ✅ Suporte a múltiplas exchanges (Binance, Bybit, Crypto.com)
- ✅ Docker ready

## 🚦 Quick Start

### 1. Clone e Configure

```bash
git clone <repo>
cd btc-signal-monitor

# Copie o arquivo de exemplo
cp .env.example .env

# Edite com suas credenciais
nano .env
```

### 2. Execute

**Com Python:**
```bash
pip install -r requirements.txt
python main.py
```

**Com Docker:**
```bash
docker-compose up -d
```

## ⚙️ Configuração

### Variáveis de Ambiente

| Variável | Descrição | Default |
|----------|-----------|---------|
| `SYMBOL` | Par de trading | `BTCUSD-PERP` |
| `TIMEFRAME` | Timeframe dos candles | `1h` |
| `EXCHANGE` | Exchange (binance, bybit, cryptocom) | `binance` |
| `CHECK_INTERVAL` | Intervalo entre verificações (segundos) | `60` |
| `SIGNAL_COOLDOWN` | Tempo entre sinais (segundos) | `3600` |

### Configuração do Trade

| Variável | Descrição | Default |
|----------|-----------|---------|
| `ENTRY_ZONE_MIN` | Início da zona de entrada | `94200` |
| `ENTRY_ZONE_MAX` | Fim da zona de entrada | `94500` |
| `STOP_LOSS` | Stop loss | `93000` |
| `TP1` | Take profit 1 | `95800` |
| `TP2` | Take profit 2 | `97000` |
| `TP3` | Take profit 3 | `98500` |
| `MIN_CONDITIONS` | Condições mínimas para sinal | `4` |
| `MIN_CONFIDENCE` | Confiança mínima (%) | `60` |

### Presets de Trading

Use `TRADING_PRESET` para configurações pré-definidas:

| Preset | Descrição | Probabilidade |
|--------|-----------|---------------|
| `conservative` | Maior probabilidade, menor reward | ~85% |
| `moderate` | Balanceado | ~75% |
| `aggressive` | Maior reward, menor probabilidade | ~60% |
| `scalp` | Curto prazo | ~70% |

## 📡 Configurando Notificações

### Webhook Genérico

```env
WEBHOOK_URL=https://seu-servidor.com/webhook
```

Recebe JSON:
```json
{
  "signal_type": "LONG",
  "symbol": "BTCUSD-PERP",
  "entry_zone": {"min": 94200, "max": 94500},
  "stop_loss": 93000,
  "take_profits": {"tp1": 95800, "tp2": 97000, "tp3": 98500},
  "pattern": "HAMMER",
  "confidence_score": 75,
  "conditions_met": ["..."],
  "timestamp": "2026-01-14T02:00:00Z",
  "current_price": 94350,
  "risk_reward_ratio": 1.8
}
```

### Telegram

1. Crie um bot com [@BotFather](https://t.me/BotFather)
2. Salve o token
3. Inicie uma conversa com seu bot
4. Obtenha seu `chat_id`:
   ```
   https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
   ```
5. Configure:
   ```env
   TELEGRAM_TOKEN=123456789:ABCdef...
   TELEGRAM_CHAT_ID=987654321
   ```

### Discord

1. Vá em **Server Settings** > **Integrations** > **Webhooks**
2. Crie um webhook
3. Copie a URL
4. Configure:
   ```env
   DISCORD_WEBHOOK=https://discord.com/api/webhooks/...
   ```

### n8n

1. Crie um workflow com node **Webhook**
2. Configure como **POST**
3. Copie a URL de produção
4. Configure:
   ```env
   N8N_WEBHOOK=https://seu-n8n.com/webhook/btc-signal
   ```

## 🕯️ Padrões de Candle Detectados

| Padrão | Descrição | Confiança |
|--------|-----------|-----------|
| **BULLISH_ENGULFING** | Candle verde engole o vermelho anterior | +30% |
| **HAMMER** | Martelo com pavio inferior 2x+ corpo | +25% |
| **PINBAR_BULLISH** | Pinbar com 60%+ do range no pavio inferior | +25% |
| **DOJI** | Corpo < 10% do range (indecisão) | +10% |

## 📊 Condições Verificadas

1. **Zona de Entrada**: Preço dentro do range configurado
2. **Padrão de Candle**: Um dos padrões bullish detectado
3. **SMA7 > SMA21**: Tendência de alta
4. **Preço > SMA21**: Acima da média
5. **RSI 30-50**: Zona de suporte
6. **Volume**: Acima da média

## 🔌 Integrando com Outras Aplicações

### Exemplo: Recebendo sinal em Node.js

```javascript
const express = require('express');
const app = express();

app.use(express.json());

app.post('/webhook', (req, res) => {
  const signal = req.body;
  
  console.log(`📊 SINAL ${signal.signal_type}`);
  console.log(`   Entrada: ${signal.entry_zone.min} - ${signal.entry_zone.max}`);
  console.log(`   Stop: ${signal.stop_loss}`);
  console.log(`   Confiança: ${signal.confidence_score}%`);
  
  // Processar sinal...
  
  res.sendStatus(200);
});

app.listen(3000);
```

### Exemplo: Workflow n8n

```json
{
  "nodes": [
    {
      "name": "Webhook",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "btc-signal",
        "httpMethod": "POST"
      }
    },
    {
      "name": "IF",
      "type": "n8n-nodes-base.if",
      "parameters": {
        "conditions": {
          "number": [{
            "value1": "={{$json.confidence_score}}",
            "operation": "largerEqual",
            "value2": 70
          }]
        }
      }
    },
    {
      "name": "Execute Trade",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "https://api.exchange.com/order",
        "method": "POST",
        "body": "={{$json}}"
      }
    }
  ]
}
```

## 📁 Estrutura do Projeto

```
btc-signal-monitor/
├── main.py              # Ponto de entrada
├── src/
│   ├── config.py        # Configurações
│   ├── exchanges.py     # APIs das exchanges
│   └── monitor.py       # Lógica principal
├── requirements.txt     # Dependências
├── Dockerfile          # Container
├── docker-compose.yml  # Orquestração
├── .env.example        # Exemplo de config
└── README.md           # Documentação
```

## 🔧 Customização

### Adicionando Nova Exchange

```python
# src/exchanges.py

class NovaExchange(BaseExchange):
    async def get_candles(self, symbol, timeframe, limit):
        # Implementar...
        pass
    
    async def get_ticker(self, symbol):
        # Implementar...
        pass

# Registrar
exchanges["nova"] = NovaExchange
```

### Adicionando Novo Padrão de Candle

```python
# main.py ou src/monitor.py

@staticmethod
def detect_meu_padrao(candle: Candle) -> bool:
    # Sua lógica aqui
    return True

# Adicionar ao detector
@classmethod
def detect(cls, candles):
    if cls.detect_meu_padrao(candles[-1]):
        return CandlePattern.MEU_PADRAO
    # ...
```

## ⚠️ Aviso Legal

Este software é apenas para fins educacionais. Trading de criptomoedas envolve risco significativo. Não invista mais do que você pode perder. O autor não se responsabiliza por perdas financeiras.

## 📄 Licença

MIT License

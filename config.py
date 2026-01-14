"""
Configuração do BTC Signal Monitor
Edite este arquivo com suas credenciais e preferências
"""

import os
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """Carrega configuração do ambiente ou usa valores padrão"""
    
    return {
        # ============================================================
        # CONFIGURAÇÃO DO ATIVO
        # ============================================================
        "symbol": os.getenv("SYMBOL", "BTCUSD-PERP"),
        "timeframe": os.getenv("TIMEFRAME", "1h"),  # 1h, 4h, 1D
        
        # ============================================================
        # CONFIGURAÇÃO DE MONITORAMENTO
        # ============================================================
        "check_interval": int(os.getenv("CHECK_INTERVAL", "60")),  # segundos
        "signal_cooldown": int(os.getenv("SIGNAL_COOLDOWN", "3600")),  # segundos entre sinais
        
        # ============================================================
        # CONFIGURAÇÃO DO TRADE (AJUSTE PARA SEU SETUP)
        # ============================================================
        "trading": {
            # Zona de entrada (Fibonacci 38.2% - 23.6%)
            "entry_zone_min": float(os.getenv("ENTRY_ZONE_MIN", "94200")),
            "entry_zone_max": float(os.getenv("ENTRY_ZONE_MAX", "94500")),
            
            # Stop Loss
            "stop_loss": float(os.getenv("STOP_LOSS", "93000")),
            
            # Take Profits
            "tp1": float(os.getenv("TP1", "95800")),
            "tp2": float(os.getenv("TP2", "97000")),
            "tp3": float(os.getenv("TP3", "98500")),
            
            # Condições mínimas para sinal
            "min_conditions": int(os.getenv("MIN_CONDITIONS", "4")),
            "min_confidence": int(os.getenv("MIN_CONFIDENCE", "60")),
        },
        
        # ============================================================
        # CONFIGURAÇÃO DE NOTIFICAÇÕES
        # Configure apenas os que deseja usar
        # ============================================================
        "notifications": {
            # ----- WEBHOOK GENÉRICO -----
            # Envia JSON para qualquer URL
            "webhook_url": os.getenv("WEBHOOK_URL"),
            
            # ----- TELEGRAM -----
            # 1. Crie um bot com @BotFather
            # 2. Obtenha o token
            # 3. Inicie conversa com o bot
            # 4. Obtenha seu chat_id em https://api.telegram.org/bot<TOKEN>/getUpdates
            "telegram_token": os.getenv("TELEGRAM_TOKEN"),
            "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
            
            # ----- DISCORD -----
            # 1. Vá em Configurações do servidor > Integrações > Webhooks
            # 2. Crie um webhook e copie a URL
            "discord_webhook": os.getenv("DISCORD_WEBHOOK"),
            
            # ----- N8N -----
            # Use o node "Webhook" no n8n e copie a URL
            "n8n_webhook": os.getenv("N8N_WEBHOOK"),
        },
        
        # ============================================================
        # CONFIGURAÇÃO DE EXCHANGE
        # ============================================================
        "exchange": {
            "name": os.getenv("EXCHANGE", "cryptocom"),  # cryptocom, binance, bybit
            "api_key": os.getenv("EXCHANGE_API_KEY"),
            "api_secret": os.getenv("EXCHANGE_API_SECRET"),
        },

        # ============================================================
        # CONFIGURAÇÃO DE AI (para análises sob demanda)
        # ============================================================
        "ai": {
            # Anthropic API Key - https://console.anthropic.com/api-keys
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
            # Modelo Claude a usar (haiku é mais barato, sonnet é mais preciso)
            # Opções: claude-3-haiku-20240307, claude-3-sonnet-20240229, claude-3-5-sonnet-20241022
            "model": os.getenv("AI_MODEL", "claude-3-haiku-20240307"),
            # Habilitar comandos do Telegram
            "telegram_commands_enabled": os.getenv("TELEGRAM_COMMANDS_ENABLED", "true").lower() == "true",
        }
    }


# Configuração específica para diferentes cenários de trading
TRADING_PRESETS = {
    # Setup conservador (maior probabilidade)
    "conservative": {
        "entry_zone_min": 94200,
        "entry_zone_max": 94500,
        "stop_loss": 93000,
        "tp1": 95500,
        "tp2": None,
        "tp3": None,
        "min_conditions": 5,
        "min_confidence": 75,
    },
    
    # Setup moderado (balanceado)
    "moderate": {
        "entry_zone_min": 94200,
        "entry_zone_max": 94500,
        "stop_loss": 93000,
        "tp1": 95800,
        "tp2": 97000,
        "tp3": None,
        "min_conditions": 4,
        "min_confidence": 60,
    },
    
    # Setup agressivo (maior reward)
    "aggressive": {
        "entry_zone_min": 94000,
        "entry_zone_max": 94800,
        "stop_loss": 92500,
        "tp1": 96500,
        "tp2": 98000,
        "tp3": 100000,
        "min_conditions": 3,
        "min_confidence": 50,
    },
    
    # Scalp (curto prazo)
    "scalp": {
        "entry_zone_min": 95100,
        "entry_zone_max": 95300,
        "stop_loss": 94700,
        "tp1": 96200,
        "tp2": None,
        "tp3": None,
        "min_conditions": 3,
        "min_confidence": 50,
    }
}


# Padrões de candle e seus pesos de confiança
CANDLE_PATTERN_WEIGHTS = {
    "HAMMER": 25,
    "BULLISH_ENGULFING": 30,
    "BEARISH_ENGULFING": 30,
    "PINBAR_BULLISH": 25,
    "PINBAR_BEARISH": 25,
    "DOJI": 10,
    "NONE": 0
}


# Formato do sinal JSON para integração com outras aplicações
SIGNAL_SCHEMA = {
    "type": "object",
    "properties": {
        "signal_type": {"type": "string", "enum": ["LONG", "SHORT", "CLOSE"]},
        "symbol": {"type": "string"},
        "entry_zone": {
            "type": "object",
            "properties": {
                "min": {"type": "number"},
                "max": {"type": "number"}
            }
        },
        "stop_loss": {"type": "number"},
        "take_profits": {
            "type": "object",
            "properties": {
                "tp1": {"type": "number"},
                "tp2": {"type": ["number", "null"]},
                "tp3": {"type": ["number", "null"]}
            }
        },
        "pattern": {"type": "string"},
        "confidence_score": {"type": "number"},
        "conditions_met": {"type": "array", "items": {"type": "string"}},
        "timestamp": {"type": "string", "format": "date-time"},
        "timeframe": {"type": "string"},
        "current_price": {"type": "number"},
        "risk_reward_ratio": {"type": "number"},
        "notes": {"type": "string"}
    }
}

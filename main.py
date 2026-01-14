#!/usr/bin/env python3
"""
BTC Signal Monitor - Ponto de entrada principal
Execute com: python main.py

Deploy: Railway, Render, Fly.io, ou qualquer PaaS
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Carregar variáveis de ambiente do .env (desenvolvimento local)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Usar uvloop para melhor performance em Linux
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

# Adicionar src ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges import get_exchange, Candle
from config import load_config, TRADING_PRESETS

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Importar classes do monitor
import aiohttp
from enum import Enum
from dataclasses import dataclass


class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class CandlePattern(Enum):
    HAMMER = "HAMMER"
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    PINBAR_BULLISH = "PINBAR_BULLISH"
    DOJI = "DOJI"
    NONE = "NONE"


@dataclass
class TradingSignal:
    signal_type: SignalType
    symbol: str
    entry_zone_min: float
    entry_zone_max: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    pattern_detected: CandlePattern
    confidence_score: float
    conditions_met: List[str]
    timestamp: datetime
    timeframe: str
    current_price: float
    risk_reward_ratio: float
    notes: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type.value,
            "symbol": self.symbol,
            "entry_zone": {"min": self.entry_zone_min, "max": self.entry_zone_max},
            "stop_loss": self.stop_loss,
            "take_profits": {"tp1": self.take_profit_1, "tp2": self.take_profit_2, "tp3": self.take_profit_3},
            "pattern": self.pattern_detected.value,
            "confidence_score": self.confidence_score,
            "conditions_met": self.conditions_met,
            "timestamp": self.timestamp.isoformat(),
            "timeframe": self.timeframe,
            "current_price": self.current_price,
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "notes": self.notes
        }
    
    def to_message(self) -> str:
        emoji = "🟢" if self.signal_type == SignalType.LONG else "🔴"
        return f"""
{emoji} **SINAL {self.signal_type.value}** | {self.symbol}

💰 Preço: ${self.current_price:,.2f}
📍 Entrada: ${self.entry_zone_min:,.2f} - ${self.entry_zone_max:,.2f}
🛑 Stop: ${self.stop_loss:,.2f}
🎯 TP1: ${self.take_profit_1:,.2f} | TP2: ${self.take_profit_2 or 0:,.2f}

📊 Confiança: {self.confidence_score:.0f}%
🕯️ Padrão: {self.pattern_detected.value}
📈 R:R: {self.risk_reward_ratio:.2f}

✅ Condições:
{chr(10).join(['  • ' + c for c in self.conditions_met])}

⏰ {self.timestamp.strftime('%H:%M:%S UTC')}
"""


class PatternDetector:
    """Detecta padrões de candle"""
    
    @staticmethod
    def detect_hammer(candle: Candle) -> bool:
        if candle.body == 0:
            return False
        lower_ratio = candle.lower_wick / candle.body
        upper_ratio = candle.upper_wick / candle.body if candle.body > 0 else 0
        return lower_ratio >= 2.0 and upper_ratio < 0.5
    
    @staticmethod
    def detect_engulfing(current: Candle, previous: Candle) -> bool:
        return (
            previous.is_bearish and
            current.is_bullish and
            current.open < previous.close and
            current.close > previous.open
        )
    
    @staticmethod
    def detect_pinbar(candle: Candle) -> bool:
        if candle.range == 0:
            return False
        lower_ratio = candle.lower_wick / candle.range
        return lower_ratio >= 0.6
    
    @staticmethod
    def detect_doji(candle: Candle) -> bool:
        if candle.range == 0:
            return False
        return (candle.body / candle.range) < 0.1
    
    @classmethod
    def detect(cls, candles: List[Candle]) -> CandlePattern:
        if len(candles) < 2:
            return CandlePattern.NONE
        
        current, previous = candles[-1], candles[-2]
        
        if cls.detect_engulfing(current, previous):
            return CandlePattern.BULLISH_ENGULFING
        if cls.detect_hammer(current):
            return CandlePattern.HAMMER
        if cls.detect_pinbar(current):
            return CandlePattern.PINBAR_BULLISH
        if cls.detect_doji(current):
            return CandlePattern.DOJI
        
        return CandlePattern.NONE


class Indicators:
    """Indicadores técnicos"""
    
    @staticmethod
    def sma(prices: List[float], period: int) -> Optional[float]:
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> Optional[float]:
        if len(prices) < period + 1:
            return None
        
        gains, losses = [], []
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            gains.append(max(0, change))
            losses.append(max(0, -change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def fibonacci(high: float, low: float) -> Dict[str, float]:
        diff = high - low
        return {
            "0.236": high - (diff * 0.236),
            "0.382": high - (diff * 0.382),
            "0.5": high - (diff * 0.5),
            "0.618": high - (diff * 0.618),
        }


class SignalNotifier:
    """Envia notificações"""
    
    def __init__(self, config: Dict):
        self.webhook = config.get("webhook_url")
        self.telegram_token = config.get("telegram_token")
        self.telegram_chat = config.get("telegram_chat_id")
        self.discord = config.get("discord_webhook")
        self.n8n = config.get("n8n_webhook")
    
    async def notify(self, signal: TradingSignal) -> bool:
        results = []
        
        if self.webhook:
            results.append(await self._webhook(signal))
        if self.telegram_token and self.telegram_chat:
            results.append(await self._telegram(signal))
        if self.discord:
            results.append(await self._discord(signal))
        if self.n8n:
            results.append(await self._n8n(signal))
        
        return any(results) if results else False
    
    async def _webhook(self, signal: TradingSignal) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook, json=signal.to_dict()) as r:
                    success = r.status == 200
                    logger.info(f"{'✅' if success else '❌'} Webhook: {r.status}")
                    return success
        except Exception as e:
            logger.error(f"❌ Webhook erro: {e}")
            return False
    
    async def _telegram(self, signal: TradingSignal) -> bool:
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {"chat_id": self.telegram_chat, "text": signal.to_message(), "parse_mode": "Markdown"}
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as r:
                    success = r.status == 200
                    logger.info(f"{'✅' if success else '❌'} Telegram: {r.status}")
                    return success
        except Exception as e:
            logger.error(f"❌ Telegram erro: {e}")
            return False
    
    async def _discord(self, signal: TradingSignal) -> bool:
        try:
            payload = {"content": signal.to_message()}
            async with aiohttp.ClientSession() as session:
                async with session.post(self.discord, json=payload) as r:
                    success = r.status in [200, 204]
                    logger.info(f"{'✅' if success else '❌'} Discord: {r.status}")
                    return success
        except Exception as e:
            logger.error(f"❌ Discord erro: {e}")
            return False
    
    async def _n8n(self, signal: TradingSignal) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.n8n, json=signal.to_dict()) as r:
                    success = r.status == 200
                    logger.info(f"{'✅' if success else '❌'} n8n: {r.status}")
                    return success
        except Exception as e:
            logger.error(f"❌ n8n erro: {e}")
            return False


class AIAnalyzer:
    """Analisador de mercado usando Claude (Anthropic)"""

    def __init__(self, config: Dict):
        self.api_key = config.get("ai", {}).get("anthropic_api_key")
        self.model = config.get("ai", {}).get("model", "claude-3-haiku-20240307")
        self.client = None

        if self.api_key:
            try:
                from anthropic import AsyncAnthropic
                self.client = AsyncAnthropic(api_key=self.api_key)
                logger.info(f"✅ Claude AI Analyzer inicializado (modelo: {self.model})")
            except ImportError:
                logger.warning("⚠️ Anthropic não instalado. AI desabilitado.")

    async def analyze(self, market_data: Dict) -> str:
        """Gera análise de mercado usando Claude"""
        if not self.client:
            return self._fallback_analysis(market_data)

        try:
            prompt = self._build_prompt(market_data)

            system_prompt = """Você é um analista técnico de criptomoedas experiente.
Analise os dados de mercado fornecidos e dê uma opinião clara e objetiva sobre:
1. Tendência atual (alta/baixa/lateral)
2. Força do movimento
3. Níveis importantes de suporte/resistência
4. Recomendação (comprar/vender/aguardar)
5. Pontos de atenção

Seja direto e use emojis para facilitar a leitura. Responda em português."""

            response = await self.client.messages.create(
                model=self.model,
                max_tokens=800,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"❌ Erro na análise Claude: {e}")
            return self._fallback_analysis(market_data)

    def _build_prompt(self, data: Dict) -> str:
        """Constrói o prompt para a AI"""
        return f"""Analise os seguintes dados do {data.get('symbol', 'BTC')}:

📊 **Dados Atuais:**
- Preço: ${data.get('price', 0):,.2f}
- Timeframe: {data.get('timeframe', '1h')}

📈 **Indicadores Técnicos:**
- RSI (14): {data.get('rsi', 'N/A'):.1f}
- SMA7: ${data.get('sma7', 0):,.2f}
- SMA21: ${data.get('sma21', 0):,.2f}
- SMA50: ${data.get('sma50', 'N/A')}

🕯️ **Padrão de Candle:** {data.get('pattern', 'Nenhum')}

📊 **Volume:** {data.get('volume_ratio', 1):.2f}x da média

🎯 **Setup Configurado:**
- Zona de Entrada: ${data.get('entry_min', 0):,.2f} - ${data.get('entry_max', 0):,.2f}
- Stop Loss: ${data.get('stop_loss', 0):,.2f}
- Take Profit 1: ${data.get('tp1', 0):,.2f}
- Take Profit 2: ${data.get('tp2', 0):,.2f}

📋 **Condições Atendidas ({data.get('conditions_count', 0)}):**
{chr(10).join(['• ' + c for c in data.get('conditions', [])])}

Confiança atual: {data.get('confidence', 0)}%

Forneça uma análise completa e recomendação."""

    def _fallback_analysis(self, data: Dict) -> str:
        """Análise básica quando AI não está disponível"""
        price = data.get('price', 0)
        rsi = data.get('rsi', 50)
        sma7 = data.get('sma7', 0)
        sma21 = data.get('sma21', 0)
        pattern = data.get('pattern', 'NONE')
        confidence = data.get('confidence', 0)
        conditions = data.get('conditions', [])

        # Determinar tendência
        if sma7 > sma21 and price > sma21:
            trend = "📈 Alta"
            trend_strength = "forte" if price > sma7 else "moderada"
        elif sma7 < sma21 and price < sma21:
            trend = "📉 Baixa"
            trend_strength = "forte" if price < sma7 else "moderada"
        else:
            trend = "➡️ Lateral"
            trend_strength = "indefinida"

        # RSI
        if rsi < 30:
            rsi_status = "🔵 Sobrevendido (oportunidade de compra)"
        elif rsi > 70:
            rsi_status = "🔴 Sobrecomprado (cautela)"
        elif rsi < 50:
            rsi_status = "🟡 Zona neutra baixa"
        else:
            rsi_status = "🟢 Zona neutra alta"

        # Recomendação
        if confidence >= 60 and len(conditions) >= 4:
            recommendation = "🟢 **COMPRA** - Condições favoráveis"
        elif confidence >= 40:
            recommendation = "🟡 **AGUARDAR** - Monitorar setup"
        else:
            recommendation = "🔴 **FORA** - Condições insuficientes"

        return f"""
📊 **ANÁLISE DE MERCADO** | {data.get('symbol', 'BTC')}

💰 **Preço Atual:** ${price:,.2f}

📈 **Tendência:** {trend} ({trend_strength})

📉 **RSI:** {rsi:.1f} - {rsi_status}

🕯️ **Padrão:** {pattern}

📊 **Médias Móveis:**
• SMA7: ${sma7:,.2f}
• SMA21: ${sma21:,.2f}

✅ **Condições Atendidas:** {len(conditions)}/5
{chr(10).join(['  • ' + c for c in conditions]) if conditions else '  • Nenhuma condição atendida'}

📈 **Confiança:** {confidence}%

💡 **Recomendação:** {recommendation}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}
"""


class TelegramBot:
    """Bot do Telegram para receber comandos"""

    def __init__(self, config: Dict, monitor: 'BTCMonitor', analyzer: AIAnalyzer):
        self.token = config.get("notifications", {}).get("telegram_token")
        self.chat_id = config.get("notifications", {}).get("telegram_chat_id")
        self.enabled = config.get("ai", {}).get("telegram_commands_enabled", True)
        self.monitor = monitor
        self.analyzer = analyzer
        self.last_update_id = 0

        if self.token and self.enabled:
            logger.info("🤖 Telegram Bot inicializado - Comandos habilitados")

    async def send_message(self, text: str, chat_id: str = None) -> bool:
        """Envia mensagem para o Telegram"""
        if not self.token:
            return False

        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": chat_id or self.chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as r:
                    return r.status == 200
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem: {e}")
            return False

    async def get_updates(self) -> List[Dict]:
        """Busca novas mensagens do Telegram"""
        if not self.token:
            return []

        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates"
            params = {
                "offset": self.last_update_id + 1,
                "timeout": 1,
                "allowed_updates": ["message"]
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status == 200:
                        data = await r.json()
                        return data.get("result", [])
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f"❌ Erro ao buscar updates: {e}")

        return []

    async def process_command(self, message: Dict) -> None:
        """Processa comandos recebidos"""
        text = message.get("text", "").strip().lower()
        chat_id = message.get("chat", {}).get("id")

        if not text.startswith("/"):
            return

        command = text.split()[0]

        if command in ["/analise", "/análise", "/analysis", "/a"]:
            await self._handle_analysis(chat_id)
        elif command in ["/setup", "/s"]:
            await self._handle_setup(chat_id)
        elif command in ["/status", "/st"]:
            await self._handle_status(chat_id)
        elif command in ["/help", "/ajuda", "/h"]:
            await self._handle_help(chat_id)
        elif command in ["/preco", "/preço", "/price", "/p"]:
            await self._handle_price(chat_id)

    async def _handle_analysis(self, chat_id: str) -> None:
        """Gera análise completa com AI"""
        await self.send_message("🔄 Gerando análise com AI...", chat_id)

        try:
            # Buscar dados atuais
            market_data = await self._get_market_data()

            # Gerar análise
            analysis = await self.analyzer.analyze(market_data)

            await self.send_message(analysis, chat_id)

        except Exception as e:
            logger.error(f"❌ Erro na análise: {e}")
            await self.send_message(f"❌ Erro ao gerar análise: {e}", chat_id)

    async def _handle_setup(self, chat_id: str) -> None:
        """Mostra configuração atual do setup"""
        trading = self.monitor.trading

        message = f"""
⚙️ **SETUP ATUAL** | {self.monitor.symbol}

📍 **Zona de Entrada:**
   ${trading.get('entry_zone_min', 0):,.2f} - ${trading.get('entry_zone_max', 0):,.2f}

🛑 **Stop Loss:** ${trading.get('stop_loss', 0):,.2f}

🎯 **Take Profits:**
   TP1: ${trading.get('tp1', 0):,.2f}
   TP2: ${trading.get('tp2', 0):,.2f}
   TP3: ${trading.get('tp3', 0):,.2f}

📊 **Critérios:**
   Mín. Condições: {trading.get('min_conditions', 4)}
   Mín. Confiança: {trading.get('min_confidence', 60)}%

⏱️ **Timeframe:** {self.monitor.timeframe}
🔄 **Intervalo:** {self.monitor.interval}s
⏳ **Cooldown:** {self.monitor.cooldown}s
"""
        await self.send_message(message, chat_id)

    async def _handle_status(self, chat_id: str) -> None:
        """Mostra status do monitor"""
        last_signal = self.monitor.last_signal
        status = "🟢 Ativo" if self.monitor else "🔴 Inativo"

        message = f"""
📡 **STATUS DO MONITOR**

{status}

📊 Par: {self.monitor.symbol}
⏱️ Timeframe: {self.monitor.timeframe}
🔄 Intervalo: {self.monitor.interval}s

📨 Último Sinal: {last_signal.strftime('%d/%m %H:%M UTC') if last_signal else 'Nenhum'}

⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}
"""
        await self.send_message(message, chat_id)

    async def _handle_price(self, chat_id: str) -> None:
        """Mostra preço atual"""
        try:
            candles = await self.monitor.exchange.get_candles(
                self.monitor.symbol, self.monitor.timeframe, 1
            )
            if candles:
                price = candles[-1].close
                message = f"💰 **{self.monitor.symbol}**\n\nPreço: ${price:,.2f}\n\n⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
            else:
                message = "❌ Não foi possível obter o preço"

            await self.send_message(message, chat_id)
        except Exception as e:
            await self.send_message(f"❌ Erro: {e}", chat_id)

    async def _handle_help(self, chat_id: str) -> None:
        """Mostra comandos disponíveis"""
        message = """
🤖 **COMANDOS DISPONÍVEIS**

📊 **/analise** (ou /a)
   Gera análise completa com AI

⚙️ **/setup** (ou /s)
   Mostra configuração atual

📡 **/status** (ou /st)
   Status do monitor

💰 **/preco** (ou /p)
   Preço atual

❓ **/help** (ou /ajuda)
   Lista de comandos
"""
        await self.send_message(message, chat_id)

    async def _get_market_data(self) -> Dict:
        """Busca dados de mercado para análise"""
        candles = await self.monitor.exchange.get_candles(
            self.monitor.symbol, self.monitor.timeframe, 100
        )

        if not candles or len(candles) < 50:
            raise Exception("Dados insuficientes")

        price = candles[-1].close
        closes = [c.close for c in candles]

        # Indicadores
        sma7 = Indicators.sma(closes, 7)
        sma21 = Indicators.sma(closes, 21)
        sma50 = Indicators.sma(closes, 50)
        rsi = Indicators.rsi(closes)
        pattern = PatternDetector.detect(candles)

        # Volume
        volumes = [c.volume for c in candles[-10:]]
        avg_vol = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 0
        volume_ratio = candles[-1].volume / avg_vol if avg_vol > 0 else 1

        # Verificar condições
        _, conditions, confidence, _ = self.monitor.check_conditions(candles, price)

        return {
            "symbol": self.monitor.symbol,
            "timeframe": self.monitor.timeframe,
            "price": price,
            "rsi": rsi or 50,
            "sma7": sma7 or 0,
            "sma21": sma21 or 0,
            "sma50": sma50,
            "pattern": pattern.value,
            "volume_ratio": volume_ratio,
            "conditions": conditions,
            "conditions_count": len(conditions),
            "confidence": confidence,
            "entry_min": self.monitor.trading.get("entry_zone_min", 0),
            "entry_max": self.monitor.trading.get("entry_zone_max", 0),
            "stop_loss": self.monitor.trading.get("stop_loss", 0),
            "tp1": self.monitor.trading.get("tp1", 0),
            "tp2": self.monitor.trading.get("tp2", 0),
        }

    async def poll(self) -> None:
        """Processa mensagens pendentes"""
        if not self.token or not self.enabled:
            return

        updates = await self.get_updates()

        for update in updates:
            self.last_update_id = update.get("update_id", self.last_update_id)
            message = update.get("message", {})

            if message:
                await self.process_command(message)


class BTCMonitor:
    """Monitor principal"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.symbol = config.get("symbol", "BTCUSD-PERP")
        self.timeframe = config.get("timeframe", "1h")
        self.interval = config.get("check_interval", 60)
        self.cooldown = config.get("signal_cooldown", 3600)
        
        self.exchange = get_exchange(config.get("exchange", {}).get("name", "binance"))
        self.notifier = SignalNotifier(config.get("notifications", {}))
        self.trading = config.get("trading", {})
        
        self.last_signal = None
    
    def check_conditions(self, candles: List[Candle], price: float) -> tuple:
        """Verifica condições de entrada"""
        conditions = []
        confidence = 0
        
        closes = [c.close for c in candles]
        
        # 1. Zona de entrada
        entry_min = self.trading.get("entry_zone_min", 94200)
        entry_max = self.trading.get("entry_zone_max", 94500)
        
        if entry_min <= price <= entry_max:
            conditions.append(f"Preço na zona de entrada (${entry_min:,.0f}-${entry_max:,.0f})")
            confidence += 25
        
        # 2. Padrão de candle
        pattern = PatternDetector.detect(candles)
        bullish_patterns = [CandlePattern.HAMMER, CandlePattern.BULLISH_ENGULFING, CandlePattern.PINBAR_BULLISH]
        
        if pattern in bullish_patterns:
            conditions.append(f"Padrão de reversão: {pattern.value}")
            confidence += 25
        elif pattern == CandlePattern.DOJI:
            conditions.append("Doji detectado (indecisão)")
            confidence += 10
        
        # 3. SMAs
        sma7 = Indicators.sma(closes, 7)
        sma21 = Indicators.sma(closes, 21)
        
        if sma7 and sma21:
            if price > sma21:
                conditions.append(f"Preço > SMA21 (${sma21:,.0f})")
                confidence += 15
            if sma7 > sma21:
                conditions.append("SMA7 > SMA21 (tendência de alta)")
                confidence += 10
        
        # 4. RSI
        rsi = Indicators.rsi(closes)
        if rsi:
            if 30 <= rsi <= 50:
                conditions.append(f"RSI em zona de suporte ({rsi:.1f})")
                confidence += 15
            elif 50 < rsi < 70:
                conditions.append(f"RSI neutro ({rsi:.1f})")
                confidence += 5
        
        # 5. Volume
        volumes = [c.volume for c in candles[-10:]]
        avg_vol = sum(volumes[:-1]) / len(volumes[:-1]) if len(volumes) > 1 else 0
        
        if avg_vol > 0 and candles[-1].volume > avg_vol * 1.2:
            conditions.append(f"Volume acima da média ({candles[-1].volume/avg_vol:.1f}x)")
            confidence += 10
        
        # Decidir se envia sinal
        min_cond = self.trading.get("min_conditions", 4)
        min_conf = self.trading.get("min_confidence", 60)
        
        should_signal = (
            len(conditions) >= min_cond and
            confidence >= min_conf and
            pattern in bullish_patterns
        )
        
        return should_signal, conditions, confidence, pattern
    
    async def run_once(self) -> Optional[TradingSignal]:
        """Executa uma verificação"""
        
        # Verificar cooldown
        if self.last_signal:
            elapsed = (datetime.now(timezone.utc) - self.last_signal).total_seconds()
            if elapsed < self.cooldown:
                return None
        
        # Buscar dados
        candles = await self.exchange.get_candles(self.symbol, self.timeframe, 100)
        if not candles or len(candles) < 50:
            logger.warning("⚠️ Dados insuficientes")
            return None
        
        price = candles[-1].close
        logger.info(f"📊 {self.symbol} @ ${price:,.2f}")
        
        # Verificar condições
        should_signal, conditions, confidence, pattern = self.check_conditions(candles, price)
        
        logger.info(f"   Condições: {len(conditions)} | Confiança: {confidence}%")
        
        if not should_signal:
            return None
        
        # Criar sinal
        entry_min = self.trading.get("entry_zone_min", 94200)
        entry_max = self.trading.get("entry_zone_max", 94500)
        stop = self.trading.get("stop_loss", 93000)
        tp1 = self.trading.get("tp1", 95800)
        tp2 = self.trading.get("tp2", 97000)
        tp3 = self.trading.get("tp3", 98500)
        
        risk = ((entry_min + entry_max) / 2) - stop
        reward = tp1 - ((entry_min + entry_max) / 2)
        rr = reward / risk if risk > 0 else 0
        
        signal = TradingSignal(
            signal_type=SignalType.LONG,
            symbol=self.symbol,
            entry_zone_min=entry_min,
            entry_zone_max=entry_max,
            stop_loss=stop,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            pattern_detected=pattern,
            confidence_score=confidence,
            conditions_met=conditions,
            timestamp=datetime.now(timezone.utc),
            timeframe=self.timeframe,
            current_price=price,
            risk_reward_ratio=rr,
            notes="Pullback na zona dourada de Fibonacci"
        )
        
        logger.info(f"\n🚨 SINAL DETECTADO!\n{signal.to_message()}")
        
        # Enviar notificação
        success = await self.notifier.notify(signal)
        
        if success:
            self.last_signal = datetime.now(timezone.utc)
            logger.info("✅ Sinal enviado!")
        
        return signal
    
    async def run(self, telegram_bot: 'TelegramBot' = None):
        """Loop principal"""
        ai_status = "Habilitado" if telegram_bot and telegram_bot.enabled else "Desabilitado"

        logger.info(f"""
╔══════════════════════════════════════════════════════════╗
║          BTC SIGNAL MONITOR - INICIANDO                  ║
╠══════════════════════════════════════════════════════════╣
║  Símbolo: {self.symbol:<20}                        ║
║  Timeframe: {self.timeframe:<18}                        ║
║  Intervalo: {self.interval}s                                       ║
║  Cooldown: {self.cooldown}s                                       ║
║  Ambiente: {os.getenv('RAILWAY_ENVIRONMENT', 'local'):<18}              ║
║  Comandos AI: {ai_status:<15}                           ║
╚══════════════════════════════════════════════════════════╝
        """)

        check_count = 0

        while True:
            try:
                # Verificar comandos do Telegram
                if telegram_bot:
                    await telegram_bot.poll()

                await self.run_once()
                check_count += 1

                # Log de heartbeat a cada 60 verificações (~1h se intervalo=60s)
                if check_count % 60 == 0:
                    logger.info(f"💓 Heartbeat: {check_count} verificações | Último sinal: {self.last_signal or 'Nenhum'}")

            except Exception as e:
                logger.error(f"❌ Erro: {e}")

            await asyncio.sleep(self.interval)


async def main():
    """Entrada principal"""

    # Carregar config
    config = load_config()

    # Sobrescrever com preset se especificado
    preset = os.getenv("TRADING_PRESET")
    if preset and preset in TRADING_PRESETS:
        config["trading"].update(TRADING_PRESETS[preset])
        logger.info(f"📋 Usando preset: {preset}")

    # Iniciar monitor
    monitor = BTCMonitor(config)

    # Iniciar AI Analyzer e Telegram Bot
    analyzer = AIAnalyzer(config)
    telegram_bot = TelegramBot(config, monitor, analyzer)

    await monitor.run(telegram_bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Encerrando...")

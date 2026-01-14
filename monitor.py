"""
BTC Trading Signal Monitor
Monitora BTCUSD-PERP e envia sinais quando condições são atendidas
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from enum import Enum
import aiohttp

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SignalType(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    CLOSE = "CLOSE"


class CandlePattern(Enum):
    HAMMER = "HAMMER"
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    BEARISH_ENGULFING = "BEARISH_ENGULFING"
    DOJI = "DOJI"
    PINBAR_BULLISH = "PINBAR_BULLISH"
    PINBAR_BEARISH = "PINBAR_BEARISH"
    NONE = "NONE"


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    @property
    def body(self) -> float:
        return abs(self.close - self.open)
    
    @property
    def upper_wick(self) -> float:
        return self.high - max(self.open, self.close)
    
    @property
    def lower_wick(self) -> float:
        return min(self.open, self.close) - self.low
    
    @property
    def range(self) -> float:
        return self.high - self.low
    
    @property
    def is_bullish(self) -> bool:
        return self.close > self.open
    
    @property
    def is_bearish(self) -> bool:
        return self.close < self.open


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
    confidence_score: float  # 0-100
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
            "entry_zone": {
                "min": self.entry_zone_min,
                "max": self.entry_zone_max
            },
            "stop_loss": self.stop_loss,
            "take_profits": {
                "tp1": self.take_profit_1,
                "tp2": self.take_profit_2,
                "tp3": self.take_profit_3
            },
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
        """Formata sinal como mensagem legível"""
        tp_str = f"TP1: ${self.take_profit_1:,.2f}"
        if self.take_profit_2:
            tp_str += f" | TP2: ${self.take_profit_2:,.2f}"
        if self.take_profit_3:
            tp_str += f" | TP3: ${self.take_profit_3:,.2f}"
            
        conditions_str = "\n".join([f"  ✅ {c}" for c in self.conditions_met])
        
        return f"""
🚨 **SINAL DE TRADING DETECTADO** 🚨

📊 **{self.signal_type.value}** {self.symbol}
⏰ Timeframe: {self.timeframe}
💰 Preço Atual: ${self.current_price:,.2f}

📍 **ENTRADA**
   Zona: ${self.entry_zone_min:,.2f} - ${self.entry_zone_max:,.2f}

🛑 **STOP LOSS**
   ${self.stop_loss:,.2f}

🎯 **TAKE PROFITS**
   {tp_str}

📈 **R:R Ratio:** {self.risk_reward_ratio:.2f}
🎲 **Confiança:** {self.confidence_score:.0f}%
🕯️ **Padrão:** {self.pattern_detected.value}

✅ **Condições Atendidas:**
{conditions_str}

📝 {self.notes}

⏱️ {self.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
"""


class CandlePatternDetector:
    """Detecta padrões de candle"""
    
    @staticmethod
    def detect_hammer(candle: Candle, min_wick_ratio: float = 2.0) -> bool:
        """
        Detecta padrão Martelo (Hammer)
        - Pavio inferior >= 2x o corpo
        - Pavio superior pequeno ou inexistente
        - Corpo no terço superior do range
        """
        if candle.body == 0:
            return False
            
        lower_wick_ratio = candle.lower_wick / candle.body if candle.body > 0 else 0
        upper_wick_ratio = candle.upper_wick / candle.body if candle.body > 0 else 0
        
        # Pavio inferior deve ser pelo menos 2x o corpo
        # Pavio superior deve ser menor que o corpo
        return (
            lower_wick_ratio >= min_wick_ratio and
            upper_wick_ratio < 1.0 and
            candle.lower_wick > candle.upper_wick
        )
    
    @staticmethod
    def detect_bullish_engulfing(current: Candle, previous: Candle) -> bool:
        """
        Detecta padrão Engolfo de Alta
        - Candle anterior é bearish
        - Candle atual é bullish
        - Corpo atual engole completamente o corpo anterior
        """
        return (
            previous.is_bearish and
            current.is_bullish and
            current.open < previous.close and
            current.close > previous.open
        )
    
    @staticmethod
    def detect_bearish_engulfing(current: Candle, previous: Candle) -> bool:
        """Detecta padrão Engolfo de Baixa"""
        return (
            previous.is_bullish and
            current.is_bearish and
            current.open > previous.close and
            current.close < previous.open
        )
    
    @staticmethod
    def detect_doji(candle: Candle, threshold: float = 0.1) -> bool:
        """
        Detecta Doji
        - Corpo muito pequeno em relação ao range
        """
        if candle.range == 0:
            return False
        body_ratio = candle.body / candle.range
        return body_ratio < threshold
    
    @staticmethod
    def detect_pinbar_bullish(candle: Candle) -> bool:
        """Detecta Pinbar de Alta"""
        if candle.range == 0:
            return False
        
        lower_wick_ratio = candle.lower_wick / candle.range
        body_position = (min(candle.open, candle.close) - candle.low) / candle.range
        
        return (
            lower_wick_ratio >= 0.6 and  # Pavio inferior é 60%+ do range
            body_position >= 0.6  # Corpo está no terço superior
        )
    
    @classmethod
    def detect_pattern(cls, candles: List[Candle]) -> CandlePattern:
        """Detecta o padrão mais relevante nos últimos candles"""
        if len(candles) < 2:
            return CandlePattern.NONE
            
        current = candles[-1]
        previous = candles[-2]
        
        # Ordem de prioridade dos padrões
        if cls.detect_bullish_engulfing(current, previous):
            return CandlePattern.BULLISH_ENGULFING
        
        if cls.detect_bearish_engulfing(current, previous):
            return CandlePattern.BEARISH_ENGULFING
        
        if cls.detect_hammer(current):
            return CandlePattern.HAMMER
        
        if cls.detect_pinbar_bullish(current):
            return CandlePattern.PINBAR_BULLISH
        
        if cls.detect_doji(current):
            return CandlePattern.DOJI
        
        return CandlePattern.NONE


class TechnicalIndicators:
    """Calcula indicadores técnicos"""
    
    @staticmethod
    def sma(prices: List[float], period: int) -> Optional[float]:
        """Simple Moving Average"""
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    @staticmethod
    def ema(prices: List[float], period: int) -> Optional[float]:
        """Exponential Moving Average"""
        if len(prices) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = prices[0]
        
        for price in prices[1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """Relative Strength Index"""
        if len(prices) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, len(prices)):
            change = prices[i] - prices[i-1]
            if change >= 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def fibonacci_levels(high: float, low: float) -> Dict[str, float]:
        """Calcula níveis de Fibonacci"""
        diff = high - low
        return {
            "0.0": high,
            "0.236": high - (diff * 0.236),
            "0.382": high - (diff * 0.382),
            "0.5": high - (diff * 0.5),
            "0.618": high - (diff * 0.618),
            "0.786": high - (diff * 0.786),
            "1.0": low,
            "1.272": low - (diff * 0.272),
            "1.618": low - (diff * 0.618)
        }
    
    @staticmethod
    def atr(candles: List[Candle], period: int = 14) -> Optional[float]:
        """Average True Range"""
        if len(candles) < period + 1:
            return None
        
        true_ranges = []
        for i in range(1, len(candles)):
            current = candles[i]
            previous = candles[i-1]
            
            tr = max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close)
            )
            true_ranges.append(tr)
        
        return sum(true_ranges[-period:]) / period


class SignalNotifier:
    """Envia sinais para destinos externos"""
    
    def __init__(self, config: Dict[str, Any]):
        self.webhook_url = config.get("webhook_url")
        self.telegram_token = config.get("telegram_token")
        self.telegram_chat_id = config.get("telegram_chat_id")
        self.discord_webhook = config.get("discord_webhook")
        self.n8n_webhook = config.get("n8n_webhook")
    
    async def send_signal(self, signal: TradingSignal) -> bool:
        """Envia sinal para todos os destinos configurados"""
        results = []
        
        if self.webhook_url:
            results.append(await self._send_webhook(signal))
        
        if self.telegram_token and self.telegram_chat_id:
            results.append(await self._send_telegram(signal))
        
        if self.discord_webhook:
            results.append(await self._send_discord(signal))
        
        if self.n8n_webhook:
            results.append(await self._send_n8n(signal))
        
        return all(results) if results else False
    
    async def _send_webhook(self, signal: TradingSignal) -> bool:
        """Envia para webhook genérico"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=signal.to_dict(),
                    headers={"Content-Type": "application/json"}
                ) as response:
                    success = response.status == 200
                    if success:
                        logger.info(f"✅ Sinal enviado para webhook: {self.webhook_url}")
                    else:
                        logger.error(f"❌ Erro webhook: {response.status}")
                    return success
        except Exception as e:
            logger.error(f"❌ Erro ao enviar webhook: {e}")
            return False
    
    async def _send_telegram(self, signal: TradingSignal) -> bool:
        """Envia para Telegram"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                "chat_id": self.telegram_chat_id,
                "text": signal.to_message(),
                "parse_mode": "Markdown"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    success = response.status == 200
                    if success:
                        logger.info("✅ Sinal enviado para Telegram")
                    return success
        except Exception as e:
            logger.error(f"❌ Erro ao enviar Telegram: {e}")
            return False
    
    async def _send_discord(self, signal: TradingSignal) -> bool:
        """Envia para Discord"""
        try:
            payload = {
                "content": signal.to_message(),
                "embeds": [{
                    "title": f"🚨 {signal.signal_type.value} {signal.symbol}",
                    "color": 65280 if signal.signal_type == SignalType.LONG else 16711680,
                    "fields": [
                        {"name": "Entrada", "value": f"${signal.entry_zone_min:,.2f} - ${signal.entry_zone_max:,.2f}", "inline": True},
                        {"name": "Stop Loss", "value": f"${signal.stop_loss:,.2f}", "inline": True},
                        {"name": "TP1", "value": f"${signal.take_profit_1:,.2f}", "inline": True},
                        {"name": "Confiança", "value": f"{signal.confidence_score:.0f}%", "inline": True},
                        {"name": "Padrão", "value": signal.pattern_detected.value, "inline": True},
                        {"name": "R:R", "value": f"{signal.risk_reward_ratio:.2f}", "inline": True}
                    ]
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.discord_webhook, json=payload) as response:
                    success = response.status in [200, 204]
                    if success:
                        logger.info("✅ Sinal enviado para Discord")
                    return success
        except Exception as e:
            logger.error(f"❌ Erro ao enviar Discord: {e}")
            return False
    
    async def _send_n8n(self, signal: TradingSignal) -> bool:
        """Envia para n8n webhook"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.n8n_webhook,
                    json=signal.to_dict(),
                    headers={"Content-Type": "application/json"}
                ) as response:
                    success = response.status == 200
                    if success:
                        logger.info("✅ Sinal enviado para n8n")
                    return success
        except Exception as e:
            logger.error(f"❌ Erro ao enviar n8n: {e}")
            return False


class TradingConditions:
    """Define e verifica condições de trading"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.pattern_detector = CandlePatternDetector()
        self.indicators = TechnicalIndicators()
    
    def check_long_conditions(
        self,
        candles: List[Candle],
        current_price: float
    ) -> tuple[bool, List[str], float, CandlePattern]:
        """
        Verifica condições para sinal LONG
        Retorna: (should_signal, conditions_met, confidence_score, pattern)
        """
        conditions_met = []
        confidence = 0
        
        # Extrair preços de fechamento
        closes = [c.close for c in candles]
        
        # 1. Verificar zona de entrada (Fibonacci)
        # Usando os últimos 50 candles para definir swing high/low
        recent_high = max(c.high for c in candles[-50:])
        recent_low = min(c.low for c in candles[-50:])
        fib_levels = self.indicators.fibonacci_levels(recent_high, recent_low)
        
        entry_zone_min = self.config.get("entry_zone_min", fib_levels["0.382"])
        entry_zone_max = self.config.get("entry_zone_max", fib_levels["0.236"])
        
        in_entry_zone = entry_zone_min <= current_price <= entry_zone_max
        if in_entry_zone:
            conditions_met.append(f"Preço na zona de entrada (${entry_zone_min:,.0f}-${entry_zone_max:,.0f})")
            confidence += 20
        
        # 2. Verificar padrão de candle
        pattern = self.pattern_detector.detect_pattern(candles)
        bullish_patterns = [
            CandlePattern.HAMMER,
            CandlePattern.BULLISH_ENGULFING,
            CandlePattern.PINBAR_BULLISH
        ]
        
        if pattern in bullish_patterns:
            conditions_met.append(f"Padrão de reversão detectado: {pattern.value}")
            confidence += 25
        elif pattern == CandlePattern.DOJI:
            conditions_met.append("Doji detectado (aguardar confirmação)")
            confidence += 10
        
        # 3. Verificar tendência (SMAs)
        sma_7 = self.indicators.sma(closes, 7)
        sma_21 = self.indicators.sma(closes, 21)
        sma_50 = self.indicators.sma(closes, 50)
        
        if sma_7 and sma_21 and sma_50:
            if current_price > sma_21:
                conditions_met.append(f"Preço acima da SMA21 (${sma_21:,.0f})")
                confidence += 15
            
            if sma_7 > sma_21 > sma_50:
                conditions_met.append("SMAs alinhadas (tendência de alta)")
                confidence += 15
        
        # 4. Verificar RSI
        rsi = self.indicators.rsi(closes)
        if rsi:
            if 40 <= rsi <= 60:
                conditions_met.append(f"RSI em zona neutra ({rsi:.1f})")
                confidence += 10
            elif 30 <= rsi < 40:
                conditions_met.append(f"RSI em zona de suporte ({rsi:.1f})")
                confidence += 15
        
        # 5. Verificar volume
        recent_volumes = [c.volume for c in candles[-10:]]
        avg_volume = sum(recent_volumes[:-1]) / len(recent_volumes[:-1])
        current_volume = candles[-1].volume
        
        if current_volume > avg_volume * 1.2:
            conditions_met.append(f"Volume acima da média ({current_volume/avg_volume:.1f}x)")
            confidence += 10
        
        # 6. Verificar que não está em sobrecompra
        if rsi and rsi < 70:
            conditions_met.append("RSI não está em sobrecompra")
            confidence += 5
        
        # Determinar se deve enviar sinal
        min_conditions = self.config.get("min_conditions", 4)
        min_confidence = self.config.get("min_confidence", 60)
        
        should_signal = (
            len(conditions_met) >= min_conditions and
            confidence >= min_confidence and
            pattern in bullish_patterns  # Requer padrão de confirmação
        )
        
        return should_signal, conditions_met, confidence, pattern


class BTCSignalMonitor:
    """Monitor principal de sinais BTC"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.symbol = config.get("symbol", "BTCUSD-PERP")
        self.timeframe = config.get("timeframe", "1h")
        self.check_interval = config.get("check_interval", 60)  # segundos
        
        self.notifier = SignalNotifier(config.get("notifications", {}))
        self.conditions = TradingConditions(config.get("trading", {}))
        
        self.last_signal_time = None
        self.signal_cooldown = config.get("signal_cooldown", 3600)  # 1 hora entre sinais
        
        # Configurações de trade
        self.stop_loss = config.get("trading", {}).get("stop_loss", 93000)
        self.tp1 = config.get("trading", {}).get("tp1", 95800)
        self.tp2 = config.get("trading", {}).get("tp2", 97000)
        self.tp3 = config.get("trading", {}).get("tp3", 98500)
    
    async def fetch_candles(self) -> List[Candle]:
        """Busca candles da API"""
        # Usando API pública da Crypto.com
        url = f"https://api.crypto.com/exchange/v1/public/get-candlestick"
        params = {
            "instrument_name": self.symbol,
            "timeframe": self.timeframe
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        candles = []
                        
                        for item in data.get("result", {}).get("data", []):
                            candle = Candle(
                                timestamp=datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")),
                                open=float(item["open"]),
                                high=float(item["high"]),
                                low=float(item["low"]),
                                close=float(item["close"]),
                                volume=float(item["volume"])
                            )
                            candles.append(candle)
                        
                        # Ordenar por timestamp
                        candles.sort(key=lambda x: x.timestamp)
                        return candles
                    else:
                        logger.error(f"Erro ao buscar candles: {response.status}")
                        return []
        except Exception as e:
            logger.error(f"Erro na requisição: {e}")
            return []
    
    async def check_and_signal(self):
        """Verifica condições e envia sinal se necessário"""
        # Verificar cooldown
        if self.last_signal_time:
            elapsed = (datetime.now(timezone.utc) - self.last_signal_time).total_seconds()
            if elapsed < self.signal_cooldown:
                logger.debug(f"Em cooldown, restam {self.signal_cooldown - elapsed:.0f}s")
                return
        
        # Buscar dados
        candles = await self.fetch_candles()
        if not candles or len(candles) < 50:
            logger.warning("Dados insuficientes")
            return
        
        current_price = candles[-1].close
        logger.info(f"📊 {self.symbol} @ ${current_price:,.2f}")
        
        # Verificar condições
        should_signal, conditions_met, confidence, pattern = self.conditions.check_long_conditions(
            candles, current_price
        )
        
        logger.info(f"   Condições: {len(conditions_met)}/4 | Confiança: {confidence}%")
        
        if should_signal:
            # Calcular zona de entrada baseada em Fibonacci
            recent_high = max(c.high for c in candles[-50:])
            recent_low = min(c.low for c in candles[-50:])
            fib = TechnicalIndicators.fibonacci_levels(recent_high, recent_low)
            
            entry_min = self.config.get("trading", {}).get("entry_zone_min", fib["0.382"])
            entry_max = self.config.get("trading", {}).get("entry_zone_max", fib["0.236"])
            
            # Calcular R:R
            risk = (entry_min + entry_max) / 2 - self.stop_loss
            reward = self.tp1 - (entry_min + entry_max) / 2
            rr_ratio = reward / risk if risk > 0 else 0
            
            signal = TradingSignal(
                signal_type=SignalType.LONG,
                symbol=self.symbol,
                entry_zone_min=entry_min,
                entry_zone_max=entry_max,
                stop_loss=self.stop_loss,
                take_profit_1=self.tp1,
                take_profit_2=self.tp2,
                take_profit_3=self.tp3,
                pattern_detected=pattern,
                confidence_score=confidence,
                conditions_met=conditions_met,
                timestamp=datetime.now(timezone.utc),
                timeframe=self.timeframe,
                current_price=current_price,
                risk_reward_ratio=rr_ratio,
                notes=f"Pullback na zona dourada de Fibonacci. ATR: ${TechnicalIndicators.atr(candles):,.0f}"
            )
            
            logger.info(f"🚨 SINAL DETECTADO! Confiança: {confidence}%")
            logger.info(signal.to_message())
            
            # Enviar sinal
            success = await self.notifier.send_signal(signal)
            
            if success:
                self.last_signal_time = datetime.now(timezone.utc)
                logger.info("✅ Sinal enviado com sucesso!")
            else:
                logger.warning("⚠️ Falha ao enviar sinal")
    
    async def run(self):
        """Loop principal do monitor"""
        logger.info(f"🚀 Iniciando monitor {self.symbol} @ {self.timeframe}")
        logger.info(f"   Intervalo de verificação: {self.check_interval}s")
        logger.info(f"   Cooldown entre sinais: {self.signal_cooldown}s")
        
        while True:
            try:
                await self.check_and_signal()
            except Exception as e:
                logger.error(f"Erro no loop principal: {e}")
            
            await asyncio.sleep(self.check_interval)


async def main():
    """Função principal"""
    # Carregar configuração
    config = {
        "symbol": "BTCUSD-PERP",
        "timeframe": "1h",
        "check_interval": 60,  # Verificar a cada 60 segundos
        "signal_cooldown": 3600,  # 1 hora entre sinais
        
        "trading": {
            "entry_zone_min": 94200,
            "entry_zone_max": 94500,
            "stop_loss": 93000,
            "tp1": 95800,
            "tp2": 97000,
            "tp3": 98500,
            "min_conditions": 4,
            "min_confidence": 60
        },
        
        "notifications": {
            # Descomente e configure os que deseja usar:
            # "webhook_url": "https://seu-webhook.com/signal",
            # "telegram_token": "SEU_BOT_TOKEN",
            # "telegram_chat_id": "SEU_CHAT_ID",
            # "discord_webhook": "https://discord.com/api/webhooks/...",
            # "n8n_webhook": "https://seu-n8n.com/webhook/...",
        }
    }
    
    monitor = BTCSignalMonitor(config)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())

"""
Cliente para API de Análise de Mercado (Supabase Edge Functions)
Substitui cálculos locais por análise completa da API
"""

import aiohttp
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MarketAnalysis:
    """Resultado da análise de mercado"""
    symbol: str
    timeframe: str
    current_price: float

    # Indicadores
    rsi14: float
    atr14: float
    ma20: float
    ma50: float
    ma200: float
    adx: float
    adx_trend: str  # 'strong', 'moderate', 'weak'

    # Volume
    avg_volume: float
    current_volume: float
    relative_volume: float
    is_volume_spike: bool

    # Estrutura
    bias: str  # 'bullish', 'bearish', 'neutral'
    pattern: str

    # Trade Plan
    side: Optional[str]  # 'long', 'short', None
    entry: Optional[float]
    stop: Optional[float]
    targets: list
    risk_reward: float
    setup: str

    # Confiança
    confidence_score: int
    confidence_grade: str  # 'A', 'B', 'C', 'D', 'F'

    # AI
    ai_summary: str

    # Divergência
    divergence_type: Optional[str]
    divergence_category: Optional[str]

    # Níveis
    levels: list

    # Raw data
    raw_data: Dict[str, Any]


class SupabaseAnalyzer:
    """Cliente para API de análise do Supabase"""

    def __init__(self, base_url: str, anon_key: str):
        self.base_url = base_url.rstrip('/')
        self.anon_key = anon_key
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {anon_key}'
        }

    async def analyze_market(
        self,
        symbol: str,
        timeframe: str = "4h",
        limit: int = 500
    ) -> Optional[MarketAnalysis]:
        """
        Chama a API /analyze-market e retorna análise completa

        Args:
            symbol: Símbolo do ativo (ex: BTCUSDT, BTCUSDT.P para futuros)
            timeframe: Timeframe (1h, 4h, 1d, etc)
            limit: Número de candles (max 1000)

        Returns:
            MarketAnalysis ou None se falhar
        """
        url = f"{self.base_url}/functions/v1/analyze-market"

        payload = {
            "symbol": symbol,
            "timeframe": timeframe,
            "limit": limit
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return self._parse_analysis(data)
                    else:
                        error_text = await response.text()
                        logger.error(f"Supabase API error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Failed to call Supabase API: {e}")
            return None

    def _parse_analysis(self, data: Dict[str, Any]) -> MarketAnalysis:
        """Converte resposta da API para MarketAnalysis"""

        indicators = data.get("indicators", {})
        volume = data.get("volumeAnalysis", {})
        structure = data.get("structure", {})
        trade_plan = data.get("tradePlan", {})
        confidence = data.get("confidence", {})
        divergence = data.get("divergence", {})

        return MarketAnalysis(
            symbol=data.get("symbol", ""),
            timeframe=data.get("timeframe", ""),
            current_price=data.get("currentPrice", 0),

            # Indicadores
            rsi14=indicators.get("rsi14", 50),
            atr14=indicators.get("atr14", 0),
            ma20=indicators.get("ma20", 0),
            ma50=indicators.get("ma50", 0),
            ma200=indicators.get("ma200", 0),
            adx=indicators.get("adx", 0),
            adx_trend=indicators.get("adxTrend", "weak"),

            # Volume
            avg_volume=volume.get("avgVolume", 0),
            current_volume=volume.get("currentVolume", 0),
            relative_volume=volume.get("relativeVolume", 1),
            is_volume_spike=volume.get("isVolumeSpike", False),

            # Estrutura
            bias=structure.get("bias", "neutral"),
            pattern=structure.get("pattern", ""),

            # Trade Plan
            side=trade_plan.get("side"),
            entry=trade_plan.get("entry"),
            stop=trade_plan.get("stop"),
            targets=trade_plan.get("targets", []),
            risk_reward=trade_plan.get("riskRewardRatio", 0),
            setup=trade_plan.get("setup", ""),

            # Confiança
            confidence_score=confidence.get("score", 0),
            confidence_grade=confidence.get("grade", "F"),

            # AI
            ai_summary=data.get("aiSummary", ""),

            # Divergência
            divergence_type=divergence.get("type"),
            divergence_category=divergence.get("category"),

            # Níveis
            levels=data.get("levels", []),

            # Raw
            raw_data=data
        )

    async def scan_confluence(
        self,
        symbols: Optional[list] = None,
        timeframe: str = "4h",
        min_confidence: int = 50
    ) -> Optional[Dict[str, Any]]:
        """
        Escaneia múltiplos pares buscando confluências

        Args:
            symbols: Lista de símbolos (usa default se None)
            timeframe: Timeframe para análise
            min_confidence: Score mínimo de confiança

        Returns:
            Resultado do scan ou None se falhar
        """
        url = f"{self.base_url}/functions/v1/scan-confluence"

        payload = {
            "timeframe": timeframe,
            "minConfidence": min_confidence
        }

        if symbols:
            payload["symbols"] = symbols

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_text = await response.text()
                        logger.error(f"Scan confluence error {response.status}: {error_text}")
                        return None

        except Exception as e:
            logger.error(f"Failed to scan confluence: {e}")
            return None


def create_supabase_analyzer(config: Dict[str, Any]) -> Optional[SupabaseAnalyzer]:
    """
    Factory para criar SupabaseAnalyzer a partir da config

    Args:
        config: Configuração com 'supabase' section

    Returns:
        SupabaseAnalyzer ou None se não configurado
    """
    supabase_config = config.get("supabase", {})

    base_url = supabase_config.get("url")
    anon_key = supabase_config.get("anon_key")

    if not base_url or not anon_key:
        logger.warning("Supabase not configured - using local analysis")
        return None

    return SupabaseAnalyzer(base_url, anon_key)

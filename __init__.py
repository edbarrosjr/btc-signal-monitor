"""BTC Signal Monitor - Módulo principal"""
from .config import load_config, TRADING_PRESETS
from .exchanges import get_exchange, Candle

__all__ = ["load_config", "TRADING_PRESETS", "get_exchange", "Candle"]

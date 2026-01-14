"""
Módulo de Exchanges
Suporta múltiplas exchanges com interface unificada
"""

import asyncio
import aiohttp
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass
import hmac
import hashlib
import time


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


class BaseExchange(ABC):
    """Interface base para exchanges"""
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
    
    @abstractmethod
    async def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        """Busca candles/klines"""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Busca ticker atual"""
        pass
    
    @abstractmethod
    async def get_orderbook(self, symbol: str, depth: int = 10) -> Dict[str, Any]:
        """Busca order book"""
        pass


class CryptoComExchange(BaseExchange):
    """Exchange Crypto.com"""
    
    BASE_URL = "https://api.crypto.com/exchange/v1"
    
    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "6h": "6h",
        "12h": "12h",
        "1d": "1D",
        "1D": "1D",
        "1w": "1W",
        "1W": "1W",
    }
    
    async def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        tf = self.TIMEFRAME_MAP.get(timeframe, timeframe)
        url = f"{self.BASE_URL}/public/get-candlestick"
        params = {
            "instrument_name": symbol,
            "timeframe": tf
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    candles = []
                    
                    for item in data.get("result", {}).get("data", []):
                        try:
                            ts = item.get("timestamp", item.get("t"))
                            if isinstance(ts, str):
                                timestamp = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                            else:
                                timestamp = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                            
                            candle = Candle(
                                timestamp=timestamp,
                                open=float(item.get("open", item.get("o"))),
                                high=float(item.get("high", item.get("h"))),
                                low=float(item.get("low", item.get("l"))),
                                close=float(item.get("close", item.get("c"))),
                                volume=float(item.get("volume", item.get("v", 0)))
                            )
                            candles.append(candle)
                        except Exception as e:
                            continue
                    
                    candles.sort(key=lambda x: x.timestamp)
                    return candles[-limit:]
                
                return []
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/public/get-ticker"
        params = {"instrument_name": symbol}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get("result", {}).get("data", [{}])[0]
                    return {
                        "symbol": symbol,
                        "last": float(result.get("a", 0)),
                        "bid": float(result.get("b", 0)),
                        "ask": float(result.get("k", 0)),
                        "volume_24h": float(result.get("v", 0)),
                        "change_24h": float(result.get("c", 0)),
                    }
                return {}
    
    async def get_orderbook(self, symbol: str, depth: int = 10) -> Dict[str, Any]:
        url = f"{self.BASE_URL}/public/get-book"
        params = {"instrument_name": symbol, "depth": depth}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get("result", {}).get("data", [{}])[0]
                    return {
                        "bids": [(float(b["price"]), float(b["qty"])) for b in result.get("bids", [])],
                        "asks": [(float(a["price"]), float(a["qty"])) for a in result.get("asks", [])]
                    }
                return {"bids": [], "asks": []}


class BinanceExchange(BaseExchange):
    """Exchange Binance Spot (API pública)"""

    BASE_URL = "https://api.binance.com"

    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1D": "1d",
        "1w": "1w",
    }

    SYMBOL_MAP = {
        "BTCUSD-PERP": "BTCUSDT",
        "BTCUSDT": "BTCUSDT",
        "ETHUSD-PERP": "ETHUSDT",
        "ETHUSDT": "ETHUSDT",
    }

    async def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        sym = self.SYMBOL_MAP.get(symbol, symbol)
        tf = self.TIMEFRAME_MAP.get(timeframe, timeframe)
        url = f"{self.BASE_URL}/api/v3/klines"
        params = {
            "symbol": sym,
            "interval": tf,
            "limit": limit
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        data = await response.json()
                        candles = []

                        for item in data:
                            candle = Candle(
                                timestamp=datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc),
                                open=float(item[1]),
                                high=float(item[2]),
                                low=float(item[3]),
                                close=float(item[4]),
                                volume=float(item[5])
                            )
                            candles.append(candle)

                        print(f"[Binance] ✅ {len(candles)} candles recebidos para {sym}")
                        return candles
                    else:
                        error_text = await response.text()
                        print(f"[Binance] ❌ Erro HTTP {response.status}: {error_text[:200]}")
                        return []
        except Exception as e:
            print(f"[Binance] ❌ Erro de conexão: {e}")
            return []

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        sym = self.SYMBOL_MAP.get(symbol, symbol)
        url = f"{self.BASE_URL}/api/v3/ticker/24hr"
        params = {"symbol": sym}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "symbol": symbol,
                        "last": float(data.get("lastPrice", 0)),
                        "bid": float(data.get("bidPrice", 0)),
                        "ask": float(data.get("askPrice", 0)),
                        "volume_24h": float(data.get("volume", 0)),
                        "change_24h": float(data.get("priceChangePercent", 0)),
                    }
                return {}
    
    async def get_orderbook(self, symbol: str, depth: int = 10) -> Dict[str, Any]:
        sym = self.SYMBOL_MAP.get(symbol, symbol)
        url = f"{self.BASE_URL}/fapi/v1/depth"
        params = {"symbol": sym, "limit": depth}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "bids": [(float(b[0]), float(b[1])) for b in data.get("bids", [])],
                        "asks": [(float(a[0]), float(a[1])) for a in data.get("asks", [])]
                    }
                return {"bids": [], "asks": []}


class BybitExchange(BaseExchange):
    """Exchange Bybit"""
    
    BASE_URL = "https://api.bybit.com"
    
    TIMEFRAME_MAP = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "4h": "240",
        "1d": "D",
        "1D": "D",
        "1w": "W",
    }
    
    SYMBOL_MAP = {
        "BTCUSD-PERP": "BTCUSDT",
        "ETHUSD-PERP": "ETHUSDT",
    }
    
    async def get_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Candle]:
        sym = self.SYMBOL_MAP.get(symbol, symbol)
        tf = self.TIMEFRAME_MAP.get(timeframe, timeframe)
        url = f"{self.BASE_URL}/v5/market/kline"
        params = {
            "category": "linear",
            "symbol": sym,
            "interval": tf,
            "limit": limit
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        data = await response.json()

                        if data.get("retCode") != 0:
                            print(f"[Bybit] ❌ API Error: {data.get('retMsg')}")
                            return []

                        candles = []
                        for item in data.get("result", {}).get("list", []):
                            candle = Candle(
                                timestamp=datetime.fromtimestamp(int(item[0]) / 1000, tz=timezone.utc),
                                open=float(item[1]),
                                high=float(item[2]),
                                low=float(item[3]),
                                close=float(item[4]),
                                volume=float(item[5])
                            )
                            candles.append(candle)

                        candles.sort(key=lambda x: x.timestamp)
                        print(f"[Bybit] ✅ {len(candles)} candles recebidos para {sym}")
                        return candles
                    else:
                        error_text = await response.text()
                        print(f"[Bybit] ❌ Erro HTTP {response.status}: {error_text[:200]}")
                        return []
        except Exception as e:
            print(f"[Bybit] ❌ Erro de conexão: {e}")
            return []
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        sym = self.SYMBOL_MAP.get(symbol, symbol)
        url = f"{self.BASE_URL}/v5/market/tickers"
        params = {"category": "linear", "symbol": sym}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get("result", {}).get("list", [{}])[0]
                    return {
                        "symbol": symbol,
                        "last": float(result.get("lastPrice", 0)),
                        "bid": float(result.get("bid1Price", 0)),
                        "ask": float(result.get("ask1Price", 0)),
                        "volume_24h": float(result.get("volume24h", 0)),
                        "change_24h": float(result.get("price24hPcnt", 0)) * 100,
                    }
                return {}
    
    async def get_orderbook(self, symbol: str, depth: int = 10) -> Dict[str, Any]:
        sym = self.SYMBOL_MAP.get(symbol, symbol)
        url = f"{self.BASE_URL}/v5/market/orderbook"
        params = {"category": "linear", "symbol": sym, "limit": depth}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = data.get("result", {})
                    return {
                        "bids": [(float(b[0]), float(b[1])) for b in result.get("b", [])],
                        "asks": [(float(a[0]), float(a[1])) for a in result.get("a", [])]
                    }
                return {"bids": [], "asks": []}


def get_exchange(name: str, api_key: Optional[str] = None, api_secret: Optional[str] = None) -> BaseExchange:
    """Factory para criar instância da exchange"""
    exchanges = {
        "cryptocom": CryptoComExchange,
        "crypto.com": CryptoComExchange,
        "binance": BinanceExchange,
        "bybit": BybitExchange,
    }
    
    exchange_class = exchanges.get(name.lower())
    if not exchange_class:
        raise ValueError(f"Exchange não suportada: {name}. Opções: {list(exchanges.keys())}")
    
    return exchange_class(api_key, api_secret)


# Teste rápido
async def test_exchanges():
    """Testa conexão com exchanges"""
    
    exchanges_to_test = ["cryptocom", "binance", "bybit"]
    symbol = "BTCUSD-PERP"
    
    for name in exchanges_to_test:
        print(f"\n{'='*50}")
        print(f"Testando {name.upper()}")
        print('='*50)
        
        try:
            exchange = get_exchange(name)
            
            # Testar candles
            candles = await exchange.get_candles(symbol, "1h", limit=5)
            if candles:
                print(f"✅ Candles: {len(candles)} recebidos")
                print(f"   Último: O:{candles[-1].open:.2f} H:{candles[-1].high:.2f} L:{candles[-1].low:.2f} C:{candles[-1].close:.2f}")
            else:
                print("❌ Candles: Nenhum dado")
            
            # Testar ticker
            ticker = await exchange.get_ticker(symbol)
            if ticker:
                print(f"✅ Ticker: ${ticker.get('last', 0):,.2f}")
            else:
                print("❌ Ticker: Nenhum dado")
            
        except Exception as e:
            print(f"❌ Erro: {e}")


if __name__ == "__main__":
    asyncio.run(test_exchanges())

#!/usr/bin/env python3
"""
Script de teste - Verifica se tudo está configurado corretamente
Execute antes de fazer deploy: python test_config.py
"""

import asyncio
import os
import sys

# Carregar .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv não instalado, usando apenas variáveis de ambiente do sistema")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import aiohttp


async def test_exchange():
    """Testa conexão com a exchange"""
    print("\n" + "="*50)
    print("🔌 TESTANDO CONEXÃO COM EXCHANGE")
    print("="*50)
    
    exchange = os.getenv("EXCHANGE", "binance")
    symbol = os.getenv("SYMBOL", "BTCUSD-PERP")
    
    print(f"   Exchange: {exchange}")
    print(f"   Symbol: {symbol}")
    
    try:
        from src.exchanges import get_exchange
        ex = get_exchange(exchange)
        candles = await ex.get_candles(symbol, "1h", limit=5)
        
        if candles:
            print(f"   ✅ Conexão OK!")
            print(f"   📊 Último preço: ${candles[-1].close:,.2f}")
            return True
        else:
            print("   ❌ Nenhum dado retornado")
            return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


async def test_telegram():
    """Testa Telegram"""
    print("\n" + "="*50)
    print("📱 TESTANDO TELEGRAM")
    print("="*50)
    
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        print("   ⏭️  Não configurado (TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID ausente)")
        return None
    
    print(f"   Token: {token[:10]}...{token[-5:]}")
    print(f"   Chat ID: {chat_id}")
    
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": "🧪 Teste do BTC Signal Monitor - Configuração OK!",
            "parse_mode": "Markdown"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as r:
                if r.status == 200:
                    print("   ✅ Telegram OK! Mensagem enviada.")
                    return True
                else:
                    data = await r.json()
                    print(f"   ❌ Erro {r.status}: {data.get('description', 'Unknown')}")
                    return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


async def test_discord():
    """Testa Discord"""
    print("\n" + "="*50)
    print("🎮 TESTANDO DISCORD")
    print("="*50)
    
    webhook = os.getenv("DISCORD_WEBHOOK")
    
    if not webhook:
        print("   ⏭️  Não configurado (DISCORD_WEBHOOK ausente)")
        return None
    
    print(f"   Webhook: {webhook[:50]}...")
    
    try:
        payload = {"content": "🧪 Teste do BTC Signal Monitor - Configuração OK!"}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload) as r:
                if r.status in [200, 204]:
                    print("   ✅ Discord OK! Mensagem enviada.")
                    return True
                else:
                    print(f"   ❌ Erro {r.status}")
                    return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


async def test_webhook():
    """Testa Webhook genérico"""
    print("\n" + "="*50)
    print("🌐 TESTANDO WEBHOOK GENÉRICO")
    print("="*50)
    
    webhook = os.getenv("WEBHOOK_URL")
    
    if not webhook:
        print("   ⏭️  Não configurado (WEBHOOK_URL ausente)")
        return None
    
    print(f"   URL: {webhook}")
    
    try:
        payload = {
            "test": True,
            "message": "Teste do BTC Signal Monitor",
            "timestamp": "2026-01-14T00:00:00Z"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload) as r:
                if r.status == 200:
                    print("   ✅ Webhook OK!")
                    return True
                else:
                    print(f"   ⚠️  Status {r.status} (pode estar OK dependendo do servidor)")
                    return True
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


async def test_n8n():
    """Testa n8n"""
    print("\n" + "="*50)
    print("⚡ TESTANDO N8N")
    print("="*50)
    
    webhook = os.getenv("N8N_WEBHOOK")
    
    if not webhook:
        print("   ⏭️  Não configurado (N8N_WEBHOOK ausente)")
        return None
    
    print(f"   URL: {webhook}")
    
    try:
        payload = {
            "test": True,
            "signal_type": "TEST",
            "message": "Teste do BTC Signal Monitor"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=payload) as r:
                if r.status == 200:
                    print("   ✅ n8n OK!")
                    return True
                else:
                    print(f"   ⚠️  Status {r.status}")
                    return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False


def check_env_vars():
    """Verifica variáveis de ambiente"""
    print("\n" + "="*50)
    print("📋 VERIFICANDO VARIÁVEIS DE AMBIENTE")
    print("="*50)
    
    required = {
        "SYMBOL": os.getenv("SYMBOL", "BTCUSD-PERP"),
        "TIMEFRAME": os.getenv("TIMEFRAME", "1h"),
        "EXCHANGE": os.getenv("EXCHANGE", "binance"),
        "CHECK_INTERVAL": os.getenv("CHECK_INTERVAL", "60"),
    }
    
    trading = {
        "ENTRY_ZONE_MIN": os.getenv("ENTRY_ZONE_MIN", "94200"),
        "ENTRY_ZONE_MAX": os.getenv("ENTRY_ZONE_MAX", "94500"),
        "STOP_LOSS": os.getenv("STOP_LOSS", "93000"),
        "TP1": os.getenv("TP1", "95800"),
    }
    
    print("\n   Configuração Geral:")
    for k, v in required.items():
        status = "✅" if v else "❌"
        print(f"   {status} {k}: {v}")
    
    print("\n   Configuração do Trade:")
    for k, v in trading.items():
        print(f"   📊 {k}: ${float(v):,.0f}")
    
    print("\n   Notificações Configuradas:")
    notifications = {
        "TELEGRAM": bool(os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_CHAT_ID")),
        "DISCORD": bool(os.getenv("DISCORD_WEBHOOK")),
        "WEBHOOK": bool(os.getenv("WEBHOOK_URL")),
        "N8N": bool(os.getenv("N8N_WEBHOOK")),
    }
    
    any_configured = False
    for name, configured in notifications.items():
        status = "✅" if configured else "⬜"
        print(f"   {status} {name}")
        if configured:
            any_configured = True
    
    if not any_configured:
        print("\n   ⚠️  ATENÇÃO: Nenhuma notificação configurada!")
        print("   Configure pelo menos uma para receber os sinais.")
    
    return any_configured


async def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║        BTC SIGNAL MONITOR - TESTE DE CONFIGURAÇÃO        ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    # Verificar variáveis
    has_notification = check_env_vars()
    
    # Testar exchange
    exchange_ok = await test_exchange()
    
    # Testar notificações
    results = {
        "telegram": await test_telegram(),
        "discord": await test_discord(),
        "webhook": await test_webhook(),
        "n8n": await test_n8n(),
    }
    
    # Resumo
    print("\n" + "="*50)
    print("📊 RESUMO")
    print("="*50)
    
    print(f"\n   Exchange: {'✅ OK' if exchange_ok else '❌ FALHOU'}")
    
    notification_ok = False
    for name, result in results.items():
        if result is True:
            print(f"   {name.capitalize()}: ✅ OK")
            notification_ok = True
        elif result is False:
            print(f"   {name.capitalize()}: ❌ FALHOU")
        else:
            print(f"   {name.capitalize()}: ⏭️  Não configurado")
    
    print("\n" + "="*50)
    
    if exchange_ok and notification_ok:
        print("🎉 TUDO PRONTO! Pode fazer o deploy.")
    elif exchange_ok and not notification_ok:
        print("⚠️  Exchange OK, mas configure pelo menos uma notificação!")
    else:
        print("❌ Corrija os erros antes de fazer deploy.")
    
    print("="*50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

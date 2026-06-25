import re

FINANCE_KEYWORDS = {
    # Forex & currency
    "forex", "fx", "currency", "usd", "eur", "gbp", "jpy", "aud", "cad", "chf",
    "cny", "idr", "exchange rate", "pip", "spread", "margin", "leverage",
    "bullish", "bearish", "support", "resistance",
    # Stocks & trading
    "stock", "stocks", "share", "shares", "equity", "equities", "etf", "etfs",
    "dividend", "dividends", "ipo", "capital", "market cap", "volume",
    "buy", "sell", "short", "long", "position", "hedge", "hedging",
    "bull market", "bear market", "rally", "correction", "crash",
    # Indices
    "idx", "s&p", "nasdaq", "dow jones", "ftse", "nikkei", "dax", "cac",
    "hangseng", "kospi", "sensex", "nifty",
    # Trading
    "trading", "trade", "trader", "day trading", "swing trade", "scalp",
    "technical analysis", "chart", "candlestick", "pattern", "breakout",
    "moving average", "rsi", "macd", "bollinger", "fibonacci",
    "crypto", "bitcoin", "btc", "ethereum", "eth", "altcoin",
    # Investment
    "invest", "investment", "investor", "investing", "portfolio",
    "asset", "assets", "wealth", "saving", "savings", "retirement",
    "bond", "bonds", "treasury", "yield", "interest rate", "inflation",
    "fundamental analysis", "p/e", "eps", "roi", "roic", "ebitda",
    # Economy
    "economy", "economic", "gdp", "cpi", "ppp", "employment", "unemployment",
    "central bank", "fed", "federal reserve", "monetary policy",
    "fiscal policy", "stimulus", "recession", "recovery", "growth",
    "export", "import", "trade war", "tariff", "sanction",
    # Indonesia specific
    "saham", "investasi", "reksadana", "obligasi", "pasar modal",
    "bursa", "forex indonesia", "trading indonesia", "idx composite",
    "ihsg", "krypto", "rupiah",
    # General finance
    "finance", "financial", "fintech", "bank", "banking", "loan", "credit",
    "mortgage", "insurance", "fund", "funding", "capital market",
    "profit", "revenue", "earnings", "income", "net worth",
    "valuation", "overvalued", "undervalued", "risk", "volatility",
}


def is_finance_related(text: str) -> bool:
    if not text:
        return False
    text_lower = text.lower()
    for kw in FINANCE_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def compute_score(text: str) -> float:
    """Return a simple ratio of matched keyword tokens to total words."""
    if not text:
        return 0.0
    words = re.findall(r"\w+", text.lower())
    if not words:
        return 0.0
    matches = sum(1 for w in words if w in FINANCE_KEYWORDS)
    return matches / len(words)

from trading_agent.data import DEFAULT_SYMBOLS, update_universe


if __name__ == "__main__":
    results = update_universe(DEFAULT_SYMBOLS, period="60d", interval="5m")
    for symbol, result in results.items():
        print(f"{symbol}: {result}")

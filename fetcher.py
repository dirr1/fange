import asyncio
import httpx
import requests
import json
from typing import List, Dict, Any
from predmarket import KalshiRest, PolymarketRest

class MarketFetcher:
    def __init__(self):
        self._async_client = None
        self._kalshi = None
        self._polymarket = None

    async def get_client(self):
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=30.0)
            self._kalshi = KalshiRest(self._async_client)
            self._polymarket = PolymarketRest(self._async_client)
        return self._async_client

    async def fetch_kalshi_markets(self) -> List[Dict[str, Any]]:
        try:
            await self.get_client()
            response = await self._kalshi.fetch_questions()
            data = response.model_dump()
            markets = []
            items = data.get('data', [])
            for item in items:
                for market in item.get('markets', []):
                    markets.append({
                        "platform": "Kalshi",
                        "event_ticker": item.get('ticker'),
                        "market_ticker": market.get('ticker'),
                        "question": market.get('title') or item.get('title'),
                        "outcomes": [
                            {"name": "Yes", "probability": (market.get('yes_price', 0) or 0) / 100.0, "volume": market.get('volume', 0)},
                            {"name": "No", "probability": (market.get('no_price', 0) or 0) / 100.0, "volume": market.get('volume', 0)}
                        ],
                        "id": market.get('ticker'),
                        "url": f"https://kalshi.com/markets/{item.get('ticker')}"
                    })
            return markets
        except Exception as e:
            print(f"Error fetching Kalshi: {e}")
            return []

    async def fetch_polymarket_markets(self) -> List[Dict[str, Any]]:
        try:
            await self.get_client()
            response = await self._polymarket.fetch_questions(limit=100)
            data_dump = response.model_dump()
            items = data_dump.get('data', [])
            markets = []
            for item in items:
                for market in item.get('markets', []):
                    outcomes = []
                    names = market.get('outcomes', ["Yes", "No"])
                    prices = market.get('outcomePrices', ["0.5", "0.5"])

                    if isinstance(names, str):
                        try:
                            names = json.loads(names)
                        except:
                            names = ["Yes", "No"]
                    if isinstance(prices, str):
                        try:
                            prices = json.loads(prices)
                        except:
                            prices = ["0.5", "0.5"]

                    for i in range(len(names)):
                        prob = 0
                        try:
                            prob = float(prices[i]) if i < len(prices) else 0
                        except:
                            prob = 0
                        outcomes.append({
                            "name": names[i],
                            "probability": prob,
                            "volume": float(market.get('volume', 0) or 0)
                        })

                    markets.append({
                        "platform": "Polymarket",
                        "question": market.get('question') or item.get('question'),
                        "outcomes": outcomes,
                        "id": str(market.get('id')),
                        "url": f"https://polymarket.com/event/{item.get('slug')}"
                    })
            return markets
        except Exception as e:
            print(f"Error fetching Polymarket: {e}")
            return []

    def fetch_predictit_markets(self) -> List[Dict[str, Any]]:
        try:
            url = "https://www.predictit.org/api/marketdata/all/"
            response = requests.get(url, timeout=30)
            data = response.json()
            markets = []
            for market in data.get('markets', []):
                outcomes = []
                for contract in market.get('contracts', []):
                    outcomes.append({
                        "name": contract.get('name'),
                        "probability": float(contract.get('lastTradePrice') or 0),
                        "volume": 0
                    })
                markets.append({
                    "platform": "PredictIt",
                    "question": market.get('name'),
                    "outcomes": outcomes,
                    "id": str(market.get('id')),
                    "url": market.get('url')
                })
            return markets
        except Exception as e:
            print(f"Error fetching PredictIt: {e}")
            return []

    async def fetch_all(self):
        kalshi_task = self.fetch_kalshi_markets()
        poly_task = self.fetch_polymarket_markets()

        # Run predictit in a thread to keep it non-blocking
        loop = asyncio.get_running_loop()
        predictit_markets = await loop.run_in_executor(None, self.fetch_predictit_markets)

        kalshi_markets, poly_markets = await asyncio.gather(kalshi_task, poly_task)

        return kalshi_markets + poly_markets + predictit_markets

    async def close(self):
        if self._async_client:
            await self._async_client.aclose()

if __name__ == "__main__":
    async def test():
        fetcher = MarketFetcher()
        all_markets = await fetcher.fetch_all()
        print(f"Total markets fetched: {len(all_markets)}")
        await fetcher.close()

    asyncio.run(test())

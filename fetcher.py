import os
import asyncio
import httpx
import requests
import json
from typing import List, Dict, Any, Optional
from predmarket import KalshiRest, PolymarketRest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MarketFetcher:
    def __init__(self):
        self._async_client = None
        self._kalshi = None
        self._polymarket = None

        # API Keys from environment if available
        self.kalshi_key_id = os.getenv("KALSHI_KEY_ID")
        self.kalshi_key_secret = os.getenv("KALSHI_KEY_SECRET")
        self.polymarket_api_key = os.getenv("POLYMARKET_API_KEY")

    async def get_client(self):
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=30.0)
            self._kalshi = KalshiRest(self._async_client)
            self._polymarket = PolymarketRest(self._async_client)
        return self._async_client

    async def fetch_kalshi_markets(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch markets from Kalshi.
        """
        try:
            await self.get_client()
            markets = []

            # Kalshi doesn't have a great 'search' in the SDK yet, so we fetch top questions and contracts
            # 1. Fetch questions (events)
            questions_resp = await self._kalshi.fetch_questions()
            q_data = questions_resp.model_dump()
            items = q_data.get('data', [])

            for item in items:
                ticker = item.get('event_ticker') or item.get('id')
                # Check if it matches query locally if provided
                if query and query.lower() not in item.get('title', '').lower():
                    continue

                raw = item.get('raw', {})
                nested_markets = item.get('markets', []) or raw.get('markets', [])

                if nested_markets:
                    for market in nested_markets:
                        markets.append({
                            "platform": "Kalshi",
                            "question": market.get('title') or item.get('title'),
                            "outcomes": [
                                {"name": "Yes", "probability": (market.get('yes_price', 0) or 0) / 100.0, "volume": market.get('volume', 0)},
                                {"name": "No", "probability": (market.get('no_price', 0) or 0) / 100.0, "volume": market.get('volume', 0)}
                            ],
                            "id": market.get('ticker'),
                            "url": f"https://kalshi.com/markets/{ticker}"
                        })

            # 2. Fetch contracts directly
            # If query is provided, we can't search via SDK easily, so we just fetch more and filter
            contracts_resp = await self._kalshi.fetch_contracts(limit=1000)
            c_data = contracts_resp.model_dump()
            for contract in c_data.get('data', []):
                if query and query.lower() not in contract.get('title', '').lower():
                    continue

                if any(m['id'] == contract.get('ticker') for m in markets):
                    continue

                raw_c = contract.get('raw', {})
                last_price = float(raw_c.get('last_price_dollars') or 0)
                if last_price == 0:
                    ask = float(raw_c.get('yes_ask_dollars') or 0)
                    bid = float(raw_c.get('yes_bid_dollars') or 0)
                    if ask > 0 and bid > 0: last_price = (ask + bid) / 2
                    elif ask > 0: last_price = ask
                    elif bid > 0: last_price = bid

                markets.append({
                    "platform": "Kalshi",
                    "question": contract.get('title'),
                    "outcomes": [
                        {"name": "Yes", "probability": last_price, "volume": float(raw_c.get('volume_fp', 0) or 0)},
                        {"name": "No", "probability": 1.0 - last_price, "volume": float(raw_c.get('volume_fp', 0) or 0)}
                    ],
                    "id": contract.get('ticker'),
                    "url": f"https://kalshi.com/markets/{contract.get('event_ticker')}"
                })

            return markets
        except Exception as e:
            print(f"Error fetching Kalshi: {e}")
            return []

    async def fetch_polymarket_markets(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch active markets from Polymarket using direct Gamma API.
        """
        try:
            url = "https://gamma-api.polymarket.com/events"
            params = {"active": "true", "limit": 100, "order": "volume", "ascending": "false"}
            if query:
                params["search"] = query

            resp = requests.get(url, params=params, timeout=30)
            events = resp.json()

            # If no results for query, try without search but with higher limit
            if query and not events:
                params.pop("search")
                params["limit"] = 250
                resp = requests.get(url, params=params, timeout=30)
                events = resp.json()

            markets = []
            for item in events:
                for market in item.get('markets', []):
                    if market.get('closed'): continue

                    outcomes_raw = market.get('outcomes', '["Yes", "No"]')
                    prices_raw = market.get('outcomePrices', '["0.5", "0.5"]')

                    try:
                        names = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                    except:
                        names, prices = ["Yes", "No"], [0.5, 0.5]

                    outcomes = []
                    for i, name in enumerate(names):
                        prob = 0.0
                        try: prob = float(prices[i]) if i < len(prices) else 0.0
                        except: prob = 0.0
                        outcomes.append({
                            "name": name,
                            "probability": prob,
                            "volume": float(market.get('volume', 0) or 0)
                        })

                    markets.append({
                        "platform": "Polymarket",
                        "question": market.get('question') or item.get('title'),
                        "outcomes": outcomes,
                        "id": str(market.get('id')),
                        "url": f"https://polymarket.com/event/{item.get('slug')}"
                    })
            return markets
        except Exception as e:
            print(f"Error fetching Polymarket: {e}")
            return []

    def fetch_predictit_markets(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            url = "https://www.predictit.org/api/marketdata/all/"
            response = requests.get(url, timeout=30)
            data = response.json()
            markets = []
            for market in data.get('markets', []):
                # Local filtering for PredictIt as they don't have a search API
                if query and query.lower() not in market.get('name', '').lower():
                    continue

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

    async def fetch_all(self, query: Optional[str] = None):
        kalshi_task = self.fetch_kalshi_markets(query=query)
        poly_task = self.fetch_polymarket_markets(query=query)

        loop = asyncio.get_running_loop()
        predictit_markets = await loop.run_in_executor(None, self.fetch_predictit_markets, query)

        kalshi_markets, poly_markets = await asyncio.gather(kalshi_task, poly_task)

        return kalshi_markets + poly_markets + predictit_markets

    async def close(self):
        if self._async_client:
            await self._async_client.aclose()

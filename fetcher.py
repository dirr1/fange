import os
import asyncio
import httpx
import json
import logging
from typing import List, Dict, Any, Optional
from predmarket import KalshiRest, PolymarketRest
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

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
        try:
            await self.get_client()
            markets = []

            # Fetch a large batch of contracts and filter locally for best recall
            contracts_resp = await self._kalshi.fetch_contracts(limit=1000)
            c_data = contracts_resp.model_dump()

            for contract in c_data.get('data', []):
                title = contract.get('title', '')
                if query and query.lower() not in title.lower():
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
                    "question": title,
                    "outcomes": [
                        {"name": "Yes", "probability": last_price, "volume": float(raw_c.get('volume_fp', 0) or 0)},
                        {"name": "No", "probability": 1.0 - last_price, "volume": float(raw_c.get('volume_fp', 0) or 0)}
                    ],
                    "id": contract.get('ticker'),
                    "url": f"https://kalshi.com/markets/{contract.get('event_ticker')}"
                })

            return markets
        except Exception as e:
            logger.error(f"Error fetching Kalshi: {e}")
            return []

    async def fetch_polymarket_markets(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            client = await self.get_client()
            url = "https://gamma-api.polymarket.com/events"
            params = {"active": "true", "limit": 1000, "order": "volume", "ascending": "false"}

            headers = {}
            if self.polymarket_api_key:
                headers["Authorization"] = f"Bearer {self.polymarket_api_key}"

            resp = await client.get(url, params=params, headers=headers)
            events = resp.json()

            markets = []
            for item in events:
                title = item.get('title', '')
                # Filter events by query
                if query and query.lower() not in title.lower():
                    # Also check question in nested markets
                    match_found = False
                    for market in item.get('markets', []):
                        if query.lower() in market.get('question', '').lower():
                            match_found = True
                            break
                    if not match_found:
                        continue

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
                        "question": market.get('question') or title,
                        "outcomes": outcomes,
                        "id": str(market.get('id')),
                        "url": f"https://polymarket.com/event/{item.get('slug')}"
                    })
            return markets
        except Exception as e:
            logger.error(f"Error fetching Polymarket: {e}")
            return []

    async def fetch_predictit_markets(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            client = await self.get_client()
            url = "https://www.predictit.org/api/marketdata/all/"
            response = await client.get(url)
            data = response.json()
            markets = []
            for market in data.get('markets', []):
                name = market.get('name', '')
                if query and query.lower() not in name.lower():
                    continue

                outcomes = []
                # PredictIt volume is per-contract in their UI, but API has less detail
                # We'll use 0 for now as it's not directly in the /all/ API summary
                for contract in market.get('contracts', []):
                    outcomes.append({
                        "name": contract.get('name'),
                        "probability": float(contract.get('lastTradePrice') or 0),
                        "volume": 0
                    })
                markets.append({
                    "platform": "PredictIt",
                    "question": name,
                    "outcomes": outcomes,
                    "id": str(market.get('id')),
                    "url": market.get('url')
                })
            return markets
        except Exception as e:
            logger.error(f"Error fetching PredictIt: {e}")
            return []

    async def fetch_manifold_markets(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            client = await self.get_client()
            term = query or ""
            url = f"https://api.manifold.markets/v0/search-markets?term={term}&limit=100"
            resp = await client.get(url)
            data = resp.json()
            markets = []
            for m in data:
                if m.get('outcomeType') not in ['BINARY', 'PSEUDO_NUMERIC']:
                    continue
                prob = m.get('probability') or 0.5
                markets.append({
                    "platform": "Manifold",
                    "question": m.get('question'),
                    "outcomes": [
                        {"name": "Yes", "probability": float(prob), "volume": float(m.get('volume', 0))},
                        {"name": "No", "probability": 1.0 - float(prob), "volume": float(m.get('volume', 0))}
                    ],
                    "id": m.get('id'),
                    "url": m.get('url')
                })
            return markets
        except Exception as e:
            logger.error(f"Error fetching Manifold: {e}")
            return []

    async def fetch_forecastex_markets(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        # ForecastEx is institutional (IBKR) and requires TWS API / Gateway.
        # This stub represents the platform's support in the aggregator.
        return []

    async def fetch_all(self, query: Optional[str] = None):
        results = await asyncio.gather(
            self.fetch_kalshi_markets(query=query),
            self.fetch_polymarket_markets(query=query),
            self.fetch_manifold_markets(query=query),
            self.fetch_predictit_markets(query=query),
            self.fetch_forecastex_markets(query=query)
        )

        all_markets = []
        for r in results:
            all_markets.extend(r)

        # Robinhood routes to Kalshi
        kalshi_results = [m for m in all_markets if m['platform'] == "Kalshi"]
        for m in kalshi_results:
            m_copy = m.copy()
            m_copy['platform'] = "Robinhood"
            m_copy['url'] = "https://robinhood.com/prediction-markets"
            all_markets.append(m_copy)

        return all_markets

    async def close(self):
        if self._async_client:
            await self._async_client.aclose()

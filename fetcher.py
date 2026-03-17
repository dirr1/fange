import os
import asyncio
import httpx
import json
import logging
import csv
from io import StringIO
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from predmarket import KalshiRest, PolymarketRest
from dotenv import load_dotenv
from exa_py import Exa

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class MarketFetcher:
    def __init__(self):
        self._async_client = None
        self._kalshi = None
        self._polymarket = None

        # API Keys from environment
        self.kalshi_key_id = os.getenv("KALSHI_KEY_ID")
        self.kalshi_key_secret = os.getenv("KALSHI_KEY_SECRET")
        self.polymarket_api_key = os.getenv("POLYMARKET_API_KEY")

        exa_key = os.getenv("EXA_API_KEY")
        self.exa = Exa(exa_key) if exa_key else None

    async def get_client(self):
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(timeout=30.0)
            self._kalshi = KalshiRest(self._async_client)
            self._polymarket = PolymarketRest(self._async_client)
        return self._async_client

    def _matches_query(self, title: str, query: Optional[str]) -> bool:
        if not query:
            return True
        keywords = query.lower().split()
        title_lower = title.lower()
        return any(k in title_lower for k in keywords)

    async def fetch_kalshi_markets(self, query: Optional[str] = None) -> List[Dict[str, Any]]:
        try:
            await self.get_client()
            markets = []
            contracts_resp = await self._kalshi.fetch_contracts(limit=1000)
            c_data = contracts_resp.model_dump()
            for contract in c_data.get('data', []):
                title = contract.get('title', '')
                if not self._matches_query(title, query):
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
                if not self._matches_query(title, query):
                    match_found = False
                    for market in item.get('markets', []):
                        if self._matches_query(market.get('question', ''), query):
                            match_found = True
                            break
                    if not match_found: continue
                for market in item.get('markets', []):
                    if market.get('closed'): continue
                    outcomes_raw = market.get('outcomes', '["Yes", "No"]')
                    prices_raw = market.get('outcomePrices', '["0.5", "0.5"]')
                    try:
                        names = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
                        prices = json.loads(prices_raw) if isinstance(prices_raw, str) else prices_raw
                    except: names, prices = ["Yes", "No"], [0.5, 0.5]
                    outcomes = []
                    for i, name in enumerate(names):
                        prob = 0.0
                        try: prob = float(prices[i]) if i < len(prices) else 0.0
                        except: prob = 0.0
                        outcomes.append({"name": name, "probability": prob, "volume": float(market.get('volume', 0) or 0)})
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
                if not self._matches_query(name, query): continue
                outcomes = []
                for contract in market.get('contracts', []):
                    outcomes.append({"name": contract.get('name'), "probability": float(contract.get('lastTradePrice') or 0), "volume": 0})
                markets.append({"platform": "PredictIt", "question": name, "outcomes": outcomes, "id": str(market.get('id')), "url": market.get('url')})
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
                if m.get('outcomeType') not in ['BINARY', 'PSEUDO_NUMERIC']: continue
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
        try:
            client = await self.get_client()
            dates_to_try = [datetime.now().strftime("%Y%m%d"), (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")]
            content = None
            for date_str in dates_to_try:
                url = f"https://forecastex.com/api/download?type=prices&date={date_str}"
                resp = await client.get(url)
                if resp.status_code == 200:
                    content = resp.text
                    break
            if not content: return []
            markets_map = {}
            f = StringIO(content)
            reader = csv.DictReader(f)
            for row in reader:
                contract_id = row['event_contract']
                if query and query.lower() not in contract_id.lower(): continue
                subtype, price = row['subtype'].upper(), float(row['end_price'] or 0)
                if contract_id not in markets_map: markets_map[contract_id] = {"yes": 0.0, "no": 0.0, "oi": 0}
                if subtype == "YES": markets_map[contract_id]["yes"] = price
                elif subtype == "NO": markets_map[contract_id]["no"] = price
                markets_map[contract_id]["oi"] += int(row.get('open_interest', 0) or 0)
            markets = []
            for cid, data in markets_map.items():
                markets.append({
                    "platform": "ForecastEx",
                    "question": f"ForecastEx Contract: {cid}",
                    "outcomes": [{"name": "Yes", "probability": data["yes"], "volume": data["oi"]}, {"name": "No", "probability": data["no"], "volume": data["oi"]}],
                    "id": cid,
                    "url": "https://forecastex.com/markets"
                })
            return markets
        except Exception as e:
            logger.error(f"Error fetching ForecastEx: {e}")
            return []

    async def fetch_exa_markets(self, query: str) -> List[Dict[str, Any]]:
        """
        Use Exa to find relevant prediction markets across the web.
        """
        if not self.exa or not query:
            return []
        try:
            # Search for prediction markets related to the query
            search_query = f"prediction market probability for {query}"
            response = self.exa.search(
                search_query,
                num_results=10,
                use_autoprompt=True,
                include_domains=["polymarket.com", "kalshi.com", "predictit.org", "manifold.markets", "forecastex.com"]
            )
            markets = []
            for result in response.results:
                # Exa results don't have probability directly, but they find relevant URLs
                # We can't easily extract prob here without LLM, but we add them as candidates
                markets.append({
                    "platform": "Exa (Web)",
                    "question": result.title,
                    "outcomes": [],
                    "id": result.id,
                    "url": result.url,
                    "text": result.text[:500] if hasattr(result, 'text') else ""
                })
            return markets
        except Exception as e:
            logger.error(f"Exa search failed: {e}")
            return []

    async def fetch_all(self, query: Optional[str] = None):
        tasks = [
            self.fetch_kalshi_markets(query=query),
            self.fetch_polymarket_markets(query=query),
            self.fetch_manifold_markets(query=query),
            self.fetch_predictit_markets(query=query),
            self.fetch_forecastex_markets(query=query)
        ]
        if query and self.exa:
            tasks.append(self.fetch_exa_markets(query))

        results = await asyncio.gather(*tasks)
        all_markets = []
        for r in results:
            all_markets.extend(r)
        return all_markets

    async def close(self):
        if self._async_client:
            await self._async_client.aclose()

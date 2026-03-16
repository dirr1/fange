import asyncio
import time
import requests
import threading
from typing import List, Dict, Any, Callable
from fetcher import MarketFetcher
from aggregator import MarketAggregator

class RealTimeTracker:
    def __init__(self, fetcher_factory: Callable[[], MarketFetcher], aggregator: MarketAggregator):
        self.fetcher_factory = fetcher_factory
        self.aggregator = aggregator
        self.tracking_jobs = {} # query -> {webhook_url, last_prob, interval}
        self.is_running = False
        self._thread = None
        self._loop = None

    def add_tracking_job(self, query: str, webhook_url: str, interval: int = 60):
        self.tracking_jobs[query] = {
            "webhook_url": webhook_url,
            "last_prob": None,
            "interval": interval,
            "last_run": 0
        }

    def remove_tracking_job(self, query: str):
        if query in self.tracking_jobs:
            del self.tracking_jobs[query]

    def start_in_background(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        # Each loop needs its own fetcher instance to have its own AsyncClient
        self.fetcher = self.fetcher_factory()
        try:
            self._loop.run_until_complete(self.run())
        finally:
            self._loop.run_until_complete(self.fetcher.close())
            self._loop.close()

    async def run(self):
        while self.is_running:
            start_time = time.time()
            if not self.tracking_jobs:
                await asyncio.sleep(10)
                continue

            try:
                # Fetch all markets once per cycle
                all_markets = await self.fetcher.fetch_all()

                for query, job in list(self.tracking_jobs.items()):
                    if start_time - job["last_run"] >= job["interval"]:
                        matched = self.aggregator.aggregate_markets(query, all_markets)
                        if matched:
                            probs = self.aggregator.calculate_aggregate_probability(matched)
                            current_prob = probs.get("accuracy_weighted", 0)

                            # Update if first time or changed by > 1%
                            if job["last_prob"] is None or abs(current_prob - job["last_prob"]) > 0.01:
                                self.send_discord_update(query, current_prob, probs, job["webhook_url"])
                                job["last_prob"] = current_prob

                        job["last_run"] = start_time
            except Exception as e:
                print(f"Error in tracker loop: {e}")

            elapsed = time.time() - start_time
            sleep_time = max(1, 10 - elapsed)
            await asyncio.sleep(sleep_time)

    def send_discord_update(self, query: str, prob: float, all_probs: Dict[str, float], webhook_url: str):
        if not webhook_url:
            return

        payload = {
            "content": f"🔔 **Probability Update for: {query}**",
            "embeds": [{
                "title": f"Market Data: {query}",
                "description": f"The aggregate probability has been updated based on the latest market data.",
                "fields": [
                    {"name": "Accuracy Weighted 🎯", "value": f"**{prob:.2%}**", "inline": False},
                    {"name": "Simple Average", "value": f"{all_probs.get('simple_average', 0):.2%}", "inline": True},
                    {"name": "Liquidity Weighted", "value": f"{all_probs.get('liquidity_weighted', 0):.2%}", "inline": True}
                ],
                "color": 3447003, # Blue
                "footer": {"text": "Prediction Market Aggregator"},
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }]
        }
        try:
            resp = requests.post(webhook_url, json=payload, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"Failed to send Discord notification for '{query}': {e}")

    def stop(self):
        self.is_running = False
        if self._loop:
            self._loop.stop()

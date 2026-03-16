import re
import os
import logging
import json
import asyncio
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher
import google.generativeai as genai

# Use a named logger for this module
logger = logging.getLogger(__name__)

class MarketAggregator:
    def __init__(self, accuracy_weights: Dict[str, float] = None):
        # Default accuracy weights based on user-provided statistics
        self.accuracy_weights = accuracy_weights or {
            "PredictIt": 0.93,
            "ForecastEx": 0.90,
            "Manifold": 0.87,
            "Kalshi": 0.78,
            "Robinhood": 0.78,
            "Polymarket": 0.67
        }

        # Initialize Gemini if API key is present
        self.gemini_enabled = False
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                self.model = genai.GenerativeModel('gemini-2.0-flash')
                self.gemini_enabled = True
                logger.info("Gemini AI enabled for semantic search and summarization.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        text = str(text).lower()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        fillers = ["the", "be", "a", "an"]
        words = [w for w in text.split() if w not in fillers]
        return " ".join(words)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        n1 = self._normalize_text(text1)
        n2 = self._normalize_text(text2)
        if not n1 or not n2:
            return 0.0
        return SequenceMatcher(None, n1, n2).ratio()

    async def semantic_filter(self, query: str, markets: List[Dict[str, Any]], threshold: float = 0.5) -> List[Dict[str, Any]]:
        """
        Use Gemini to score relevance of market titles to the query.
        """
        if not self.gemini_enabled or not markets:
            return markets

        # Group markets to avoid hitting token limits/rate limits too hard
        # We'll just process them in one batch if reasonably sized
        titles = [m['question'] for m in markets]
        prompt = f"""
        User Search Query: "{query}"

        Market Titles:
        {json.dumps(titles, indent=2)}

        Task: For each market title, provide a relevance score between 0.0 and 1.0.
        A score of 1.0 means the market is exactly what the user is looking for or highly related.
        A score of 0.0 means it is irrelevant.
        Return ONLY a JSON list of scores in the same order as the input titles.
        Example output: [0.9, 0.1, 0.5]
        """

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            text = response.text.strip()
            # Try to find the JSON list in the response
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                scores = json.loads(match.group())
                if len(scores) == len(markets):
                    matched = []
                    for m, score in zip(markets, scores):
                        if score >= threshold:
                            m['similarity'] = score
                            matched.append(m)
                    return matched
        except Exception as e:
            logger.error(f"Gemini semantic filter failed: {e}")

        return markets

    def aggregate_markets(self, query: str, all_markets: List[Dict[str, Any]], threshold: float = 0.4) -> List[Dict[str, Any]]:
        """
        Standard fuzzy matching.
        """
        matched = []
        for m in all_markets:
            sim = self.calculate_similarity(query, m['question'])
            if sim >= threshold or query.lower() in m['question'].lower():
                m['similarity'] = sim
                matched.append(m)

        matched.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return matched

    def calculate_aggregate_probability(self, group: List[Dict[str, Any]], outcome_name: str = "Yes") -> Dict[str, float]:
        if not group:
            return {}

        target = (outcome_name or "Yes").lower()
        results = {"simple_average": 0.0, "liquidity_weighted": 0.0, "accuracy_weighted": 0.0}

        probabilities, volumes, weights = [], [], []

        for m in group:
            prob, vol = None, 0
            for o in m['outcomes']:
                o_name = str(o.get('name') or "").lower()
                if target in o_name or o_name in target:
                    prob, vol = o['probability'], o.get('volume', 0) or 0
                    break

            if prob is None and m['outcomes']:
                prob, vol = m['outcomes'][0]['probability'], m['outcomes'][0].get('volume', 0) or 0

            if prob is not None:
                probabilities.append(float(prob))
                volumes.append(float(vol))
                weights.append(float(self.accuracy_weights.get(m['platform'], 0.5)))

        if not probabilities:
            return results

        results["simple_average"] = sum(probabilities) / len(probabilities)
        total_vol = sum(volumes)
        results["liquidity_weighted"] = sum(p * v for p, v in zip(probabilities, volumes)) / total_vol if total_vol > 0 else results["simple_average"]
        total_weight = sum(weights)
        results["accuracy_weighted"] = sum(p * w for p, w in zip(probabilities, weights)) / total_weight if total_weight > 0 else results["simple_average"]

        return results

    async def generate_summary(self, query: str, stats: Dict[str, float], matched_count: int) -> str:
        if not self.gemini_enabled:
            return ""

        prompt = f"""
        User Query: "{query}"
        Aggregated Market Stats:
        - Accuracy Weighted Prob: {stats.get('accuracy_weighted', 0):.2%}
        - Simple Average: {stats.get('simple_average', 0):.2%}
        - Liquidity Weighted: {stats.get('liquidity_weighted', 0):.2%}
        - Markets Analyzed: {matched_count}

        Task: Provide a concise, professional one-sentence summary of the market's current prediction for this topic.
        Acknowledge the degree of consensus among platforms.
        """

        try:
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Gemini summary generation failed: {e}")
            return ""

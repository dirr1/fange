import re
import os
import logging
import json
import asyncio
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

from google import genai
import cohere
import anthropic
from openai import OpenAI
from groq import Groq

# Use a named logger for this module
logger = logging.getLogger(__name__)

class MarketAggregator:
    def __init__(self, accuracy_weights: Dict[str, float] = None):
        # Default accuracy weights
        self.accuracy_weights = accuracy_weights or {
            "PredictIt": 0.93,
            "ForecastEx": 0.90,
            "Manifold": 0.87,
            "Kalshi": 0.78,
            "Robinhood": 0.78,
            "Polymarket": 0.67,
            "Exa (Web)": 0.50
        }

        # Initialize Tiered AI Components
        self.gemini_client = None
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                self.gemini_client = genai.Client(api_key=gemini_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {e}")

        self.cohere_client = None
        cohere_key = os.getenv("COHERE_API_KEY")
        if cohere_key:
            self.cohere_client = cohere.ClientV2(api_key=cohere_key)

        self.anthropic_client = None
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.anthropic_client = anthropic.Anthropic(api_key=anthropic_key)

        self.openai_client = None
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.openai_client = OpenAI(api_key=openai_key)

        self.groq_client = None
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            self.groq_client = Groq(api_key=groq_key)

    def _normalize_text(self, text: str) -> str:
        if not text: return ""
        text = str(text).lower()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        fillers = ["the", "be", "a", "an"]
        words = [w for w in text.split() if w not in fillers]
        return " ".join(words)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        n1 = self._normalize_text(text1)
        n2 = self._normalize_text(text2)
        if not n1 or not n2: return 0.0
        return SequenceMatcher(None, n1, n2).ratio()

    async def rerank_markets(self, query: str, markets: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Tiered Reranking using Cohere (if available), otherwise falling back to fuzzy.
        """
        if not markets:
            return []

        if self.cohere_client:
            try:
                documents = [m['question'] for m in markets]
                response = await asyncio.to_thread(
                    self.cohere_client.rerank,
                    model="rerank-english-v3.0",
                    query=query,
                    documents=documents,
                    top_n=top_n
                )

                reranked = []
                for res in response.results:
                    market = markets[res.index]
                    market['similarity'] = res.relevance_score
                    reranked.append(market)
                return reranked
            except Exception as e:
                logger.error(f"Cohere rerank failed: {e}")

        # Fallback to standard fuzzy matching if no Cohere
        matched = self.aggregate_markets(query, markets, threshold=0.4)
        return matched[:top_n]

    def aggregate_markets(self, query: str, all_markets: List[Dict[str, Any]], threshold: float = 0.4) -> List[Dict[str, Any]]:
        matched = []
        for m in all_markets:
            sim = self.calculate_similarity(query, m['question'])
            if sim >= threshold or query.lower() in m['question'].lower():
                m['similarity'] = sim
                matched.append(m)
        matched.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return matched

    async def extract_missing_data(self, markets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Use fast LLM (GPT-4o mini or Groq) to extract probabilities from markets that lack them (e.g. Exa results).
        """
        extracted = []
        for m in markets:
            if m.get('outcomes'):
                extracted.append(m)
                continue

            # If no outcomes, try to extract from text/title
            context = m.get('text', '') or m['question']
            if not context:
                extracted.append(m)
                continue

            prompt = f"""
            Extract prediction market probability from this text: "{context}"
            If a probability is mentioned for a "Yes" outcome, return it as a decimal between 0 and 1.
            If multiple probabilities exist, pick the most relevant one.
            If none found, return null.
            Return ONLY a JSON object like {{"probability": 0.65}} or {{"probability": null}}
            """

            prob = None
            try:
                if self.openai_client:
                    resp = await asyncio.to_thread(
                        self.openai_client.chat.completions.create,
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"}
                    )
                    data = json.loads(resp.choices[0].message.content)
                    prob = data.get('probability')
                elif self.groq_client:
                    resp = await asyncio.to_thread(
                        self.groq_client.chat.completions.create,
                        model="llama-3.1-8b-instant",
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"}
                    )
                    data = json.loads(resp.choices[0].message.content)
                    prob = data.get('probability')

                if prob is not None:
                    m['outcomes'] = [
                        {"name": "Yes", "probability": float(prob), "volume": 0},
                        {"name": "No", "probability": 1.0 - float(prob), "volume": 0}
                    ]
            except Exception as e:
                logger.error(f"Data extraction failed for {m['url']}: {e}")

            extracted.append(m)
        return extracted

    def calculate_aggregate_probability(self, group: List[Dict[str, Any]], outcome_name: str = "Yes") -> Dict[str, float]:
        if not group: return {}
        target = (outcome_name or "Yes").lower()
        results = {"simple_average": 0.0, "liquidity_weighted": 0.0, "accuracy_weighted": 0.0}
        probabilities, volumes, weights = [], [], []
        for m in group:
            prob, vol = None, 0
            if not m.get('outcomes'): continue
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
        if not probabilities: return results
        results["simple_average"] = sum(probabilities) / len(probabilities)
        total_vol = sum(volumes)
        results["liquidity_weighted"] = sum(p * v for p, v in zip(probabilities, volumes)) / total_vol if total_vol > 0 else results["simple_average"]
        total_weight = sum(weights)
        results["accuracy_weighted"] = sum(p * w for p, w in zip(probabilities, weights)) / total_weight if total_weight > 0 else results["simple_average"]
        return results

    async def synthesize_summary(self, query: str, markets: List[Dict[str, Any]], stats: Dict[str, float]) -> str:
        """
        Tiered Synthesis using Claude 3.5 Sonnet (if available), otherwise Gemini or fallback.
        """
        market_summary = []
        for m in markets[:10]:
            prob = "N/A"
            if m.get('outcomes'): prob = f"{m['outcomes'][0]['probability']:.1%}"
            market_summary.append(f"- [{m['platform']}] {m['question']}: {prob}")

        prompt = f"""
        User Query: "{query}"

        Aggregated Data:
        - Accuracy Weighted: {stats.get('accuracy_weighted', 0):.1%}
        - Simple Average: {stats.get('simple_average', 0):.1%}
        - Total Markets: {len(markets)}

        Detailed Markets:
        {"\n".join(market_summary)}

        Task: Provide a high-reasoning synthesis of these market predictions.
        Explain the consensus level and any notable outliers. Be professional and concise.
        """

        try:
            if self.anthropic_client:
                resp = await asyncio.to_thread(
                    self.anthropic_client.messages.create,
                    model="claude-sonnet-4-6",
                    max_tokens=300,
                    messages=[{"role": "user", "content": prompt}]
                )
                return resp.content[0].text.strip()
            elif self.gemini_client:
                resp = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model='gemini-2.0-flash',
                    contents=prompt
                )
                return resp.text.strip()
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")

        return f"Consensus probability is approximately {stats.get('accuracy_weighted', 0):.1%} across {len(markets)} markets."

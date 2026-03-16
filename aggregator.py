import re
import logging
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

# Set up logging to a file for debugging
logging.basicConfig(filename='aggregator.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

class MarketAggregator:
    def __init__(self, accuracy_weights: Dict[str, float] = None):
        # Default accuracy weights based on studies mentioned in instructions
        self.accuracy_weights = accuracy_weights or {
            "PredictIt": 0.93,
            "Kalshi": 0.78,
            "Polymarket": 0.67
        }

    def _normalize_text(self, text: str) -> str:
        if not text:
            return ""
        # Lowercase, remove special characters, remove common fillers
        text = str(text).lower()
        text = re.sub(r'[^a-z0-9\s]', '', text)
        # Remove common phrases that might differ between platforms
        fillers = ["will", "the", "be", "by", "in", "of", "a", "an", "at", "to", "how", "many"]
        words = [w for w in text.split() if w not in fillers]
        return " ".join(words)

    def calculate_similarity(self, text1: str, text2: str) -> float:
        n1 = self._normalize_text(text1)
        n2 = self._normalize_text(text2)
        if not n1 or not n2:
            return 0.0
        return SequenceMatcher(None, n1, n2).ratio()

    def aggregate_markets(self, query: str, all_markets: List[Dict[str, Any]], threshold: float = 0.6) -> List[Dict[str, Any]]:
        """
        Find markets matching the query.
        """
        matched = []
        for m in all_markets:
            sim = self.calculate_similarity(query, m['question'])
            # Also allow direct substring match for better recall
            if sim >= threshold or query.lower() in m['question'].lower():
                m['similarity'] = sim
                matched.append(m)

        # Sort by similarity
        matched.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return matched

    def calculate_aggregate_probability(self, group: List[Dict[str, Any]], outcome_name: str = "Yes") -> Dict[str, float]:
        """
        Given a group of markets, calculate aggregated probabilities.
        """
        if not group:
            return {}

        target = (outcome_name or "Yes").lower()

        results = {
            "simple_average": 0.0,
            "liquidity_weighted": 0.0,
            "accuracy_weighted": 0.0
        }

        probabilities = []
        volumes = []
        weights = []

        for m in group:
            prob = None
            vol = 0

            # 1. Try to find the specific outcome
            for o in m['outcomes']:
                o_name = str(o.get('name') or "").lower()
                if target in o_name or o_name in target:
                    prob = o['probability']
                    vol = o.get('volume', 0) or 0
                    break

            # 2. Fallback to first outcome if not found
            if prob is None and m['outcomes']:
                prob = m['outcomes'][0]['probability']
                vol = m['outcomes'][0].get('volume', 0) or 0

            if prob is not None:
                probabilities.append(float(prob))
                volumes.append(float(vol))
                weights.append(float(self.accuracy_weights.get(m['platform'], 0.5)))

        if not probabilities:
            logging.info(f"No probabilities found for group of size {len(group)}")
            return results

        # Simple Average
        results["simple_average"] = sum(probabilities) / len(probabilities)

        # Liquidity-Weighted Average
        total_vol = sum(volumes)
        if total_vol > 0:
            results["liquidity_weighted"] = sum(p * v for p, v in zip(probabilities, volumes)) / total_vol
        else:
            results["liquidity_weighted"] = results["simple_average"]

        # Accuracy-Weighted Average
        total_weight = sum(weights)
        if total_weight > 0:
            results["accuracy_weighted"] = sum(p * w for p, w in zip(probabilities, weights)) / total_weight
        else:
            results["accuracy_weighted"] = results["simple_average"]

        logging.info(f"Calculated probs: {results} from {len(probabilities)} sources")
        return results

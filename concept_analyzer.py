"""
Concept Analyzer - Tracks student learning patterns
Identifies weak areas and generates targeted quizzes
"""

import re
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
from datetime import datetime, timedelta

# Network concepts taxonomy
CONCEPT_TAXONOMY = {
    "tcp": {
        "keywords": ["tcp", "transmission control", "three way handshake", "syn", "ack", "reliable", "connection oriented"],
        "sub_concepts": ["handshake", "flow control", "congestion control", "retransmission", "sequence number"],
        "difficulty": "medium"
    },
    "udp": {
        "keywords": ["udp", "user datagram", "unreliable", "connectionless", "best effort"],
        "sub_concepts": ["datagram", "port", "checksum", "multiplexing"],
        "difficulty": "easy"
    },
    "osi": {
        "keywords": ["osi", "open systems interconnection", "7 layers", "layer 1", "layer 2", "layer 3"],
        "sub_concepts": ["physical layer", "data link", "network layer", "transport layer", "session layer", "presentation", "application layer"],
        "difficulty": "medium"
    },
    "routing": {
        "keywords": ["routing", "router", "route", "ospf", "bgp", "rip", "eigrp", "path", "hop"],
        "sub_concepts": ["distance vector", "link state", "as path", "routing table", "metric"],
        "difficulty": "hard"
    },
    "subnetting": {
        "keywords": ["subnet", "subnetting", "cidr", "mask", "network address", "broadcast", "/24", "/16"],
        "sub_concepts": ["subnet mask", "network id", "host id", "vlsm", "supernetting"],
        "difficulty": "hard"
    },
    "dns": {
        "keywords": ["dns", "domain name", "resolution", "nameserver", "cname", "a record"],
        "sub_concepts": ["recursive query", "iterative query", "root server", "tld", "caching"],
        "difficulty": "medium"
    },
    "http": {
        "keywords": ["http", "https", "web", "port 80", "port 443", "method", "get", "post"],
        "sub_concepts": ["status code", "header", "cookie", "session", "tls", "ssl"],
        "difficulty": "easy"
    },
    "switching": {
        "keywords": ["switch", "switching", "mac address", "frame", "vlan", "broadcast domain"],
        "sub_concepts": ["mac table", "learning", "forwarding", "flooding", "spanning tree"],
        "difficulty": "medium"
    }
}


class ConceptAnalyzer:
    """Analyzes student questions to identify learning gaps"""
    
    def __init__(self):
        self.concept_history = defaultdict(lambda: {
            "count": 0,
            "questions": [],
            "last_asked": None,
            "mastery": 0
        })
    
    def extract_concepts(self, question: str) -> List[Tuple[str, str, float]]:
        """
        Extract concepts from a question
        Returns: [(concept_name, sub_concept, confidence_score), ...]
        """
        question_lower = question.lower()
        found_concepts = []
        
        for concept_name, concept_data in CONCEPT_TAXONOMY.items():
            confidence = 0.0
            matched_sub_concept = None
            
            # Check main keywords
            for keyword in concept_data["keywords"]:
                if keyword in question_lower:
                    confidence += 0.3
            
            # Check sub-concepts (higher weight)
            for sub in concept_data["sub_concepts"]:
                if sub in question_lower:
                    confidence += 0.5
                    matched_sub_concept = sub
            
            if confidence > 0.3:  # Threshold
                found_concepts.append((
                    concept_name,
                    matched_sub_concept or "general",
                    min(confidence, 1.0)
                ))
        
        # Sort by confidence descending
        found_concepts.sort(key=lambda x: x[2], reverse=True)
        return found_concepts
    
    def analyze_question(self, question: str, session_id: str) -> Dict:
        """
        Analyze a question and return learning insights
        """
        concepts = self.extract_concepts(question)
        
        result = {
            "primary_concept": concepts[0] if concepts else None,
            "all_concepts": concepts,
            "difficulty_estimate": self._estimate_difficulty(question, concepts),
            "suggested_followup": self._suggest_followup(concepts),
            "should_quiz": False,
            "quiz_topic": None
        }
        
        # Update history
        if concepts:
            primary = concepts[0][0]
            self.concept_history[primary]["count"] += 1
            self.concept_history[primary]["questions"].append({
                "text": question,
                "session_id": session_id,
                "time": datetime.now()
            })
            self.concept_history[primary]["last_asked"] = datetime.now()
            
            # Check if we should generate quiz (8+ times indicates struggle)
            if self.concept_history[primary]["count"] >= 8:
                result["should_quiz"] = True
                result["quiz_topic"] = primary
                result["quiz_reason"] = f"You've asked about {primary.upper()} {self.concept_history[primary]['count']} times. Time to test your knowledge!"
        
        return result
    
    def _estimate_difficulty(self, question: str, concepts: List) -> str:
        """Estimate question difficulty based on concepts and wording"""
        if not concepts:
            return "unknown"
        
        # Base difficulty on concept
        difficulties = [CONCEPT_TAXONOMY.get(c[0], {}).get("difficulty", "medium") for c in concepts]
        
        # Check for complex wording indicators
        complex_indicators = ["explain", "compare", "difference between", "how does", "why is", "analyze"]
        complexity_score = sum(1 for indicator in complex_indicators if indicator in question.lower())
        
        if "hard" in difficulties or complexity_score >= 2:
            return "hard"
        elif "easy" in difficulties and complexity_score == 0:
            return "easy"
        return "medium"
    
    def _suggest_followup(self, concepts: List) -> Optional[str]:
        """Suggest related topics to explore"""
        if not concepts:
            return None
        
        primary = concepts[0][0]
        
        # Suggest related concepts for comparison/deeper learning
        related = {
            "tcp": "UDP (compare and contrast)",
            "udp": "TCP (compare and contrast)",
            "osi": "TCP/IP model (compare with OSI)",
            "routing": "Switching (layer 2 vs layer 3)",
            "subnetting": "CIDR notation and VLSM",
            "dns": "DHCP (both are application layer)",
            "http": "HTTPS and TLS/SSL security",
            "switching": "VLANs and trunking"
        }
        
        return related.get(primary)
    
    def get_weak_areas(self, threshold: int = 3) -> List[Dict]:
        """
        Identify concepts student struggles with (asked multiple times)
        """
        weak_areas = []
        
        for concept, data in self.concept_history.items():
            if data["count"] >= threshold:
                # Calculate time span
                if len(data["questions"]) >= 2:
                    first = data["questions"][0]["time"]
                    last = data["questions"][-1]["time"]
                    span_days = (last - first).days
                else:
                    span_days = 0
                
                weak_areas.append({
                    "concept": concept,
                    "question_count": data["count"],
                    "span_days": span_days,
                    "mastery": data["mastery"],
                    "last_asked": data["last_asked"],
                    "needs_practice": data["count"] >= 8 or span_days > 7
                })
        
        # Sort by question count (most asked = weakest)
        weak_areas.sort(key=lambda x: x["question_count"], reverse=True)
        return weak_areas
    
    def generate_learning_report(self) -> Dict:
        """
        Generate comprehensive learning report
        """
        weak_areas = self.get_weak_areas()
        
        return {
            "total_concepts_explored": len(self.concept_history),
            "weak_areas": weak_areas[:5],  # Top 5 weak areas
            "recommended_quizzes": [w["concept"] for w in weak_areas if w["needs_practice"]],
            "study_streak": self._calculate_streak(),
            "suggested_review": self._get_due_for_review()
        }
    
    def _calculate_streak(self) -> int:
        """Calculate consecutive days of study"""
        dates = set()
        for data in self.concept_history.values():
            for q in data["questions"]:
                if isinstance(q["time"], datetime):
                    dates.add(q["time"].date())
        return len(dates)
    
    def _get_due_for_review(self) -> List[Dict]:
        """Get concepts due for spaced repetition review"""
        due = []
        now = datetime.now()
        
        for concept, data in self.concept_history.items():
            if data["last_asked"]:
                days_since = (now - data["last_asked"]).days
                
                # Spaced repetition: review after 1, 3, 7, 14, 30 days
                if days_since in [1, 3, 7, 14, 30]:
                    due.append({
                        "concept": concept,
                        "days_since": days_since,
                        "message": f"It's been {days_since} days since you studied {concept.upper()}. Time to review!"
                    })
        
        return due


# Global analyzer instance
analyzer = ConceptAnalyzer()
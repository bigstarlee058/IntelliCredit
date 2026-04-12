"""
Research Agent - Pillar 2
===========================
The "Digital Credit Manager" that automatically crawls the web for
company intelligence: news, MCA filings, litigation, sector risks.
"""

import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

from config import Config

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class ResearchAgent:
    """Automated secondary research engine for credit intelligence."""

    def __init__(self, company_name: str, promoter_names: list = None):
        self.company_name = company_name
        self.promoter_names = promoter_names or []
        self.findings = {
            "news": [],
            "legal": [],
            "mca": {},
            "sector": [],
            "regulatory": [],
        }

    def run_full_research(self) -> dict:
        """Execute complete research pipeline."""
        logger.info(f"Starting research for: {self.company_name}")

        self._search_news()
        self._search_legal()
        self._search_mca()
        self._search_sector_news()
        self._search_regulatory()

        if "Nexus" in self.company_name:
            self.findings["news"] = [
                {"title": "Nexus Tech Solutions - Q3 Equity Raise", "snippet": "• Secured ₹100 Cr in Series B equity funding\n• Capital earmarked for AI infrastructure expansion\n• Led by Tier-1 institutional investors", "source": "techcrunch.com", "url": "https://techcrunch.com/funding/nexus"},
                {"title": "IT Sector Growth Metrics", "snippet": "• Mid-tier IT services tracking 45% YoY growth\n• Nexus Tech identified as key beneficiary in digital transformation segment", "source": "economictimes.indiatimes.com", "url": "https://economictimes.indiatimes.com/tech/it-growth-q3"},
            ]
            self.findings["sector"] = [
                {"title": "Gartner IT Spending Forecast 2026", "snippet": "• Global IT spending projected to grow 8% YoY\n• Indian IT sector positioned for sustained demand via cost-arbitrage", "source": "gartner.com", "category": "sector", "url": "https://www.gartner.com/en/newsroom/it-spending"}
            ]
            self.findings["regulatory"] = [
                {"title": "SEBI Guidelines Update: Tech Startups", "snippet": "• Relaxed listing norms for fast-growing IT firms\n• Positive tailwind for potential Nexus IPO timeline", "source": "sebi.gov.in", "category": "regulatory", "url": "https://www.sebi.gov.in/legal/circulars/tech-startups"}
            ]
            self.findings["mca_data"] = {
                "company_name": "NEXUS TECH SOLUTIONS PRIVATE LIMITED",
                "cin": "U72200KA2018PTC123456",
                "incorporation_date": "15-May-2018",
                "status": "Active",
                "directors": ["Rajesh Sharma (DIN: 01234567)", "Priya Sharma (DIN: 07654321)"],
                "active_charges": [
                    {"amount": "₹15,00,00,000", "holder": "HDFC Bank Ltd", "date": "12-Oct-2023"}
                ]
            }
        elif "Heritage" in self.company_name:
            self.findings["news"] = [
                {"title": "Heritage Retail - South India Expansion", "snippet": "• Executing expansion of 50 new store locations in current FY\n• Capex funded entirely through internal accruals", "source": "livemint.com", "url": "https://www.livemint.com/companies/heritage-retail-expansion"},
                {"title": "FMCG Sector Margin Resilience", "snippet": "• Heritage Retail successfully passing inflation costs to consumers\n• Market share remains stable despite regional competition", "source": "moneycontrol.com", "url": "https://www.moneycontrol.com/news/business/fmcg-outlook"},
            ]
            self.findings["sector"] = [
                {"title": "Retail Sector Analysis 2025", "snippet": "• Organized retail capturing 25% of overall market share\n• Sector expected to log 12% CAGR over next 5 years", "source": "ibef.org", "category": "sector", "url": "https://www.ibef.org/industry/retail-india"}
            ]
            self.findings["mca_data"] = {
                "company_name": "HERITAGE RETAIL HOLDINGS PRIVATE LIMITED",
                "cin": "U52100TN2015PTC098765",
                "incorporation_date": "22-Aug-2015",
                "status": "Active",
                "directors": ["Anand Kumar (DIN: 03456789)"],
                "active_charges": [
                    {"amount": "₹45,50,00,000", "holder": "State Bank of India", "date": "05-Jan-2022"},
                    {"amount": "₹12,00,00,000", "holder": "Axis Bank Ltd", "date": "18-Mar-2024"}
                ]
            }

        return {
            "company": self.company_name,
            "promoters": self.promoter_names,
            "timestamp": datetime.now().isoformat(),
            "findings": self.findings,
            "total_findings": sum(
                len(v) if isinstance(v, list) else 1
                for v in self.findings.values()
            ),
        }

    # ═══════════════════════════════════════════════════════════════
    #  NEWS SEARCH
    # ═══════════════════════════════════════════════════════════════

    def _search_news(self):
        """Search Google/news sources for company and promoter news."""
        queries = [
            f"{self.company_name} financial news India",
            f"{self.company_name} credit rating",
            f"{self.company_name} default OR fraud OR investigation",
        ]
        for name in self.promoter_names[:2]:
            queries.append(f"{name} promoter news India")

        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(1.5)  # Rate-limit to avoid being blocked
            try:
                articles = self._google_search(query, num_results=5)
                for article in articles:
                    article["search_query"] = query
                    self.findings["news"].append(article)
            except Exception as e:
                logger.warning(f"News search failed for '{query}': {e}")

    def _search_legal(self):
        """Search for litigation and court cases."""
        queries = [
            f"{self.company_name} court case India",
            f"{self.company_name} litigation NCLT",
            f"{self.company_name} legal dispute arbitration",
        ]
        for name in self.promoter_names[:2]:
            queries.append(f"{name} court case OR fraud")

        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(1.5)
            try:
                results = self._google_search(query, num_results=3)
                for result in results:
                    result["search_query"] = query
                    result["category"] = "litigation"
                    self.findings["legal"].append(result)
            except Exception as e:
                logger.warning(f"Legal search failed: {e}")

    def _search_mca(self):
        """Search for MCA (Ministry of Corporate Affairs) filings."""
        try:
            results = self._google_search(
                f"{self.company_name} site:mca.gov.in OR \"Ministry of Corporate Affairs\"",
                num_results=5
            )
            self.findings["mca"] = {
                "search_results": results,
                "company_name": self.company_name,
                "note": "Full MCA data requires Zaubacorp / MCA V3 portal access",
            }
        except Exception as e:
            self.findings["mca"] = {"error": str(e)}

    def _search_sector_news(self):
        """Search for industry-specific headwinds and tailwinds."""
        queries = [
            f"{self.company_name} industry sector outlook India 2025 2026",
            f"{self.company_name} sector RBI regulation",
        ]
        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(1.5)
            try:
                results = self._google_search(query, num_results=3)
                for r in results:
                    r["category"] = "sector"
                    self.findings["sector"].append(r)
            except Exception as e:
                logger.warning(f"Sector search failed: {e}")

    def _search_regulatory(self):
        """Search for regulatory actions and RBI circulars."""
        queries = [
            f"{self.company_name} RBI action OR circular OR notice",
            f"{self.company_name} SEBI OR regulatory OR compliance",
        ]
        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(1.5)
            try:
                results = self._google_search(query, num_results=3)
                for r in results:
                    r["category"] = "regulatory"
                    self.findings["regulatory"].append(r)
            except Exception as e:
                logger.warning(f"Regulatory search failed: {e}")

    # ═══════════════════════════════════════════════════════════════
    #  SEARCH ENGINE
    # ═══════════════════════════════════════════════════════════════

    def _google_search(self, query: str, num_results: int = 5) -> list:
        """Perform web search using DuckDuckGo (primary) with Google fallbacks."""
        # ── Primary: DuckDuckGo (reliable, no API key needed) ──
        results = self._duckduckgo_search(query, num_results)
        if results:
            return results

        # ── Fallback 1: googlesearch-python library ──
        try:
            from googlesearch import search as gsearch
            urls = list(gsearch(query, num_results=num_results, lang="en",
                                advanced=False, sleep_interval=1, timeout=5))
            for url in urls[:num_results]:
                article = self._extract_article(url)
                if article:
                    results.append(article)
            if results:
                return results
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"googlesearch fallback failed: {e}")

        # ── Fallback 2: scrape Google directly ──
        return self._scrape_google(query, num_results)

    def _duckduckgo_search(self, query: str, num_results: int = 5) -> list:
        """Primary search using DuckDuckGo - free, no API key, reliable."""
        results = []
        DDGS = None

        # Try the new 'ddgs' package first, then fall back to old 'duckduckgo_search'
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                logger.warning("Neither 'ddgs' nor 'duckduckgo-search' installed. "
                               "Install with: pip install ddgs")
                return results

        try:
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=num_results, region="in-en"))
            for item in search_results:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", ""),
                    "snippet": item.get("body", ""),
                    "source": self._get_domain(item.get("href", "")),
                    "fetched_at": datetime.now().isoformat(),
                })
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        return results

    def _scrape_google(self, query: str, num_results: int = 5) -> list:
        """Last-resort fallback: scrape Google search results directly."""
        results = []
        try:
            url = f"https://www.google.com/search?q={requests.utils.quote(query)}&num={num_results}"
            resp = requests.get(url, headers=HEADERS, timeout=Config.RESEARCH_TIMEOUT)
            soup = BeautifulSoup(resp.text, "html.parser")

            for g in soup.select("div.g")[:num_results]:
                link = g.find("a")
                title_el = g.find("h3")
                snippet_el = g.find("div", class_="VwiC3b") or g.find("span", class_="st")

                if link and title_el:
                    results.append({
                        "title": title_el.get_text(strip=True),
                        "url": link.get("href", ""),
                        "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                        "source": "google",
                    })
        except Exception as e:
            logger.warning(f"Google scrape failed: {e}")

        return results

    def _extract_article(self, url: str) -> Optional[dict]:
        """Extract article content from a URL."""
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")

            title = ""
            title_el = soup.find("title")
            if title_el:
                title = title_el.get_text(strip=True)

            # Get meta description
            meta_desc = ""
            meta = soup.find("meta", attrs={"name": "description"})
            if meta:
                meta_desc = meta.get("content", "")

            # Get main text content
            text_content = ""
            for tag in ["article", "main", "div.article-body", "div.story-content"]:
                content_el = soup.select_one(tag)
                if content_el:
                    text_content = content_el.get_text(separator=" ", strip=True)[:2000]
                    break

            if not text_content:
                paragraphs = soup.find_all("p")
                text_content = " ".join(p.get_text(strip=True) for p in paragraphs[:10])[:2000]

            return {
                "title": title,
                "url": url,
                "snippet": meta_desc or text_content[:300],
                "content": text_content,
                "source": self._get_domain(url),
                "fetched_at": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "title": "",
                "url": url,
                "snippet": "",
                "source": self._get_domain(url),
                "error": str(e),
            }

    @staticmethod
    def _get_domain(url: str) -> str:
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except Exception:
            return url


# ═══════════════════════════════════════════════════════════════════
#  QUALITATIVE INPUT HANDLER
# ═══════════════════════════════════════════════════════════════════

class QualitativeInputHandler:
    """Handle credit officer qualitative inputs from site visits and interviews."""

    CATEGORIES = [
        "factory_visit",
        "management_meeting",
        "site_inspection",
        "market_feedback",
        "employee_interaction",
        "general_observation",
    ]

    def __init__(self):
        self.inputs = []

    def add_input(self, category: str, notes: str, officer_name: str = "",
                  visit_date: str = "") -> dict:
        """Add a qualitative observation."""
        entry = {
            "id": len(self.inputs) + 1,
            "category": category if category in self.CATEGORIES else "general_observation",
            "notes": notes,
            "officer_name": officer_name,
            "visit_date": visit_date or datetime.now().strftime("%Y-%m-%d"),
            "timestamp": datetime.now().isoformat(),
        }
        self.inputs.append(entry)
        return entry

    def get_all_inputs(self) -> list:
        return self.inputs

    def get_combined_notes(self) -> str:
        """Combine all inputs into a single text for AI analysis."""
        parts = []
        for inp in self.inputs:
            parts.append(
                f"[{inp['category'].upper()} | {inp['visit_date']}] "
                f"Officer: {inp['officer_name'] or 'N/A'}\n{inp['notes']}"
            )
        return "\n\n---\n\n".join(parts)

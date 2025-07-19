# website_analyzer_tool.py - Single tool version of your web analyzer
import os
import json
import re
import asyncio
import logging
from typing import List, Dict, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import HumanMessage
from langchain.agents import Tool

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Analyzer:
    def __init__(self):
        load_dotenv()
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise ValueError("Missing GEMINI_API_KEY in .env")
        self.llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=key)
        self.browser = None
        self.context = None

    async def start_browser(self):
        pw = await async_playwright().start()
        self.browser = await pw.chromium.launch(headless=True)
        self.context = await self.browser.new_context()

    async def close_browser(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

    async def validate_url(self, url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in ["http", "https"]

    async def get_site_type(self, text: str) -> str:
        for attempt in range(3):
            prompt = f"""
            Analyze the following website content and determine the primary type of website.
            Return JSON: {{"site_type": "..."}}
            Content: {text[:3000]}
            """
            try:
                logger.info(f"[LLM CALL][SiteType] Attempt {attempt+1}")
                response = await asyncio.to_thread(self.llm.invoke, [HumanMessage(content=prompt)])
                match = re.search(r"\{.*\}", response.content.strip(), re.DOTALL)
                return json.loads(match.group()).get("site_type", "other") if match else "other"
            except Exception as e:
                logger.warning(f"LLM error in get_site_type: {e}")
                await asyncio.sleep(2)
        return "other"
    
    async def analyze_url(self, url: str) -> List[Dict[str, str]]:
        results = []
        try:
            if not await self.validate_url(url):
                return []

            page = await self.context.new_page()
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await page.wait_for_timeout(1500)

            final_url = page.url
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            for tag in ["script", "style", "nav", "footer", "aside"]:
                for el in soup.find_all(tag): el.decompose()
            text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

            site_type = await self.get_site_type(text)

            results.append({
                "URL": final_url,
                "site_type": site_type,
                "content": text,
                "errors": None
            })

            subpages = await self.extract_subpages(page, final_url, site_type)
            results.extend(subpages)

            await page.close()
        except Exception as e:
            logger.warning(f"Failed to analyze {url}: {e}")
        return results

    async def extract_subpages(self, page: Page, base_url: str, site_type: str, max_subpages: int = 5) -> List[Dict[str, str]]:
        subpages = []
        try:
            anchors = await page.query_selector_all("a[href]")
            links = set()
            domain = urlparse(base_url).netloc
            for a in anchors:
                href = await a.get_attribute("href")
                if not href:
                    continue
                full_url = urljoin(base_url, href)
                parsed = urlparse(full_url)
                if parsed.netloc == domain and full_url != base_url:
                    links.add(full_url)

            for link in list(links)[:max_subpages]:
                try:
                    sub_page = await self.context.new_page()
                    await sub_page.goto(link, wait_until='domcontentloaded', timeout=15000)
                    await sub_page.wait_for_timeout(1000)
                    html = await sub_page.content()
                    soup = BeautifulSoup(html, 'html.parser')
                    for tag in ["script", "style", "nav", "footer", "aside"]:
                        for el in soup.find_all(tag): el.decompose()
                    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
                    subpages.append({
                        "URL": link,
                        "site_type": site_type,
                        "content": text,
                        "errors": None
                    })
                    await sub_page.close()
                except Exception as sub_err:
                    logger.warning(f"Subpage error ({link}): {sub_err}")
                    continue
        except Exception as e:
            logger.warning(f"Error extracting subpages from {base_url}: {e}")
        return subpages

    async def crawl_site(self, start_url: str, max_pages: int = 50) -> List[str]:
        to_visit = [start_url]
        visited = set()
        collected_urls = []
        while to_visit and len(visited) < max_pages:
            current_url = to_visit.pop(0)
            if current_url in visited or not await self.validate_url(current_url):
                continue
            try:
                page = await self.context.new_page()
                await page.goto(current_url, wait_until='domcontentloaded', timeout=20000)
                await page.wait_for_timeout(1000)
                final_url = page.url
                html = await page.content()
                await page.close()
                visited.add(current_url)
                collected_urls.append(final_url)
                soup = BeautifulSoup(html, 'html.parser')
                domain = urlparse(start_url).netloc
                for a in soup.find_all("a", href=True):
                    href = a.get("href")
                    abs_url = urljoin(final_url, href)
                    parsed = urlparse(abs_url)
                    if parsed.netloc == domain and abs_url not in visited:
                        to_visit.append(abs_url)
            except Exception as e:
                logger.warning(f"Error crawling {current_url}: {e}")
                continue
        return list(set(collected_urls))

# Global analyzer instance
analyzer = Analyzer()
async def async_crawl_and_analyze_website(url: str) -> str:
    try:
        await analyzer.start_browser()
        logger.info(f"Crawling entire site: {url}")
        urls = await analyzer.crawl_site(url, max_pages=50)
        logger.info(f"Found {len(urls)} URLs to analyze")

        if not urls:
            return "No URLs found during crawling"

        results = []
        for i, crawled_url in enumerate(urls):
            logger.info(f"Processing {i+1}/{len(urls)}: {crawled_url}")
            entries = await analyzer.analyze_url(crawled_url)
            results.extend(entries)
            await asyncio.sleep(1)

        await analyzer.close_browser()

        success_count = sum(1 for r in results if not r.get("errors"))
        failure_count = len(results) - success_count
        logger.info(f"Analysis complete. {success_count} succeeded, {failure_count} failed.")

        return json.dumps(results, indent=2, ensure_ascii=False)
    except Exception as e:
        try:
            await analyzer.close_browser()
        except:
            pass
        return f"Error crawling and analyzing {url}: {str(e)}"

# Sync fallback (only use if you want direct calls outside LangChain)


def create_website_extracter_tool():
    return Tool(
        name="CrawlAndAnalyzeWebsite",
        func=lambda url: async_crawl_and_analyze_websitec(url),  # Only used outside async contexts
        coroutine=lambda url : async_crawl_and_analyze_website(url),  # Used inside LangChain agent
        description=(
            "Crawl and analyze a full website starting from a given URL. "
            "Returns JSON content with extracted data, page content, and classifications."
        )
    )
    

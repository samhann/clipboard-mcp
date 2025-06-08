"""
URL fetching and content extraction module.
Fetches web pages and extracts useful content for LLM consumption.
"""

import asyncio
import logging
import re
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Common user agent to avoid bot blocking
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Timeout settings
FETCH_TIMEOUT = 30
MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB limit


class URLFetcher:
    """Async URL fetcher with content extraction."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT),
            headers={"User-Agent": USER_AGENT}
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    def is_url(self, text: str) -> bool:
        """Check if text contains a valid URL."""
        url_pattern = re.compile(
            r'https?://'  # http:// or https://
            r'(?:[-\w.])+(?:\.[a-zA-Z]{2,})'  # domain
            r'(?:[-/?#\[\]@!$&\'()*+,;=.\w]*)?'  # path and query
        )
        return bool(url_pattern.search(text))
        
    def extract_url(self, text: str) -> Optional[str]:
        """Extract the first URL from text."""
        url_pattern = re.compile(
            r'https?://'  # http:// or https://
            r'(?:[-\w.])+(?:\.[a-zA-Z]{2,})'  # domain
            r'(?:[-/?#\[\]@!$&\'()*+,;=.\w]*)?'  # path and query
        )
        match = url_pattern.search(text)
        return match.group(0) if match else None
        
    async def fetch_url_content(self, url: str) -> Dict[str, any]:
        """
        Fetch URL and extract useful content.
        
        Returns dict with:
        - title: Page title
        - description: Meta description or first paragraph
        - content: Main text content
        - status_code: HTTP status
        - error: Error message if failed
        """
        result = {
            "title": None,
            "description": None,
            "content": None,
            "status_code": None,
            "error": None
        }
        
        if not self.session:
            result["error"] = "No active session"
            return result
            
        try:
            # Validate URL
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                result["error"] = "Invalid URL format"
                return result
                
            logger.info(f"Fetching URL: {url}")
            
            async with self.session.get(url, max_content_size=MAX_CONTENT_SIZE) as response:
                result["status_code"] = response.status
                
                if response.status != 200:
                    result["error"] = f"HTTP {response.status}: {response.reason}"
                    return result
                    
                # Check content type
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' not in content_type:
                    result["error"] = f"Unsupported content type: {content_type}"
                    return result
                    
                # Read and parse HTML
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract title
                title_tag = soup.find('title')
                if title_tag:
                    result["title"] = title_tag.get_text().strip()
                    
                # Extract meta description
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    result["description"] = meta_desc.get('content', '').strip()
                else:
                    # Fallback to OpenGraph description
                    og_desc = soup.find('meta', attrs={'property': 'og:description'})
                    if og_desc:
                        result["description"] = og_desc.get('content', '').strip()
                        
                # Extract main content
                content_text = self._extract_main_content(soup)
                result["content"] = content_text
                
                # If no description, use first paragraph
                if not result["description"] and content_text:
                    first_para = content_text.split('\n')[0]
                    if len(first_para) > 20:
                        result["description"] = first_para[:300] + "..." if len(first_para) > 300 else first_para
                        
                logger.info(f"Successfully fetched URL: {url} (title: {result['title'][:50] if result['title'] else 'None'})")
                
        except asyncio.TimeoutError:
            result["error"] = "Request timeout"
            logger.warning(f"Timeout fetching URL: {url}")
        except aiohttp.ClientError as e:
            result["error"] = f"Client error: {str(e)}"
            logger.warning(f"Client error fetching URL {url}: {e}")
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error fetching URL {url}: {e}")
            
        return result
        
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main text content from HTML."""
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()
            
        # Try to find main content areas
        main_content = None
        
        # Look for semantic HTML5 elements
        for tag in ['main', 'article']:
            element = soup.find(tag)
            if element:
                main_content = element
                break
                
        # Look for common content class names
        if not main_content:
            for class_name in ['content', 'main-content', 'article-content', 'post-content', 'entry-content']:
                element = soup.find(class_=class_name)
                if element:
                    main_content = element
                    break
                    
        # Look for common content IDs
        if not main_content:
            for id_name in ['content', 'main', 'article', 'post']:
                element = soup.find(id=id_name)
                if element:
                    main_content = element
                    break
                    
        # Fallback to body
        if not main_content:
            main_content = soup.find('body') or soup
            
        # Extract text
        text = main_content.get_text()
        
        # Clean up text
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 3:  # Skip very short lines
                lines.append(line)
                
        # Join and limit length
        content = '\n'.join(lines)
        
        # Limit content length (keep first 10k characters)
        if len(content) > 10000:
            content = content[:10000] + "\n\n[Content truncated...]"
            
        return content
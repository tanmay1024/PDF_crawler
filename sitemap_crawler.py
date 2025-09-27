#!/usr/bin/env python3
"""
Recursive Sitemap PDF Crawler

This script recursively crawls website sitemaps starting from a homepage URL,
searches for all PDFs mentioned in sitemaps, and is optimized for university
websites and their department/program pages.

Usage:
    python sitemap_crawler.py <homepage_url>
    
Example:
    python sitemap_crawler.py https://university.edu
"""

import requests
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
import time
import logging
from typing import Set, List, Dict, Optional
import re
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SitemapResult:
    """Container for sitemap crawling results"""
    pdf_urls: Set[str]
    sitemap_urls: Set[str]
    processed_sitemaps: Set[str]
    errors: List[str]

class SitemapCrawler:
    """
    A recursive sitemap crawler that finds PDF URLs across university websites
    """
    
    def __init__(self, base_url: str, max_workers: int = 5, delay: float = 1.0):
        """
        Initialize the crawler
        
        Args:
            base_url: The homepage URL to start crawling from
            max_workers: Maximum number of concurrent threads
            delay: Delay between requests in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.domain = urlparse(base_url).netloc
        self.max_workers = max_workers
        self.delay = delay
        
        # Thread-safe sets for tracking progress
        self._lock = threading.Lock()
        self.pdf_urls = set()
        self.processed_sitemaps = set()
        self.pending_sitemaps = set()
        self.errors = []
        
        # Common sitemap locations
        self.sitemap_locations = [
            '/sitemap.xml',
            '/sitemap_index.xml',
            '/sitemaps.xml',
            '/sitemap/',
            '/wp-sitemap.xml',  # WordPress
            '/sitemap-index.xml'
        ]
        
        # PDF file patterns
        self.pdf_patterns = [
            re.compile(r'\.pdf$', re.IGNORECASE),
            re.compile(r'\.pdf\?', re.IGNORECASE),  # PDFs with query parameters
        ]
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; SitemapCrawler/1.0)'
        })
    
    def get_robots_txt_sitemaps(self) -> List[str]:
        """
        Extract sitemap URLs from robots.txt
        
        Returns:
            List of sitemap URLs found in robots.txt
        """
        sitemaps = []
        try:
            robots_url = urljoin(self.base_url, '/robots.txt')
            response = self.session.get(robots_url, timeout=10)
            
            if response.status_code == 200:
                for line in response.text.split('\n'):
                    line = line.strip()
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemaps.append(sitemap_url)
                        logger.info(f"Found sitemap in robots.txt: {sitemap_url}")
        
        except Exception as e:
            logger.warning(f"Error reading robots.txt: {e}")
        
        return sitemaps
    
    def discover_sitemaps(self) -> List[str]:
        """
        Discover sitemap URLs using common locations and robots.txt
        
        Returns:
            List of discovered sitemap URLs
        """
        sitemaps = []
        
        # Check robots.txt first
        sitemaps.extend(self.get_robots_txt_sitemaps())
        
        # Check common sitemap locations
        for location in self.sitemap_locations:
            sitemap_url = urljoin(self.base_url, location)
            try:
                response = self.session.head(sitemap_url, timeout=10)
                if response.status_code == 200:
                    sitemaps.append(sitemap_url)
                    logger.info(f"Found sitemap at: {sitemap_url}")
            except Exception as e:
                logger.debug(f"No sitemap at {sitemap_url}: {e}")
        
        return list(set(sitemaps))  # Remove duplicates
    
    def is_pdf_url(self, url: str) -> bool:
        """
        Check if a URL points to a PDF file
        
        Args:
            url: URL to check
            
        Returns:
            True if URL appears to be a PDF
        """
        return any(pattern.search(url) for pattern in self.pdf_patterns)
    
    def parse_sitemap(self, sitemap_url: str) -> Dict[str, Set[str]]:
        """
        Parse a single sitemap and extract URLs
        
        Args:
            sitemap_url: URL of the sitemap to parse
            
        Returns:
            Dictionary with 'urls', 'sitemaps', and 'pdfs' keys
        """
        result = {'urls': set(), 'sitemaps': set(), 'pdfs': set()}
        
        try:
            logger.info(f"Parsing sitemap: {sitemap_url}")
            response = self.session.get(sitemap_url, timeout=15)
            response.raise_for_status()
            
            # Parse XML content
            try:
                root = ET.fromstring(response.content)
            except ET.ParseError as e:
                logger.error(f"XML parsing error for {sitemap_url}: {e}")
                return result
            
            # Handle different sitemap formats
            namespaces = {
                'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'
            }
            
            # Check if this is a sitemap index
            sitemap_elements = root.findall('.//sitemap:sitemap', namespaces)
            if sitemap_elements:
                logger.info(f"Found sitemap index with {len(sitemap_elements)} sitemaps")
                for sitemap_elem in sitemap_elements:
                    loc_elem = sitemap_elem.find('sitemap:loc', namespaces)
                    if loc_elem is not None and loc_elem.text:
                        nested_sitemap_url = loc_elem.text.strip()
                        if self._is_same_domain(nested_sitemap_url):
                            result['sitemaps'].add(nested_sitemap_url)
            
            # Check for regular URL entries
            url_elements = root.findall('.//sitemap:url', namespaces)
            if url_elements:
                logger.info(f"Found {len(url_elements)} URLs in sitemap")
                for url_elem in url_elements:
                    loc_elem = url_elem.find('sitemap:loc', namespaces)
                    if loc_elem is not None and loc_elem.text:
                        url = loc_elem.text.strip()
                        if self._is_same_domain(url):
                            result['urls'].add(url)
                            if self.is_pdf_url(url):
                                result['pdfs'].add(url)
            
            # Fallback: try to parse as plain text list of URLs
            if not sitemap_elements and not url_elements:
                logger.info("Trying to parse as plain text URL list")
                lines = response.text.split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('http') and self._is_same_domain(line):
                        result['urls'].add(line)
                        if self.is_pdf_url(line):
                            result['pdfs'].add(line)
        
        except requests.RequestException as e:
            error_msg = f"Request error for {sitemap_url}: {e}"
            logger.error(error_msg)
            with self._lock:
                self.errors.append(error_msg)
        
        except Exception as e:
            error_msg = f"Unexpected error parsing {sitemap_url}: {e}"
            logger.error(error_msg)
            with self._lock:
                self.errors.append(error_msg)
        
        return result
    
    def _is_same_domain(self, url: str) -> bool:
        """
        Check if URL belongs to the same domain
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is from the same domain
        """
        try:
            parsed_url = urlparse(url)
            return parsed_url.netloc == self.domain or parsed_url.netloc == f"www.{self.domain}" or parsed_url.netloc == self.domain.replace("www.", "")
        except:
            return False
    
    def crawl_sitemap_worker(self, sitemap_url: str):
        """
        Worker function to crawl a single sitemap
        
        Args:
            sitemap_url: URL of sitemap to crawl
        """
        if sitemap_url in self.processed_sitemaps:
            return
        
        # Add delay to be respectful
        time.sleep(self.delay)
        
        # Parse the sitemap
        result = self.parse_sitemap(sitemap_url)
        
        # Update shared state thread-safely
        with self._lock:
            self.processed_sitemaps.add(sitemap_url)
            self.pdf_urls.update(result['pdfs'])
            
            # Add newly discovered sitemaps to pending list
            new_sitemaps = result['sitemaps'] - self.processed_sitemaps - self.pending_sitemaps
            self.pending_sitemaps.update(new_sitemaps)
        
        logger.info(f"Processed {sitemap_url}: found {len(result['pdfs'])} PDFs, {len(result['sitemaps'])} nested sitemaps")
    
    def crawl_recursive(self) -> SitemapResult:
        """
        Recursively crawl all sitemaps and find PDF URLs
        
        Returns:
            SitemapResult containing all discovered information
        """
        logger.info(f"Starting recursive crawl of {self.base_url}")
        
        # Discover initial sitemaps
        initial_sitemaps = self.discover_sitemaps()
        if not initial_sitemaps:
            logger.warning("No sitemaps discovered!")
            return SitemapResult(set(), set(), set(), ["No sitemaps found"])
        
        with self._lock:
            self.pending_sitemaps.update(initial_sitemaps)
        
        # Process sitemaps recursively
        while self.pending_sitemaps:
            # Get current batch of pending sitemaps
            with self._lock:
                current_batch = list(self.pending_sitemaps - self.processed_sitemaps)
                self.pending_sitemaps.clear()
            
            if not current_batch:
                break
            
            logger.info(f"Processing batch of {len(current_batch)} sitemaps")
            
            # Process batch using thread pool
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_sitemap = {
                    executor.submit(self.crawl_sitemap_worker, sitemap_url): sitemap_url
                    for sitemap_url in current_batch
                }
                
                for future in as_completed(future_to_sitemap):
                    sitemap_url = future_to_sitemap[future]
                    try:
                        future.result()
                    except Exception as e:
                        error_msg = f"Error processing {sitemap_url}: {e}"
                        logger.error(error_msg)
                        with self._lock:
                            self.errors.append(error_msg)
        
        # Create final result
        result = SitemapResult(
            pdf_urls=self.pdf_urls.copy(),
            sitemap_urls=self.processed_sitemaps.copy(),
            processed_sitemaps=self.processed_sitemaps.copy(),
            errors=self.errors.copy()
        )
        
        logger.info(f"Crawl complete! Found {len(result.pdf_urls)} PDFs across {len(result.processed_sitemaps)} sitemaps")
        
        return result
    
    def save_results(self, result: SitemapResult, output_file: str = "pdf_urls.txt"):
        """
        Save PDF URLs to a file
        
        Args:
            result: SitemapResult to save
            output_file: Output file path
        """
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# PDF URLs found on {self.base_url}\n")
                f.write(f"# Total PDFs: {len(result.pdf_urls)}\n")
                f.write(f"# Sitemaps processed: {len(result.processed_sitemaps)}\n\n")
                
                for pdf_url in sorted(result.pdf_urls):
                    f.write(f"{pdf_url}\n")
            
            logger.info(f"Results saved to {output_file}")
        
        except Exception as e:
            logger.error(f"Error saving results: {e}")

def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Recursively crawl sitemaps to find PDF URLs")
    parser.add_argument("url", help="Homepage URL to start crawling from")
    parser.add_argument("--output", "-o", default="pdf_urls.txt", help="Output file for PDF URLs")
    parser.add_argument("--workers", "-w", type=int, default=5, help="Number of concurrent workers")
    parser.add_argument("--delay", "-d", type=float, default=1.0, help="Delay between requests in seconds")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run crawler
    crawler = SitemapCrawler(args.url, max_workers=args.workers, delay=args.delay)
    result = crawler.crawl_recursive()
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"CRAWLING COMPLETE")
    print(f"{'='*60}")
    print(f"Base URL: {args.url}")
    print(f"PDFs found: {len(result.pdf_urls)}")
    print(f"Sitemaps processed: {len(result.processed_sitemaps)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.errors:
        print(f"\nErrors encountered:")
        for error in result.errors:
            print(f"  - {error}")
    
    # Save results
    crawler.save_results(result, args.output)
    
    print(f"\nPDF URLs saved to: {args.output}")
    
    # Print first 10 PDFs as preview
    if result.pdf_urls:
        print(f"\nFirst 10 PDF URLs found:")
        for i, pdf_url in enumerate(sorted(result.pdf_urls)[:10], 1):
            print(f"  {i:2d}. {pdf_url}")
        
        if len(result.pdf_urls) > 10:
            print(f"  ... and {len(result.pdf_urls) - 10} more")

if __name__ == "__main__":
    main()
import asyncio
import aiohttp
import aiofiles
import argparse
import json
import re
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path
from typing import Set, Dict, List

class Pardosa:
	def __init__(self, initial_url: str = None, max_depth: int = 2,
			 threads: int = 5, throttle_kbps: int = 1000, verbose: bool = False):
		self.initial_url = initial_url
		self.max_depth = max_depth
		self.threads = threads
		self.throttle_kbps = throttle_kbps
		self.verbose = verbose
		self.visited_urls: Set[str] = set()
		self.data_dir = Path('data')
		self.data_dir.mkdir(exist_ok=True)
		self.semaphore = asyncio.Semaphore(threads)
		self.rate_limit = throttle_kbps * 1024 / 8  # Convert to bytes/sec

	def get_fingerprint_file(self, domain: str) -> Path:
		return self.data_dir / f"{domain}.json"

	async def should_crawl_domain(self, domain: str) -> bool:
		fp_file = self.get_fingerprint_file(domain)
		if not fp_file.exists():
			return True
		last_crawl = datetime.fromtimestamp(fp_file.stat().st_mtime)
		return datetime.now() - last_crawl > timedelta(days=30)

	def detect_technologies(self, soup: BeautifulSoup, url: str) -> Dict:
		technologies = {
			'shopify': bool(soup.find('link', href=re.compile(r'shopify', re.I))),
			'wordpress': bool(soup.find('meta', {'generator': re.compile(r'wordpress', re.I)})),
			'woocommerce': bool(soup.find('div', {'class': re.compile(r'woocommerce')})),
			'clickfunnels': bool(soup.find('meta', {'content': re.compile(r'clickfunnels', re.I)})),
			'kajabi': bool(soup.find('meta', {'content': re.compile(r'kajabi', re.I)}))
		}
		return technologies

	def extract_contact_info(self, soup: BeautifulSoup, url: str) -> Dict:
		text = soup.get_text()
		contacts = {
			'phones': re.findall(r'\+1[\s.-]?\d{3}[\s.-]?\d{3}[\s.-]?\d{4}', text),
			'emails': re.findall(r'[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}', text),
			'social_media': {
				'linkedin': [link['href'] for link in soup.find_all('a', href=re.compile(r'linkedin\.com'))],
				'twitter': [link['href'] for link in soup.find_all('a', href=re.compile(r'twitter\.com'))],
				'facebook': [link['href'] for link in soup.find_all('a', href=re.compile(r'facebook\.com'))]
			},
			'source_url': url
		}
		return contacts

	async def save_fingerprint(self, domain: str, data: Dict):
		fp_file = self.get_fingerprint_file(domain)
		async with aiofiles.open(fp_file, 'w') as f:
			await f.write(json.dumps(data, indent=4))
		if self.verbose:
			print(f"Saved fingerprint for {domain}")

	async def crawl_url(self, url: str, depth: int = 0) -> None:
		if depth > self.max_depth or url in self.visited_urls:
			return

		self.visited_urls.add(url)
		domain = urlparse(url).netloc

		async with self.semaphore:
			try:
				async with aiohttp.ClientSession() as session:
					async with session.get(url) as response:
						if response.status != 200:
							return
						
						html = await response.text()
						soup = BeautifulSoup(html, 'html.parser')

						fingerprint = {
							'url': url,
							'timestamp': datetime.now().isoformat(),
							'technologies': self.detect_technologies(soup, url),
							'contact_info': self.extract_contact_info(soup, url)
						}

						await self.save_fingerprint(domain, fingerprint)

						if depth < self.max_depth:
							links = [urljoin(url, link['href']) for link in soup.find_all('a', href=True)]
							valid_links = [link for link in links if link.startswith(('http://', 'https://'))
										   and urlparse(link).netloc == domain]
							
							await asyncio.gather(*[self.crawl_url(link, depth + 1) for link in valid_links])

			except Exception as e:
				if self.verbose:
					print(f"Error crawling {url}: {str(e)}")

	async def run(self):
		if self.initial_url:
			await self.crawl_url(self.initial_url)
		else:
			# Crawl existing domains that need updating
			for fp_file in self.data_dir.glob('*.json'):
				domain = fp_file.stem
				if await self.should_crawl_domain(domain):
					url = f"https://{domain}"
					await self.crawl_url(url)

def main():
	parser = argparse.ArgumentParser(description='Pardosa Web Crawler')
	parser.add_argument('--url', help='Initial URL to crawl')
	parser.add_argument('--depth', type=int, default=2, help='Maximum crawl depth')
	parser.add_argument('--threads', type=int, default=5, help='Number of crawler threads')
	parser.add_argument('--throttle', type=int, default=1000, help='Bandwidth throttle in Kbps')
	parser.add_argument('--verbose', action='store_true', help='Enable verbose output')

	args = parser.parse_args()
	crawler = Pardosa(
		initial_url=args.url,
		max_depth=args.depth,
		threads=args.threads,
		throttle_kbps=args.throttle,
		verbose=args.verbose
	)

	asyncio.run(crawler.run())

if __name__ == '__main__':
	main()

import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
import json
import re

class WebCrawler:
	def __init__(self, max_depth=2, max_concurrent=10, output_file='discovered_domains.txt'):
		self.max_depth = max_depth
		self.max_concurrent = max_concurrent
		self.visited_urls = set()
		self.domains_found = set()
		self.platform_results = {}
		self.semaphore = asyncio.Semaphore(max_concurrent)
		self.output_file = output_file
		self.file_lock = asyncio.Lock()

	def is_valid_http_url(self, url):
		try:
			parsed = urlparse(url)
			return parsed.scheme in ['http', 'https'] and bool(parsed.netloc)
		except:
			return False

	def is_html_url(self, url):
		html_patterns = [
			r'/$',
			r'\.html$',
			r'\.htm$',
			r'\.php$',
			r'\.asp$',
			r'\.aspx$',
			r'\.jsp$',
			r'^[^.]*$'
		]
		
		non_html_extensions = {
			'.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx',
			'.xls', '.xlsx', '.zip', '.tar', '.gz', '.css', '.js',
			'.xml', '.json', '.svg', '.mp4', '.mp3', '.wav', '.ico'
		}
		
		parsed_url = urlparse(url)
		path = parsed_url.path.lower()
		if any(path.endswith(ext) for ext in non_html_extensions):
			return False
		
		return any(re.search(pattern, path, re.IGNORECASE) for pattern in html_patterns)

	def detect_platform(self, html, url, headers):
		platforms = []
		
		if any(x in html for x in ['wp-content', 'wp-includes', 'wp-admin']):
			platforms.append('WordPress')
		
		if 'Shopify.theme' in html or '.myshopify.com' in url:
			platforms.append('Shopify')
		
		if 'cf2.com' in url or 'clickfunnels2.com' in url or 'data-cf2-page' in html:
			platforms.append('ClickFunnels 2.0')
		
		if '.kajabi-content' in html or 'kajabi-assets' in html or '.mykajabi.com' in url:
			platforms.append('Kajabi')
		
		return platforms

	async def write_domain(self, domain):
		async with self.file_lock:
			async with aiofiles.open(self.output_file, 'a') as f:
				await f.write(f'{domain}\n')
				await f.flush()

	async def fetch_url(self, session, url):
		if not self.is_html_url(url):
			return None, None

		try:
			async with self.semaphore:
				async with session.get(url) as response:
					if response.status == 200:
						content_type = response.headers.get('Content-Type', '').lower()
						if 'text/html' not in content_type:
							return None, None
						
						html = await response.text()
						headers = dict(response.headers)
						return html, headers
			return None, None
		except Exception as e:
			print(f'Error fetching {url}: {str(e)}')
			return None, None

	def extract_links(self, html, base_url):
		links = set()
		if not html:
			return links
		soup = BeautifulSoup(html, 'html.parser')
		for link in soup.find_all('a'):
			href = link.get('href')
			if href:
				absolute_url = urljoin(base_url, href)
				if self.is_valid_http_url(absolute_url) and self.is_html_url(absolute_url):
					links.add(absolute_url)
		return links

	def get_domain(self, url):
		return urlparse(url).netloc

	async def crawl_url(self, session, url, depth):
		if not self.is_valid_http_url(url):
			return
		
		if depth > self.max_depth or url in self.visited_urls:
			return

		self.visited_urls.add(url)
		domain = self.get_domain(url)
		
		if domain not in self.domains_found:
			self.domains_found.add(domain)
			await self.write_domain(domain)

		html, headers = await self.fetch_url(session, url)
		if html:
			platforms = self.detect_platform(html, url, headers)
			if platforms:
				self.platform_results[domain] = platforms

			links = self.extract_links(html, url)
			tasks = []
			for link in links:
				if link not in self.visited_urls:
					tasks.append(self.crawl_url(session, link, depth + 1))
			if tasks:
				await asyncio.gather(*tasks)

	async def write_results_to_file(self, filename='crawl_results.json'):
		results = {
			'total_domains': len(self.domains_found),
			'all_domains': sorted(list(self.domains_found)),
			'platform_detection': self.platform_results
		}
		async with aiofiles.open(filename, 'w') as f:
			await f.write(json.dumps(results, indent=4))

	async def start_crawl(self, start_url):
		# Clear the output file at the start of crawling
		async with aiofiles.open(self.output_file, 'w') as f:
			await f.write('')

		async with aiohttp.ClientSession() as session:
			await self.crawl_url(session, start_url, 0)
		
		# Write final results to JSON file
		await self.write_results_to_file()
		return self.domains_found, self.platform_results

def main():
	start_url = 'https://builtwith.com'  # Replace with your starting URL
	crawler = WebCrawler(max_depth=3, max_concurrent=20)

	async def run_crawler():
		domains, platforms = await crawler.start_crawl(start_url)
		print(f'Found {len(domains)} unique domains')
		print('\nPlatform Detection Results:')
		for domain, detected_platforms in platforms.items():
			print(f'{domain}: {", ".join(detected_platforms)}')
		print('\nFull results written to crawl_results.json')

	asyncio.run(run_crawler())

if __name__ == '__main__':
	main()
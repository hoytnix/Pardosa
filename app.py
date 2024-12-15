import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
import argparse
import json
import re
from datetime import datetime

class WebCrawler:
	def __init__(self, max_depth=2, max_concurrent=10, output_file='discovered_domains.txt', results_file='fingerprint_results.json'):
		self.max_depth = max_depth
		self.max_concurrent = max_concurrent
		self.visited_urls = set()
		self.domains_found = set()
		self.domains_to_crawl = set()
		self.domains_crawled = set()
		self.platform_results = {}
		self.semaphore = asyncio.Semaphore(max_concurrent)
		self.output_file = output_file
		self.results_file = results_file
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

	async def write_fingerprint(self, domain, platforms, status='active'):
		async with self.file_lock:
			try:
				# Read existing results
				try:
					async with aiofiles.open(self.results_file, 'r') as f:
						content = await f.read()
						results = json.loads(content) if content else {}
				except (FileNotFoundError, json.JSONDecodeError):
					results = {}

				# Update results
				results[domain] = {
					'platforms': platforms,
					'status': status,
					'last_checked': datetime.now().isoformat()
				}

				# Write updated results
				async with aiofiles.open(self.results_file, 'w') as f:
					await f.write(json.dumps(results, indent=4))
					await f.flush()
			except Exception as e:
				print(f'Error writing fingerprint for {domain}: {str(e)}')

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

	async def fingerprint_domain(self, session, domain):
		url = f'https://{domain}'
		try:
			html, headers = await self.fetch_url(session, url)
			if html:
				platforms = self.detect_platform(html, url, headers)
				await self.write_fingerprint(domain, platforms)
				return platforms
			return []
		except Exception as e:
			# Try with www. prefix if direct domain fails
			if not domain.startswith('www.'):
				try:
					www_url = f'https://www.{domain}'
					html, headers = await self.fetch_url(session, www_url)
					if html:
						platforms = self.detect_platform(html, www_url, headers)
						await self.write_fingerprint(domain, platforms)
						return platforms
					return []
				except Exception as e:
					print(f'Error fingerprinting www.{domain}: {str(e)}')
				await self.write_fingerprint(domain, [], status='error')
				return []
			print(f'Error fingerprinting {domain}: {str(e)}')
			await self.write_fingerprint(domain, [], status='error')
			return []

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
			self.domains_to_crawl.add(domain)
			await self.write_domain(domain)
			# Immediately fingerprint new domain
			platforms = await self.fingerprint_domain(session, domain)
			if platforms:
				self.platform_results[domain] = platforms

		html, headers = await self.fetch_url(session, url)
		if html:
			links = self.extract_links(html, url)
			tasks = []
			for link in links:
				if link not in self.visited_urls:
					tasks.append(self.crawl_url(session, link, depth + 1))
			if tasks:
				await asyncio.gather(*tasks)

	async def crawl_domain(self, session, domain):
		if domain in self.domains_crawled:
			return
		
		self.domains_crawled.add(domain)
		start_url = f'https://{domain}'
		try:
			await self.crawl_url(session, start_url, 0)
		except Exception as e:
			print(f'Error crawling domain {domain}: {str(e)}')
			# Try with www. prefix if the direct domain fails
			if not domain.startswith('www.'):
				try:
					www_url = f'https://www.{domain}'
					await self.crawl_url(session, www_url, 0)
				except Exception as e:
					print(f'Error crawling www.{domain}: {str(e)}')

	async def start_crawl(self, start_url):
		# Clear the output files at the start of crawling
		async with aiofiles.open(self.output_file, 'w') as f:
			await f.write('')
		async with aiofiles.open(self.results_file, 'w') as f:
			await f.write('{}')

		async with aiohttp.ClientSession() as session:
			# First crawl the start URL
			print(f'Starting initial crawl of {start_url}')
			await self.crawl_url(session, start_url, 0)
			
			# Then crawl all discovered domains
			while self.domains_to_crawl - self.domains_crawled:
				domain = (self.domains_to_crawl - self.domains_crawled).pop()
				print(f'Crawling discovered domain: {domain}')
				await self.crawl_domain(session, domain)

		return self.domains_found, self.platform_results

import argparse

def parse_arguments():
	# Create argument parser
	parser = argparse.ArgumentParser(description='Pardosa - Web Platform Fingerprinting Crawler')

	# Add arguments
	parser.add_argument(
		'--url',
		default='https://wordpress.org',
		help='Starting URL for the crawler (default: https://wordpress.org)'
	)

	parser.add_argument(
		'--depth',
		type=int,
		default=1,
		help='Maximum crawl depth (default: 1)'
	)

	parser.add_argument(
		'--concurrent',
		type=int,
		default=10,
		help='Maximum concurrent requests (default: 10)'
	)

	return parser.parse_args()

def main():
	# Parse command line arguments
	args = parse_arguments()

	# Initialize crawler with command line parameters
	crawler = WebCrawler(
		max_depth=args.depth,
		max_concurrent=args.concurrent
	)

	async def run_crawler():
		domains, platforms = await crawler.start_crawl(args.url)
		print(f'\nCrawling completed!')
		print(f'Total unique domains found: {len(domains)}')
		print(f'Total domains crawled: {len(crawler.domains_crawled)}')
		print('\nPlatform Detection Results:')
		for domain, detected_platforms in platforms.items():
			print(f'{domain}: {", ".join(detected_platforms)}')
		print('\nFull results written to fingerprint_results.json')

	asyncio.run(run_crawler())

if __name__ == '__main__':
	main()

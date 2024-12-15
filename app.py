import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from collections import deque, defaultdict
import json
import re
from datetime import datetime, timedelta
import argparse

class ContactFinder:
	def __init__(self):
		# Email pattern
		self.email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
		
		# Phone patterns for various formats
		self.phone_patterns = [
			r'\+?\d{1,3}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # International
			r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # US/Canada
			r'\d{4}[-.\s]?\d{3}[-.\s]?\d{3}'  # Alternative format
		]
		
		# Organization name patterns
		self.org_patterns = [
			r'(?i)about\s+([\w\s&,.-]+(?:Inc\.|LLC|Ltd\.|Corp\.|Corporation|Company|Co\.|Limited))',
			r'(?i)([\w\s&,.-]+(?:Inc\.|LLC|Ltd\.|Corp\.|Corporation|Company|Co\.|Limited))',
			r'©\s*\d{4}\s+([\w\s&,.-]+)'
		]
		
		# Employee patterns
		self.employee_patterns = [
			r'(?i)(?:CEO|CTO|CFO|founder|president|director):\s*([\w\s.-]+)',
			r'(?i)(?:team|staff|employee):\s*([\w\s.-]+)',
			r'(?i)contact\s+([\w\s.-]+)\s+at'
		]

	def find_emails(self, text):
		return list(set(re.findall(self.email_pattern, text)))

	def find_phones(self, text):
		phones = []
		for pattern in self.phone_patterns:
			phones.extend(re.findall(pattern, text))
		return list(set(phones))

	def find_organization(self, text):
		for pattern in self.org_patterns:
			matches = re.findall(pattern, text)
			if matches:
				return matches[0].strip()
		return None

	def find_employees(self, text):
		employees = []
		for pattern in self.employee_patterns:
			employees.extend(re.findall(pattern, text))
		return list(set(employees))

	def extract_all_contact_info(self, html, url):
		result = {
			'organization': None,
			'emails': [],
			'phones': [],
			'employees': [],
			'employee_contacts': []
		}
		
		# Extract information from HTML
		result['organization'] = self.find_organization(html)
		result['emails'] = self.find_emails(html)
		result['phones'] = self.find_phones(html)
		result['employees'] = self.find_employees(html)
		
		# Try to match employees with their contact information
		employee_contacts = []
		for employee in result['employees']:
			# Look for contact info near employee mentions
			context = self._get_context(html, employee, 200)  # Get 200 chars around employee mention
			if context:
				employee_contact = {
					'name': employee,
					'email': self.find_emails(context),
					'phone': self.find_phones(context)
				}
				employee_contacts.append(employee_contact)
		
		result['employee_contacts'] = employee_contacts
		return result

	def _get_context(self, text, target, window_size):
		try:
			index = text.index(target)
			start = max(0, index - window_size)
			end = min(len(text), index + len(target) + window_size)
			return text[start:end]
		except ValueError:
			return None

class WebCrawler:
	def __init__(self, max_depth=1, max_concurrent=10, output_file='discovered_domains.txt', results_file='fingerprint_results.json'):
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
		self.contact_finder = ContactFinder()

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

	async def write_fingerprint(self, domain, results, status='active'):
		async with self.file_lock:
			try:
				# Read existing results
				try:
					async with aiofiles.open(self.results_file, 'r') as f:
						content = await f.read()
						all_results = json.loads(content) if content else {}
				except (FileNotFoundError, json.JSONDecodeError):
					all_results = {}

				# Update results
				all_results[domain] = {
					'platforms': results['platforms'],
					'contact_info': results['contact_info'],
					'status': status,
					'last_checked': datetime.now().isoformat()
				}

				# Write updated results
				async with aiofiles.open(self.results_file, 'w') as f:
					await f.write(json.dumps(all_results, indent=4))
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

	def detect_platform_and_contacts(self, html, url, headers):
		# Get platform information
		platforms = self.detect_platform(html, url, headers)
		
		# Get contact information
		contact_info = self.contact_finder.extract_all_contact_info(html, url)
		
		return {
			'platforms': platforms,
			'contact_info': contact_info
		}

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

	def needs_update(self, domain, results):
		"""Check if a domain needs to be updated based on last check time."""
		if domain not in results:
			return True
		
		try:
			last_checked = datetime.fromisoformat(results[domain]['last_checked'])
			month_ago = datetime.now() - timedelta(days=30)
			return last_checked < month_ago
		except (KeyError, ValueError):
			return True

	def get_domains_needing_update(self, results):
		"""Get list of all domains that need updating."""
		domains_to_update = set()
		for domain, data in results.items():
			if self.needs_update(domain, results):
				domains_to_update.add(domain)
		return domains_to_update

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
			
			# Fetch and analyze the page
			html, headers = await self.fetch_url(session, url)
			if html:
				# Get both platform and contact information
				results = self.detect_platform_and_contacts(html, url, headers)
				await self.write_fingerprint(domain, results)
				if results['platforms']:
					self.platform_results[domain] = results

				# Extract and follow links
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

	async def start_continuous_crawl(self, start_url):
		# Clear the output file at the start of initial crawling
		async with aiofiles.open(self.output_file, 'w') as f:
			await f.write('')

		# Load existing results or create new file
		try:
			async with aiofiles.open(self.results_file, 'r') as f:
				content = await f.read()
				all_results = json.loads(content) if content else {}
		except (FileNotFoundError, json.JSONDecodeError):
			all_results = {}
			async with aiofiles.open(self.results_file, 'w') as f:
				await f.write('{}')

		while True:  # Continuous crawling loop
			async with aiohttp.ClientSession() as session:
				# First, crawl the start URL if it hasn't been crawled recently
				start_domain = self.get_domain(start_url)
				if self.needs_update(start_domain, all_results):
					print(f'\nStarting crawl of {start_url}')
					await self.crawl_url(session, start_url, 0)

				# Then process all domains that need updating
				domains_to_update = self.get_domains_needing_update(all_results)
				if domains_to_update:
					print(f'\nFound {len(domains_to_update)} domains needing update')
					for domain in domains_to_update:
						print(f'Crawling domain: {domain}')
						await self.crawl_domain(session, domain)
						# Reload results after each domain to get latest data
						async with aiofiles.open(self.results_file, 'r') as f:
							content = await f.read()
							all_results = json.loads(content) if content else {}
				else:
					print('\nNo domains need updating at this time')

			# Wait for an hour before checking again
			print('\nWaiting 1 hour before next check...')
			await asyncio.sleep(3600)

def parse_arguments():
	parser = argparse.ArgumentParser(description='Pardosa - Web Platform Fingerprinting Crawler')
	parser.add_argument('--url', default='https://builtwith.com',
					help='Starting URL for the crawler (default: https://builtwith.com)')
	parser.add_argument('--depth', type=int, default=5,
					help='Maximum crawl depth (default: 5)')
	parser.add_argument('--concurrent', type=int, default=20,
					help='Maximum concurrent requests (default: 20)')
	return parser.parse_args()

def main():
	args = parse_arguments()
	crawler = WebCrawler(max_depth=args.depth, max_concurrent=args.concurrent)

	async def run_crawler():
		try:
			await crawler.start_continuous_crawl(args.url)
		except KeyboardInterrupt:
			print('\nCrawling interrupted by user')
		except Exception as e:
			print(f'\nError during crawling: {str(e)}')

	asyncio.run(run_crawler())

if __name__ == '__main__':
	main()

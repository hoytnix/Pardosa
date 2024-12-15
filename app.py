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
import time
import os

class RateLimiter:
    def __init__(self, rate_limit_kbps):
        self.rate_limit_bytes = rate_limit_kbps * 1024 / 8  # Convert Kbps to bytes per second
        self.last_check = time.time()
        self.bytes_consumed = 0

    async def consume(self, bytes_count):
        current_time = time.time()
        time_passed = current_time - self.last_check
        
        if time_passed >= 1.0:
            # Reset counter if a second has passed
            self.bytes_consumed = 0
            self.last_check = current_time
        else:
            if self.bytes_consumed >= self.rate_limit_bytes:
                # Wait until the next second if we've exceeded our rate limit
                sleep_time = 1.0 - time_passed
                await asyncio.sleep(sleep_time)
                self.bytes_consumed = 0
                self.last_check = time.time()
        
        self.bytes_consumed += bytes_count

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
    def __init__(self, max_depth=1, max_concurrent=10, rate_limit_kbps=1024, timeout=5, data_dir='data'):
        self.max_depth = max_depth
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.visited_urls = set()
        self.domains_found = set()
        self.domains_to_crawl = set()
        self.domains_crawled = set()
        self.platform_results = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.data_dir = data_dir
        self.file_lock = asyncio.Lock()
        self.contact_finder = ContactFinder()
        self.rate_limiter = RateLimiter(rate_limit_kbps)
        os.makedirs(data_dir, exist_ok=True)

    def get_domain_file_path(self, domain):
        safe_filename = domain.replace(':', '_').replace('/', '_')
        return os.path.join(self.data_dir, f'{safe_filename}.json')

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
        domain_file = self.get_domain_file_path(domain)
        async with self.file_lock:
            if not os.path.exists(domain_file):
                async with aiofiles.open(domain_file, 'w') as f:
                    await f.write(json.dumps({'discovery_date': datetime.now().isoformat()}))
                    await f.flush()

    async def write_fingerprint(self, domain, results, status='active'):
        domain_file = self.get_domain_file_path(domain)
        async with self.file_lock:
            try:
                # Create domain-specific result
                domain_result = {
                    'platforms': results['platforms'],
                    'contact_info': results['contact_info'],
                    'status': status,
                    'last_checked': datetime.now().isoformat()
                }

                # Write to domain-specific file
                async with aiofiles.open(domain_file, 'w') as f:
                    await f.write(json.dumps(domain_result, indent=4))
                    await f.flush()
            except Exception as e:
                print(f'Error writing fingerprint for {domain}: {str(e)}')

    async def fetch_url(self, session, url):
        if not self.is_html_url(url):
            return None, None

        try:
            async with self.semaphore:
                # Use the configured timeout
                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with session.get(url, timeout=timeout) as response:
                    if response.status == 200:
                        content_type = response.headers.get('Content-Type', '').lower()
                        if 'text/html' not in content_type:
                            return None, None
                        
                        chunks = []
                        async for chunk in response.content.iter_chunked(8192):
                            await self.rate_limiter.consume(len(chunk))
                            chunks.append(chunk)
                        
                        html = b''.join(chunks).decode()
                        headers = dict(response.headers)
                        return html, headers
            return None, None
        except asyncio.TimeoutError:
            print(f'Timeout fetching {url}: Request took longer than {self.timeout} seconds')
            return None, None
        except Exception as e:
            print(f'Error fetching {url}: {str(e)}')
            return None, None

    def detect_platform_and_contacts(self, html, url, headers):
        platforms = self.detect_platform(html, url, headers)
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
        domain_file = self.get_domain_file_path(domain)
        if not os.path.exists(domain_file):
            return True
        
        try:
            with open(domain_file, 'r') as f:
                data = json.loads(f.read())
                last_checked = datetime.fromisoformat(data['last_checked'])
                month_ago = datetime.now() - timedelta(days=30)
                return last_checked < month_ago
        except (KeyError, ValueError, json.JSONDecodeError, IOError):
            return True

    def get_all_domain_results(self):
        """Load results for all domains from individual files."""
        results = {}
        try:
            for filename in os.listdir(self.data_dir):
                if filename.endswith('.json'):
                    domain = filename[:-5]  # Remove .json extension
                    file_path = os.path.join(self.data_dir, filename)
                    try:
                        with open(file_path, 'r') as f:
                            results[domain] = json.loads(f.read())
                    except (json.JSONDecodeError, IOError) as e:
                        print(f'Error reading {filename}: {str(e)}')
        except Exception as e:
            print(f'Error reading data directory: {str(e)}')
        return results

    def get_domains_needing_update(self, results):
        """Get list of all domains that need updating."""
        domains_to_update = set()
        for domain in self.domains_found:
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
        # Initialize domains_found from existing files
        all_results = self.get_all_domain_results()
        self.domains_found.update(all_results.keys())

        while True:  # Continuous crawling loop
            async with aiohttp.ClientSession() as session:
                # First, crawl the start URL if it hasn't been crawled recently
                start_domain = self.get_domain(start_url)
                if self.needs_update(start_domain, all_results):
                    print(f'\nStarting crawl of {start_url}')
                    await self.crawl_url(session, start_url, 0)
                    # Reload results after initial crawl
                    all_results = self.get_all_domain_results()

                # Then process all domains that need updating
                domains_to_update = self.get_domains_needing_update(all_results)
                if domains_to_update:
                    print(f'\nFound {len(domains_to_update)} domains needing update')
                    for domain in domains_to_update:
                        print(f'Crawling domain: {domain}')
                        self.visited_urls.clear()
                        # Reset domains_found for each domain crawl to discover new links
                        self.domains_found = {domain}
                        await self.crawl_domain(session, domain)
                        # Add newly discovered domains to the main set
                        self.domains_found.update(all_results.keys())
                        # Reload all results
                        all_results = self.get_all_domain_results()
                    print(f'Completed updating {len(domains_to_update)} domains')
                else:
                    print('\nNo domains need updating at this time')
                    print(f'Total domains tracked: {len(all_results)}')
                    print(f'Total domains found: {len(self.domains_found)}')

                # Wait for an hour before checking again
                print('\nWaiting 1 hour before next check...')
                await asyncio.sleep(3600)

def parse_arguments():
    parser = argparse.ArgumentParser(description='Pardosa - Web Platform Fingerprinting Crawler')
    parser.add_argument('--url', default='https://wordpress.org',
                    help='Starting URL for the crawler (default: https://wordpress.org)')
    parser.add_argument('--depth', type=int, default=1,
                    help='Maximum crawl depth (default: 1)')
    parser.add_argument('--concurrent', type=int, default=10,
                    help='Maximum concurrent requests (default: 10)')
    parser.add_argument('--rate-limit', type=int, default=1024,
                    help='Rate limit in Kbps (default: 1024)')
    parser.add_argument('--timeout', type=int, default=5,
                    help='Request timeout in seconds (default: 5)')
    return parser.parse_args()

def main():
    args = parse_arguments()
    crawler = WebCrawler(
        max_depth=args.depth,
        max_concurrent=args.concurrent,
        rate_limit_kbps=args.rate_limit,
        timeout=args.timeout
    )

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

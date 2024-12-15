import asyncio
import aiohttp
import aiofiles
import argparse
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
import threading
import time
import os

class Pardosa:
    def __init__(self, initial_url=None, max_depth=2, threads=5, throttle_kbps=None, verbose=False, timeout=5):
        self.initial_url = initial_url
        self.max_depth = max_depth
        self.max_threads = threads
        self.throttle_kbps = throttle_kbps
        self.verbose = verbose
        self.timeout = timeout
        self.visited_urls = set()
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        self.semaphore = asyncio.Semaphore(threads)
        self.fqdn_lock = threading.Lock()
        self.active_fqdns = set()

    async def start(self):
        if self.initial_url:
            await self.crawl_url(self.initial_url, 0)
        else:
            await self.crawl_outdated_fqdns()

    async def crawl_outdated_fqdns(self):
        for file in self.data_dir.glob('*.json'):
            with open(file, 'r') as f:
                data = json.load(f)
                last_crawled = datetime.fromisoformat(data['last_crawled'])
                if datetime.now() - last_crawled > timedelta(days=30):
                    await self.crawl_url(f"https://{file.stem}", 0)

    def is_valid_url(self, url):
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'],
                       result.netloc,
                       not any(ext in url.lower() for ext in ['.jpg', '.png', '.gif', '.pdf'])])
        except:
            return False

    async def throttle(self):
        if self.throttle_kbps:
            await asyncio.sleep(1/self.throttle_kbps)

    async def crawl_url(self, url, depth):
        if depth > self.max_depth or url in self.visited_urls:
            return

        self.visited_urls.add(url)
        fqdn = urlparse(url).netloc

        with self.fqdn_lock:
            if fqdn in self.active_fqdns:
                return
            self.active_fqdns.add(fqdn)

        try:
            async with self.semaphore:
                if self.verbose:
                    print(f"Crawling: {url}")

                timeout = aiohttp.ClientTimeout(total=self.timeout)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url) as response:
                        await self.throttle()
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Fingerprint technologies
                            tech_fingerprints = self.fingerprint_technologies(html, soup)
                            
                            # Fingerprint contact information
                            contact_info = self.fingerprint_contact_info(html, soup, url)
                            
                            # Save fingerprints
                            data = {
                                'url': url,
                                'last_crawled': datetime.now().isoformat(),
                                'technologies': tech_fingerprints,
                                'contact_info': contact_info
                            }
                            
                            await self.save_fingerprints(fqdn, data)
                            
                            # Find and crawl links
                            links = [urljoin(url, link.get('href')) for link in soup.find_all('a', href=True)]
                            valid_links = [link for link in links if self.is_valid_url(link)]
                            
                            tasks = [self.crawl_url(link, depth + 1) for link in valid_links]
                            await asyncio.gather(*tasks)

        except asyncio.TimeoutError:
            if self.verbose:
                print(f"Timeout occurred while crawling {url}")
        except Exception as e:
            if self.verbose:
                print(f"Error crawling {url}: {str(e)}")
        finally:
            with self.fqdn_lock:
                self.active_fqdns.remove(fqdn)

    def fingerprint_technologies(self, html, soup):
        techs = []
        
        # Shopify
        if 'Shopify.shop' in html or 'cdn.shopify.com' in html:
            techs.append('Shopify')
            
        # WordPress
        if 'wp-content' in html or 'wp-includes' in html:
            techs.append('WordPress')
            
        # WooCommerce
        if 'woocommerce' in html or 'is-woocommerce' in html:
            techs.append('WooCommerce')
            
        # ClickFunnels 2.0
        if 'clickfunnels' in html or 'cf2.0' in html:
import asyncio
import aiohttp
import aiofiles
import argparse
import json
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse
import threading
import time
import os

class Pardosa:
	def __init__(self, initial_url=None, max_depth=2, threads=5, throttle_kbps=None, verbose=False, timeout=5):
		self.initial_url = initial_url
		self.max_depth = max_depth
		self.max_threads = threads
		self.throttle_kbps = throttle_kbps
		self.verbose = verbose
		self.timeout = timeout
		self.visited_urls = set()
		self.data_dir = Path('data')
		self.data_dir.mkdir(exist_ok=True)
		self.semaphore = asyncio.Semaphore(threads)
		self.fqdn_lock = threading.Lock()
		self.active_fqdns = set()

	async def start(self):
		if self.initial_url:
			await self.crawl_url(self.initial_url, 0)
		else:
			await self.crawl_outdated_fqdns()

	async def crawl_outdated_fqdns(self):
		for file in self.data_dir.glob('*.json'):
			with open(file, 'r') as f:
				data = json.load(f)
				last_crawled = datetime.fromisoformat(data['last_crawled'])
				if datetime.now() - last_crawled > timedelta(days=30):
					await self.crawl_url(f"https://{file.stem}", 0)

	def is_valid_url(self, url):
		try:
			result = urlparse(url)
			return all([result.scheme in ['http', 'https'],
				   result.netloc,
				   not any(ext in url.lower() for ext in ['.jpg', '.png', '.gif', '.pdf'])])
		except:
			return False

	async def throttle(self):
		if self.throttle_kbps:
			await asyncio.sleep(1/self.throttle_kbps)

	async def crawl_url(self, url, depth):
		if depth > self.max_depth or url in self.visited_urls:
			return

		self.visited_urls.add(url)
		fqdn = urlparse(url).netloc

		with self.fqdn_lock:
			if fqdn in self.active_fqdns:
				return
			self.active_fqdns.add(fqdn)

		try:
			async with self.semaphore:
				if self.verbose:
					print(f"Crawling: {url}")

				timeout = aiohttp.ClientTimeout(total=self.timeout)
				async with aiohttp.ClientSession(timeout=timeout) as session:
					async with session.get(url) as response:
						await self.throttle()
						if response.status == 200:
							html = await response.text()
							soup = BeautifulSoup(html, 'html.parser')
							
							# Fingerprint technologies
							tech_fingerprints = self.fingerprint_technologies(html, soup)
							
							# Fingerprint contact information
							contact_info = self.fingerprint_contact_info(html, soup, url)
							
							# Save fingerprints
							data = {
								'url': url,
								'last_crawled': datetime.now().isoformat(),
								'technologies': tech_fingerprints,
								'contact_info': contact_info
							}
							
							await self.save_fingerprints(fqdn, data)
							
							# Find and crawl links
							links = [urljoin(url, link.get('href')) for link in soup.find_all('a', href=True)]
							valid_links = [link for link in links if self.is_valid_url(link)]
							
							tasks = [self.crawl_url(link, depth + 1) for link in valid_links]
							await asyncio.gather(*tasks)

		except asyncio.TimeoutError:
			if self.verbose:
				print(f"Timeout occurred while crawling {url}")
		except Exception as e:
			if self.verbose:
				print(f"Error crawling {url}: {str(e)}")
		finally:
			with self.fqdn_lock:
				self.active_fqdns.remove(fqdn)

	# Rest of the class methods remain unchanged...

def main():
	parser = argparse.ArgumentParser(description='Pardosa Web Crawler')
	parser.add_argument('--url', help='Initial URL to crawl')
	parser.add_argument('--depth', type=int, default=2, help='Maximum crawl depth')
	parser.add_argument('--threads', type=int, default=5, help='Number of threads')
	parser.add_argument('--throttle', type=int, help='Throttle bandwidth per thread in Kbps')
	parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
	parser.add_argument('--timeout', type=int, default=5, help='Timeout in seconds for each page crawl')
	
	args = parser.parse_args()
	
	crawler = Pardosa(
		initial_url=args.url,
		max_depth=args.depth,
		threads=args.threads,
		throttle_kbps=args.throttle,
		verbose=args.verbose,
		timeout=args.timeout
	)
	
	asyncio.run(crawler.start())

if __name__ == '__main__':
	main()
        max_depth=args.depth,
        threads=args.threads,
        throttle_kbps=args.throttle,
        verbose=args.verbose,
        timeout=args.timeout
    )
    
    asyncio.run(crawler.start())

if __name__ == '__main__':
    main()

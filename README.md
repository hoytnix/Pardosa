This is the complete, integrated code that combines all the requested features:

1. Asynchronous web crawling with concurrent requests
2. HTML-only crawling with proper content-type checking
3. HTTP/HTTPS URL validation
4. Immediate domain writing to file as they're discovered
5. Platform detection for WordPress, Shopify, ClickFunnels 2.0, and Kajabi
6. Comprehensive results output in JSON format

To use this code:

1. Install required packages:
```bash
pip install aiohttp aiofiles beautifulsoup4
```

2. Replace the start_url in main() with your target URL

3. Run the script

The crawler will:
- Write domains to 'discovered_domains.txt' as they're found
- Write complete results including platform detection to 'crawl_results.json'
- Show progress and results in the console

The code includes proper error handling, thread-safe file operations, and efficient resource usage through connection pooling and concurrent requests limiting.

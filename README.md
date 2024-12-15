# Pardosa
## Multithreaded Asynchronous Web Platform Fingerprinting Crawler

A high-performance asynchronous web crawler that discovers and fingerprints web platforms in real-time. Built with Python, it efficiently crawls websites, identifies platform technologies, and maintains immediate records of findings.

## Key Features

- **Asynchronous Operation**: Uses Python's asyncio for concurrent crawling
- **Real-time Fingerprinting**: Identifies platforms as domains are discovered
- **Platform Detection**: Currently detects:
  - WordPress
  - Shopify
  - ClickFunnels 2.0
  - Kajabi
- **Smart Crawling**: 
  - HTML-only processing
  - HTTP/HTTPS protocol filtering
  - Automatic www subdomain handling
- **Live Results**: Writes discoveries to file immediately

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/platform-fingerprint-crawler
cd platform-fingerprint-crawler

# Install required packages
pip install aiohttp aiofiles beautifulsoup4
```

## Usage

```python
# Run the crawler
python crawler.py
```

## Configuration

Modify these parameters in the main() function:

```python
start_url = 'https://example.com'  # Starting point for crawl
crawler = WebCrawler(
    max_depth=2,          # How deep to crawl
    max_concurrent=10,     # Maximum concurrent requests
    output_file='discovered_domains.txt',
    results_file='fingerprint_results.json'
)
```

## Output Files

### discovered_domains.txt
```text
example.com
subdomain.example.com
another-domain.com
```

### fingerprint_results.json
```json
{
    "example.com": {
        "platforms": ["WordPress", "Shopify"],
        "status": "active",
        "last_checked": "2023-XX-XX:XX:XX"
    }
}
```

## Error Handling

- Attempts direct domain access first
- Falls back to www prefix if needed
- Records failed attempts with error status
- Continues crawling despite individual domain failures

## Performance Considerations

- Uses connection pooling via aiohttp
- Implements concurrent request limiting
- Filters non-HTML resources early
- Maintains thread-safe file operations

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Legal Considerations

- Respect robots.txt files
- Implement appropriate rate limiting
- Check terms of service before crawling sites
- Use responsibly and ethically

# Pardosa

This is an asynchronous web crawler built in Python that discovers and fingerprints web platforms. It identifies technologies used by websites, starting from a specified URL and exploring links up to two levels deep. The current configuration starts the crawl from [https://builtwith.com](https://builtwith.com).

## Features

- **Asynchronous Crawling**: Utilizes `asyncio` and `aiohttp` for non-blocking, concurrent requests.
- **Platform Detection**: Identifies popular web platforms such as WordPress, Shopify, ClickFunnels 2.0, and Kajabi based on typical indicators in webpage content.
- **HTML-Only Crawling**: Filters and processes only HTML documents, ignoring resources like images, scripts, and stylesheets.
- **Domain Discovery**: Collects unique Fully Qualified Domain Names (FQDNs) during the crawl and writes them to a file.
- **Immediate Fingerprinting**: Newly discovered domains are fingerprinted in real-time, and results are saved immediately.
- **Error Handling**: Robust error management, including retries with `www` prefixes and logging.

## Requirements

- Python 3.7+
- Packages:
  - `aiohttp`
  - `aiofiles`
  - `beautifulsoup4`

Install the required packages using pip:

```bash
pip install aiohttp aiofiles beautifulsoup4
```

## Usage

1. **Clone the repository**:

   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Run the crawler**:

   Execute the main script:

   ```bash
   python crawler.py
   ```

   The crawler will start from `https://builtwith.com` and output results to `discovered_domains.txt` and `fingerprint_results.json`.

3. **Review Results**:
   - `discovered_domains.txt`: A list of discovered domains.
   - `fingerprint_results.json`: Detailed fingerprint data of platforms detected on each domain.

## Configuration

- **Start URL**: Change the `start_url` variable in `main()` to the desired starting point.
- **Max Depth**: Adjust `max_depth` in the `WebCrawler` class to control crawl depth.
- **Concurrency**: Set `max_concurrent` to alter the number of simultaneous requests.

## Limitations

- Ensure compliance with the `robots.txt` and terms of service of websites.
- Consider implementing rate limiting to avoid potential IP blocks due to too many rapid requests.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contribution

Feel free to submit issues, fork the repository, and make pull requests for any enhancements or fixes.

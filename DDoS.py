import aiohttp
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import logging

# Configure logging
logging.basicConfig(level=logging.WARNING)

# Initialize the base URLs
base_urls = ["https://mielenterveyskaikille.fi"]
all_urls = set()  # Store all processed URLs
total_bandwidth = 0  # Total bandwidth used


async def fetch_sitemap(session, base_url, _: bool = True):
    url = urljoin(base_url, "/sitemap.xml") if _ else base_url
    async with session.get(url) as response:
        if response.status == 200:
            sitemap_content = await response.text()
            soup = BeautifulSoup(sitemap_content, "xml")
            urls = soup.find_all("loc")
            filtered_urls = [
                url.text for url in urls if not "xml" in url.text
            ]  # Filter out URLs not containing base URL
            xml_urls = [
                url.text for url in urls if ".xml" in url.text
            ]  # Filter out URLs not containing base URL

            for url in xml_urls:
                logging.debug(f"Recursively fetching sitemap from {url}")
                filtered_urls += await fetch_sitemap(
                    session, url, False
                )  # Recursively fetch sitemaps

            if not _:
                logging.debug(filtered_urls)  # Output filtered URLs for debugging

            return filtered_urls
        else:
            logging.error(f"Failed to fetch sitemap from {base_url}")
            return []


async def fetch_resource(session, resource_url):
    global total_bandwidth
    count_shall_be = 1
    count = 0
    file_format = resource_url.split(".")[-1].lower()
    if file_format == "jpg":
        count_shall_be = 100

    if resource_url.endswith("/"):
        count_shall_be = 1000000

    tasks = []  # List to store the tasks
    while count <= count_shall_be:
        count += 1
        tasks.append(fetch_single_resource(session, resource_url))

    # Run all tasks concurrently
    await asyncio.gather(*tasks)


async def fetch_single_resource(session, resource_url):
    global total_bandwidth
    async with session.get(resource_url) as resource_response:
        if resource_response.status == 200:
            resource_content = await resource_response.read()  # Read content as bytes
            total_bandwidth += len(
                resource_content
            )  # Add the size of resource content to total bandwidth
            logging.info(f"Downloaded resource from {resource_url}")
            # Process the resource content here without saving it
        else:
            logging.error(f"Failed to download resource from {resource_url}")


async def fetch_and_process_resources(session, base_url):
    global total_bandwidth

    logging.info(f"Fetching: {base_url}")
    async with session.get(base_url) as response:
        resource_content = await response.read()  # Read content as bytes
        total_bandwidth += len(resource_content)
        html_soup = BeautifulSoup(
            resource_content, "html.parser"
        )  # Parse bytes directly
        resource_tags = html_soup.find_all(
            ["img", "script", "link", "video", "source", "iframe"], src=True
        )

        # Extract and process resource URLs from the homepage
        for resource_tag in resource_tags:
            resource_url = urljoin(base_url, resource_tag["src"])
            if resource_url.startswith(
                base_url
            ):  # Check if resource URL belongs to the base URL
                all_urls.add(resource_url)
                await fetch_resource(session, resource_url)


import math


# Function to convert bytes to the appropriate unit (bytes, KB, MB, GB, TB)
def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


async def main():
    try:
        async with aiohttp.ClientSession() as session:
            while True:
                logging.warning(f"Bandwidth used: {convert_size(total_bandwidth)}")

                tasks = []
                for base_url in base_urls:
                    # Fetch URLs from sitemap
                    urls = await fetch_sitemap(session, base_url)

                    for url in urls:
                        # Check each URL
                        tasks.append(fetch_and_process_resources(session, url))

                await asyncio.gather(*tasks)

                while True:
                    logging.warning(f"Bandwidth used: {convert_size(total_bandwidth)}")

                    tasks = []
                    for url in list(all_urls):
                        tasks.append(fetch_resource(session, url))

                    await asyncio.gather(*tasks)

    except Exception as e:
        logging.error(f"An error occurred: {e}")

    finally:
        logging.info(f"Total bandwidth used: {total_bandwidth} bytes")


# Run the main function
asyncio.run(main())

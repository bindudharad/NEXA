import webbrowser
from pathlib import Path


class BrowserAgent:
    known_sites = {
        "github": "https://github.com",
        "google": "https://google.com",
        "stackoverflow": "https://stackoverflow.com",
        "stack overflow": "https://stackoverflow.com",
    }

    def execute(self, action: str, params: dict) -> dict:
        return getattr(self, action)(**params)

    def normalize_url(self, target: str) -> str:
        lower = target.lower().strip()
        if lower in self.known_sites:
            return self.known_sites[lower]
        if not lower.startswith(("http://", "https://", "file://", "data:")):
            return f"https://{target}"
        return target

    def open_url(self, target: str) -> dict:
        url = self.normalize_url(target)
        webbrowser.open(url)
        return {"opened": url}

    async def search_google(self, query: str) -> dict:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(url)
        return {"opened": url, "query": query}

    async def fill_form(self, url: str, fields: dict[str, str], submit_selector: str | None = None) -> dict:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.normalize_url(url), wait_until="domcontentloaded")
            filled = []
            for selector, value in fields.items():
                await page.fill(selector, value)
                filled.append(selector)
            if submit_selector:
                await page.click(submit_selector)
                await page.wait_for_load_state("networkidle")
            title = await page.title()
            await browser.close()
            return {"url": url, "filled": filled, "title": title}

    async def download_file(self, url: str, click_selector: str, destination: str | None = None) -> dict:
        from playwright.async_api import async_playwright

        target_dir = Path(destination).expanduser() if destination else Path.home() / "Downloads"
        target_dir.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.normalize_url(url), wait_until="domcontentloaded")
            async with page.expect_download() as download_info:
                await page.click(click_selector)
            download = await download_info.value
            target = target_dir / download.suggested_filename
            await download.save_as(target)
            await browser.close()
            return {"downloaded": str(target)}

    async def scrape_title(self, url: str) -> dict:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(self.normalize_url(url), wait_until="domcontentloaded")
            title = await page.title()
            await browser.close()
            return {"url": url, "title": title}

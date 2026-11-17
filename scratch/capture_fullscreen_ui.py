import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use full HD 1920x1080 desktop viewport
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()
        
        # Login
        await page.goto("http://localhost:8000/admin", timeout=15000)
        await page.wait_for_selector("[data-testid=login-username]", timeout=5000)
        await page.fill("[data-testid=login-username]", "admin")
        await page.fill("[data-testid=login-password]", "admin123")
        await page.click("[data-testid=login-submit]")
        await page.wait_for_timeout(1500)
        
        # 1. Capture full width admin page
        await page.goto("http://localhost:8000/admin", timeout=15000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="C:/Users/ADMIN/.gemini/antigravity/brain/ba340a36-97fb-4bb4-a7be-0d34636d78d7/admin_full_width_1920.png")
        print("Captured admin_full_width_1920.png")
        
        # 2. Capture full width simulation dedicated page
        await page.goto("http://localhost:8000/simulation", timeout=15000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="C:/Users/ADMIN/.gemini/antigravity/brain/ba340a36-97fb-4bb4-a7be-0d34636d78d7/simulation_full_width_1920.png")
        print("Captured simulation_full_width_1920.png")
        
        # Check scrollWidth vs innerWidth
        scroll_w = await page.evaluate("document.documentElement.scrollWidth")
        inner_w = await page.evaluate("window.innerWidth")
        print(f"scrollWidth: {scroll_w}, innerWidth: {inner_w}")
        assert scroll_w <= inner_w + 1, "Horizontal scroll detected!"
        print("No horizontal scrollbar, perfectly responsive!")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

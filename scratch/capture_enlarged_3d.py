import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1400, 'height': 950})
        page = await context.new_page()
        
        # Login
        await page.goto("http://localhost:8000/admin", timeout=15000)
        await page.wait_for_selector("[data-testid=login-username]", timeout=5000)
        await page.fill("[data-testid=login-username]", "admin")
        await page.fill("[data-testid=login-password]", "admin123")
        await page.click("[data-testid=login-submit]")
        await page.wait_for_timeout(1500)
        
        # Navigate to simulation
        await page.goto("http://localhost:8000/simulation", timeout=15000)
        await page.wait_for_timeout(3000)
        
        # Take screenshot of enlarged 3D view
        await page.screenshot(path="C:/Users/ADMIN/.gemini/antigravity/brain/ba340a36-97fb-4bb4-a7be-0d34636d78d7/supermarket_3d_enlarged.png")
        print("Captured supermarket_3d_enlarged.png successfully")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

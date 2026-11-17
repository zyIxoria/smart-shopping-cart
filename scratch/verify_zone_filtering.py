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
        
        # 1. Click button "🥤 Đồ uống" to move cart to beverage
        await page.click('[data-testid="btn-goto-beverage"]')
        await page.wait_for_timeout(1500)
        
        # Verify beverage options
        options_bev = await page.eval_on_selector_all('[data-testid="select-product"] option', 'opts => opts.map(o => o.text)')
        print("Beverage items in dropdown:", options_bev)
        assert len(options_bev) == 5, f"Expected 5 beverage items, got {len(options_bev)}"
        await page.screenshot(path="C:/Users/ADMIN/.gemini/antigravity/brain/ba340a36-97fb-4bb4-a7be-0d34636d78d7/supermarket_zone_beverage.png")
        print("Saved supermarket_zone_beverage.png")
        
        # 2. Click button "🍜 Thực phẩm" to move cart to grocery
        await page.click('[data-testid="btn-goto-grocery"]')
        await page.wait_for_timeout(1500)
        
        options_groc = await page.eval_on_selector_all('[data-testid="select-product"] option', 'opts => opts.map(o => o.text)')
        print("Grocery items in dropdown:", options_groc)
        assert len(options_groc) == 7, f"Expected 7 grocery items, got {len(options_groc)}"
        await page.screenshot(path="C:/Users/ADMIN/.gemini/antigravity/brain/ba340a36-97fb-4bb4-a7be-0d34636d78d7/supermarket_zone_grocery.png")
        print("Saved supermarket_zone_grocery.png")
        
        # 3. Click button "🧼 Gia dụng" to move cart to household
        await page.click('[data-testid="btn-goto-household"]')
        await page.wait_for_timeout(1500)
        
        options_hh = await page.eval_on_selector_all('[data-testid="select-product"] option', 'opts => opts.map(o => o.text)')
        print("Household items in dropdown:", options_hh)
        assert len(options_hh) == 2, f"Expected 2 household items, got {len(options_hh)}"
        await page.screenshot(path="C:/Users/ADMIN/.gemini/antigravity/brain/ba340a36-97fb-4bb4-a7be-0d34636d78d7/supermarket_zone_household.png")
        print("Saved supermarket_zone_household.png")
        
        # 4. Click button "🪥 Cá nhân" to move cart to personal care
        await page.click('[data-testid="btn-goto-personal"]')
        await page.wait_for_timeout(1500)
        
        options_pc = await page.eval_on_selector_all('[data-testid="select-product"] option', 'opts => opts.map(o => o.text)')
        print("Personal care items in dropdown:", options_pc)
        assert len(options_pc) == 1, f"Expected 1 personal care item, got {len(options_pc)}"
        
        print("ALL ZONE RECOGNITION AND FILTERING TESTS PASSED PERFECTLY!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

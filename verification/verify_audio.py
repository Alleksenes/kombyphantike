from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    # Navigate to the demo page
    # Assuming python -m http.server 8080 is running
    page.goto("http://localhost:8080/demo_audio_client.html")

    # Verify initial state
    page.wait_for_selector("#currentWord")
    assert page.text_content("#currentWord") == "άνθρωπος"

    # Type new word
    page.fill("#textInput", "δοκιμή")
    page.click("text=Update")

    # Verify update
    assert page.text_content("#currentWord") == "δοκιμή"

    # Click play
    page.click(".speaker-icon")

    # Wait for spinner or error (since no API key)
    # The error message should appear within a few seconds
    try:
        page.wait_for_selector("#errorMsg:has-text('Error')", timeout=5000)
    except Exception:
        print("Backend might not be running or returned success unexpectedly.")

    # Take screenshot
    page.screenshot(path="verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)

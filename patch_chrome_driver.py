#!/usr/bin/env python3
"""
Patch the chrome_driver.py file to use Chromium instead of Chrome.
This script modifies the GoogleFindMyTools chrome_driver.py to work with Chromium.
"""

import os

CHROME_DRIVER_PATH = "/app/GoogleFindMyTools/chrome_driver.py"

def patch_chrome_driver():
    """Patch the chrome_driver.py file to add Chromium paths and headless options."""

    if not os.path.exists(CHROME_DRIVER_PATH):
        print(f"[Patch] Error: {CHROME_DRIVER_PATH} not found!")
        return False

    with open(CHROME_DRIVER_PATH, 'r') as f:
        content = f.read()

    # Check if already patched
    if 'driver_executable_path="/usr/bin/chromedriver"' in content:
        print("[Patch] chrome_driver.py already patched for Chromium.")
        return True

    # Patch 1: Add Chromium paths to the possiblePaths list
    old_paths = '''    possiblePaths = [
        r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\ProgramData\\chocolatey\\bin\\chrome.exe",
        r"C:\\Users\\%USERNAME%\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/local/bin/google-chrome",
        "/opt/google/chrome/chrome",
        "/snap/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    ]'''

    new_paths = '''    possiblePaths = [
        # Chromium paths (for Docker)
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        # Chrome paths
        r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        r"C:\\ProgramData\\chocolatey\\bin\\chrome.exe",
        r"C:\\Users\\%USERNAME%\\AppData\\Local\\Google\\Chrome\\Application\\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/local/bin/google-chrome",
        "/opt/google/chrome/chrome",
        "/snap/bin/chromium",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    ]'''

    if old_paths in content:
        content = content.replace(old_paths, new_paths)
        print("[Patch] Added Chromium paths.")
    else:
        print("[Patch] Warning: Could not find expected paths to patch.")

    # Patch 2: Add headless and Docker-friendly options
    old_options = '''def get_options():
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    return chrome_options'''

    new_options = '''def get_options():
    chrome_options = uc.ChromeOptions()
    # Docker-friendly options
    chrome_options.add_argument("--headless=new")  # New headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-setuid-sandbox")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("--window-size=1920,1080")

    return chrome_options'''

    if old_options in content:
        content = content.replace(old_options, new_options)
        print("[Patch] Added headless and Docker-friendly options.")
    else:
        print("[Patch] Warning: Could not find expected options to patch.")

    # Patch 3: Specify ChromeDriver path explicitly
    old_create_driver = '''def create_driver():
    """Create a Chrome WebDriver with undetected_chromedriver."""

    try:
        chrome_options = get_options()
        driver = uc.Chrome(options=chrome_options)
        print("[ChromeDriver] Installed and browser started.")
        return driver
    except Exception:
        print("[ChromeDriver] Default ChromeDriver creation failed. Trying alternative paths...")

        chrome_path = find_chrome()
        if chrome_path:
            chrome_options = get_options()
            chrome_options.binary_location = chrome_path
            try:
                driver = uc.Chrome(options=chrome_options)
                print(f"[ChromeDriver] ChromeDriver started using {chrome_path}")
                return driver
            except Exception as e:
                print(f"[ChromeDriver] ChromeDriver failed using path {chrome_path}: {e}")
        else:
            print("[ChromeDriver] No Chrome executable found in known paths.")

        raise Exception(
            "[ChromeDriver] Failed to install ChromeDriver. A current version of Chrome was not detected on your system.\\n"
            "If you know that Chrome is installed, update Chrome to the latest version. If the script is still not working, "
            "set the path to your Chrome executable manually inside the script."
        )'''

    new_create_driver = '''def create_driver():
    """Create a Chrome WebDriver with undetected_chromedriver."""

    try:
        chrome_options = get_options()
        # Explicitly specify ChromeDriver and Chrome paths for Docker
        driver = uc.Chrome(
            options=chrome_options,
            driver_executable_path="/usr/bin/chromedriver",
            browser_executable_path="/usr/bin/chromium"
        )
        print("[ChromeDriver] Installed and browser started.")
        return driver
    except Exception as e:
        print(f"[ChromeDriver] Default ChromeDriver creation failed: {e}")
        print("[ChromeDriver] Trying alternative paths...")

        chrome_path = find_chrome()
        if chrome_path:
            chrome_options = get_options()
            chrome_options.binary_location = chrome_path
            try:
                driver = uc.Chrome(
                    options=chrome_options,
                    driver_executable_path="/usr/bin/chromedriver"
                )
                print(f"[ChromeDriver] ChromeDriver started using {chrome_path}")
                return driver
            except Exception as e:
                print(f"[ChromeDriver] ChromeDriver failed using path {chrome_path}: {e}")
        else:
            print("[ChromeDriver] No Chrome executable found in known paths.")

        raise Exception(
            "[ChromeDriver] Failed to install ChromeDriver. A current version of Chrome was not detected on your system.\\n"
            "If you know that Chrome is installed, update Chrome to the latest version. If the script is still not working, "
            "set the path to your Chrome executable manually inside the script."
        )'''

    if old_create_driver in content:
        content = content.replace(old_create_driver, new_create_driver)
        print("[Patch] Added explicit ChromeDriver path.")
    else:
        print("[Patch] Warning: Could not find expected create_driver function to patch.")

    # Write the patched content
    with open(CHROME_DRIVER_PATH, 'w') as f:
        f.write(content)

    print("[Patch] Successfully patched chrome_driver.py for Chromium and headless mode.")
    return True

if __name__ == "__main__":
    patch_chrome_driver()


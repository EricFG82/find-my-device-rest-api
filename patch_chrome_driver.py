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

    # Patch 2: Add Docker-friendly options
    #
    # Deliberately NOT forcing --headless here: the in-browser VNC auth flow
    # (vnc_auth_entrypoint.py) needs a real, visible Chrome window on the
    # virtual display (DISPLAY=:99) so it can be seen/clicked through noVNC.
    # create_driver() below already falls back to --headless on its own if
    # no display is available (e.g. no DISPLAY set, or Xvfb isn't running),
    # so headless-by-necessity is still covered without hardcoding it here.
    old_options = '''def get_options():
    chrome_options = uc.ChromeOptions()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return chrome_options'''

    new_options = '''def get_options():
    chrome_options = uc.ChromeOptions()
    # Docker-friendly options
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1280,800")
    return chrome_options'''

    if old_options in content:
        content = content.replace(old_options, new_options)
        print("[Patch] Added Docker-friendly options.")
    else:
        print("[Patch] Warning: Could not find expected options to patch.")

    # Patch 3: Specify ChromeDriver/Chromium paths explicitly, instead of letting
    # undetected_chromedriver auto-detect/download a matching driver (slower,
    # depends on network access to a version-lookup endpoint). We already have
    # matching chromium + chromium-driver installed via apt at fixed versions.
    #
    # Three small, independently-anchored replacements instead of one big
    # whole-function match: create_driver() has three near-identical
    # `uc.Chrome(...)` call sites, and matching the entire function verbatim
    # is brittle against incidental upstream whitespace changes (it broke
    # once already). Each site below is anchored on its unique neighboring
    # line instead.
    create_driver_patches = [
        (
            # `pkill -f chrome` (a "kill any pre-existing Chrome first" precaution)
            # was found to hang indefinitely in some container environments -
            # reproduced directly at the shell, unrelated to "chrome" matching
            # anything. A fresh on-demand Xvfb session (the VNC auth flow) never
            # has a pre-existing Chrome to kill anyway, so this is dead weight
            # that can only hang create_driver() forever - skip it.
            '''                os.system("pkill -f chrome")''',
            '''                pass  # os.system("pkill -f chrome") removed: hangs in some environments, unneeded for a fresh Xvfb session''',
        ),
        (
            # Primary attempt (8-space indent)
            '''        driver = uc.Chrome(options=chrome_options, version_main=None)
        print("[ChromeDriver] Installed and browser started.")''',
            '''        driver = uc.Chrome(
            options=chrome_options,
            driver_executable_path="/usr/bin/chromedriver",
            browser_executable_path="/usr/bin/chromium"
        )
        print("[ChromeDriver] Installed and browser started.")''',
        ),
        (
            # find_chrome() fallback (16-space indent)
            '''                driver = uc.Chrome(options=chrome_options, version_main=None)
                print(f"[ChromeDriver] ChromeDriver started using {chrome_path}")''',
            '''                driver = uc.Chrome(
                    options=chrome_options,
                    driver_executable_path="/usr/bin/chromedriver"
                )
                print(f"[ChromeDriver] ChromeDriver started using {chrome_path}")''',
        ),
        (
            # Last-resort headless fallback (12-space indent)
            '''            chrome_options.add_argument("--headless")
            driver = uc.Chrome(options=chrome_options, version_main=None)''',
            '''            chrome_options.add_argument("--headless=new")
            driver = uc.Chrome(
                options=chrome_options,
                driver_executable_path="/usr/bin/chromedriver",
                browser_executable_path="/usr/bin/chromium"
            )''',
        ),
    ]

    create_driver_patched = 0
    for old_snippet, new_snippet in create_driver_patches:
        if old_snippet in content:
            content = content.replace(old_snippet, new_snippet)
            create_driver_patched += 1

    if create_driver_patched == len(create_driver_patches):
        print("[Patch] Added explicit ChromeDriver/Chromium paths to create_driver().")
    else:
        print(f"[Patch] Warning: Only patched {create_driver_patched}/{len(create_driver_patches)} "
              "create_driver() call sites - upstream may have changed further.")

    # Write the patched content
    with open(CHROME_DRIVER_PATH, 'w') as f:
        f.write(content)

    print("[Patch] Successfully patched chrome_driver.py for Chromium and headless mode.")
    return True

if __name__ == "__main__":
    patch_chrome_driver()


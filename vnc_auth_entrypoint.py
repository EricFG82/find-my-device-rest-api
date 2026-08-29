#!/usr/bin/env python3
"""
Runtime entrypoint for the in-browser (VNC) authentication flow.

Run with DISPLAY pointing at the Xvfb display vnc_auth_service.py started, and
GOOGLEFINDMY_HEADLESS=false so chrome_driver.py's create_driver() opens a real,
visible Chrome window instead of a headless one.

Deliberately does NOT run GoogleFindMyTools/main.py: main.py's list_devices()
has its own second interactive prompt (pick a tracker / register an ESP32)
that has nothing to do with authenticating and would block forever on this
process's detached stdin. request_device_list() alone is enough to trigger
the OAuth flow (Chrome opens, user logs in) and write secrets.json - nothing
else here needs a human.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'GoogleFindMyTools'))

from NovaApi.ListDevices.nbe_list_devices import request_device_list  # noqa: E402


def main() -> int:
    print("[VncAuth] Requesting device list to trigger the OAuth login flow...")
    try:
        result_hex = request_device_list()
    except Exception as e:
        print(f"[VncAuth] Authentication failed: {e}")
        return 1

    if not result_hex:
        print("[VncAuth] Authentication failed: no response from Google's Nova API.")
        return 1

    print("[VncAuth] Authentication succeeded.")
    return 0


if __name__ == '__main__':
    sys.exit(main())

#!/usr/bin/env python3
"""
Runtime entrypoint for the in-browser (VNC) authentication flow.

Run with DISPLAY pointing at the Xvfb display vnc_auth_service.py started, and
GOOGLEFINDMY_HEADLESS=false so chrome_driver.py's create_driver() opens a real,
visible Chrome window instead of a headless one.

Deliberately does NOT run GoogleFindMyTools/main.py: main.py's list_devices()
has its own second interactive prompt (pick a tracker / register an ESP32)
that has nothing to do with authenticating and would block forever on this
process's detached stdin.

Calls _generate_aas_token() directly instead of get_aas_token() (which only
generates a fresh token when none is cached - otherwise it silently reuses
whatever's in secrets.json even if Google has since revoked it, so a login
explicitly requested through the browser would just silently no-op). Calling
the generator directly always opens Chrome for a real login, and - crucially -
never touches the existing cached aas_token until a replacement is confirmed:
if this process gets killed partway through (session timeout, user closes the
tab, an explicit stop) the old token is simply left as it was, not wiped out.
An earlier version cleared the cache up front and only wrote the new value at
the end, which meant an aborted session could leave a previously-working
container unable to authenticate at all - worse off than before the VNC
session was ever started.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'GoogleFindMyTools'))

from Auth.aas_token_retrieval import _generate_aas_token  # noqa: E402
from Auth.token_cache import set_cached_value  # noqa: E402
from NovaApi.ListDevices.nbe_list_devices import request_device_list  # noqa: E402


def main() -> int:
    print("[VncAuth] Starting interactive login...")
    try:
        new_aas_token = _generate_aas_token()
    except Exception as e:
        print(f"[VncAuth] Login failed: {e}")
        return 1

    # Only now, with a confirmed new token in hand, replace the cached one.
    set_cached_value('aas_token', new_aas_token)
    print("[VncAuth] Login succeeded, verifying device list access...")

    try:
        result_hex = request_device_list()
    except Exception as e:
        print(f"[VncAuth] Post-login verification failed: {e}")
        return 1

    if not result_hex:
        print("[VncAuth] Post-login verification failed: no response from Google's Nova API.")
        return 1

    print("[VncAuth] Authentication succeeded.")
    return 0


if __name__ == '__main__':
    sys.exit(main())

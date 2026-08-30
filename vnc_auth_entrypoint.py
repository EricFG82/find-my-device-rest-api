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
from Auth.token_cache import set_cached_value, get_cached_value  # noqa: E402
from NovaApi.ListDevices.nbe_list_devices import request_device_list  # noqa: E402
from KeyBackup.shared_key_retrieval import get_shared_key  # noqa: E402


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

    # Decrypting a location report that came from someone else's phone (i.e.
    # any device currently out of range of your own phone - the common case)
    # needs a separate "shared key", fetched via its own Google sign-in +
    # in-page key-exchange dance (get_shared_key() only does this once; it's
    # a no-op if already cached from a previous session). This step running
    # here, in the same VNC session, is what lets it use the real, visible
    # Chrome window - triggering it later from the main API process would
    # have nowhere to show the login (see the guard in device_service.py).
    # Treated as non-fatal: the basic device list already verified above, so
    # a failure/skip here shouldn't fail the whole login - it just means
    # locations from other people's phones won't decrypt until this succeeds.
    if get_cached_value('shared_key') is not None:
        print("[VncAuth] Shared key (for decrypting other-phone location reports) already set up.")
    else:
        print("[VncAuth] Setting up the shared key needed to decrypt location reports that "
              "come from other people's phones (e.g. any device currently out of range of "
              "your own) - this needs signing in to Google a second time, in the same window.")
        try:
            get_shared_key()
            print("[VncAuth] Shared key set up successfully.")
        except Exception as e:
            print(f"[VncAuth] Could not set up the shared key: {e}")
            print("[VncAuth] Continuing anyway - devices in range of your own phone will still "
                  "work; retry this login later to enable the rest.")

    return 0


if __name__ == '__main__':
    sys.exit(main())

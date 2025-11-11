#!/usr/bin/env python3
"""
Patch script to fix fcm_receiver.py to be async-compatible.

The original fcm_receiver.py uses asyncio.get_event_loop().run_until_complete()
which doesn't work when there's already an event loop running (like in FastAPI).

This patch makes the methods properly async.
"""

import sys

def patch_fcm_receiver():
    """Patch the fcm_receiver.py file to make it async-compatible"""

    file_path = '/app/GoogleFindMyTools/Auth/fcm_receiver.py'

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        # Check if already patched
        if 'async def register_for_location_updates' in content:
            print(f"✓ {file_path} is already patched")
            return True

        print(f"Patching {file_path}...")

        # Try to patch the NEW version (with _start_listener_in_background)
        old_register_new = '''    def register_for_location_updates(self, callback):

        if not self._listening:
            self._start_listener_in_background()

        self.location_update_callbacks.append(callback)

        return self.credentials['fcm']['registration']['token']'''

        new_register_new = '''    async def register_for_location_updates(self, callback):

        if not self._listening:
            await self._register_for_fcm_and_listen()

        self.location_update_callbacks.append(callback)

        return self.credentials['fcm']['registration']['token']'''

        if old_register_new in content:
            print("Found NEW version of register_for_location_updates, patching...")
            content = content.replace(old_register_new, new_register_new)
        else:
            # Try the OLD version
            old_register = '''    def register_for_location_updates(self, callback):

        if not self._listening:
            asyncio.get_event_loop().run_until_complete(self._register_for_fcm_and_listen())

        self.location_update_callbacks.append(callback)

        return self.credentials['fcm']['registration']['token']'''

            new_register = '''    async def register_for_location_updates(self, callback):

        if not self._listening:
            await self._register_for_fcm_and_listen()

        self.location_update_callbacks.append(callback)

        return self.credentials['fcm']['registration']['token']'''

            if old_register in content:
                print("Found OLD version of register_for_location_updates, patching...")
                content = content.replace(old_register, new_register)
            else:
                print("WARNING: Could not find the expected code to patch in register_for_location_updates")
                print("  The code may have already been updated in the repository.")

        # Replace the synchronous stop_listening with async version (NEW version)
        old_stop_new = '''    def stop_listening(self):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self.pc.stop(), self._loop)
        self._listening = False'''

        new_stop_new = '''    async def stop_listening(self):
        await self.pc.stop()
        self._listening = False'''

        if old_stop_new in content:
            print("Found NEW version of stop_listening, patching...")
            content = content.replace(old_stop_new, new_stop_new)
        else:
            # Try the OLD version
            old_stop = '''    def stop_listening(self):
        asyncio.get_event_loop().run_until_complete(self.pc.stop())
        self._listening = False'''

            new_stop = '''    async def stop_listening(self):
        await self.pc.stop()
        self._listening = False'''

            if old_stop in content:
                print("Found OLD version of stop_listening, patching...")
                content = content.replace(old_stop, new_stop)
            else:
                print("WARNING: Could not find the expected code to patch in stop_listening")
                print("  The code may have already been updated in the repository.")

        # Replace the synchronous get_android_id with async version (NEW version)
        old_get_android_new = '''    def get_android_id(self):

        if self.credentials is None:
            return self._start_listener_in_background()

        return self.credentials['gcm']['android_id']'''

        new_get_android_new = '''    async def get_android_id(self):

        if self.credentials is None:
            await self._register_for_fcm_and_listen()

        return self.credentials['gcm']['android_id']'''

        if old_get_android_new in content:
            print("Found NEW version of get_android_id, patching...")
            content = content.replace(old_get_android_new, new_get_android_new)
        else:
            # Try the OLD version
            old_get_android = '''    def get_android_id(self):

        if self.credentials is None:
            return asyncio.get_event_loop().run_until_complete(self._register_for_fcm_and_listen())

        return self.credentials['gcm']['android_id']'''

            new_get_android = '''    async def get_android_id(self):

        if self.credentials is None:
            await self._register_for_fcm_and_listen()

        return self.credentials['gcm']['android_id']'''

            if old_get_android in content:
                print("Found OLD version of get_android_id, patching...")
                content = content.replace(old_get_android, new_get_android)
            else:
                print("WARNING: Could not find the expected code to patch in get_android_id")
                print("  The code may have already been updated in the repository.")

        # Write the patched content back
        with open(file_path, 'w') as f:
            f.write(content)

        print(f"✓ Patch process completed for {file_path}")
        return True

    except FileNotFoundError:
        print(f"ERROR: File not found: {file_path}")
        return False
    except Exception as e:
        print(f"ERROR: Failed to patch file: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = patch_fcm_receiver()
    sys.exit(0 if success else 1)


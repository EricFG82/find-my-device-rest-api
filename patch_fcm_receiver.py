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
        
        # Replace the synchronous register_for_location_updates with async version
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
        
        if old_register not in content:
            print("ERROR: Could not find the expected code to patch in register_for_location_updates")
            return False
        
        content = content.replace(old_register, new_register)
        
        # Replace the synchronous stop_listening with async version
        old_stop = '''    def stop_listening(self):
        asyncio.get_event_loop().run_until_complete(self.pc.stop())
        self._listening = False'''
        
        new_stop = '''    async def stop_listening(self):
        await self.pc.stop()
        self._listening = False'''
        
        if old_stop not in content:
            print("ERROR: Could not find the expected code to patch in stop_listening")
            return False
        
        content = content.replace(old_stop, new_stop)
        
        # Replace the synchronous get_android_id with async version
        old_get_android = '''    def get_android_id(self):

        if self.credentials is None:
            return asyncio.get_event_loop().run_until_complete(self._register_for_fcm_and_listen())

        return self.credentials['gcm']['android_id']'''
        
        new_get_android = '''    async def get_android_id(self):

        if self.credentials is None:
            await self._register_for_fcm_and_listen()

        return self.credentials['gcm']['android_id']'''
        
        if old_get_android not in content:
            print("ERROR: Could not find the expected code to patch in get_android_id")
            return False
        
        content = content.replace(old_get_android, new_get_android)
        
        # Write the patched content back
        with open(file_path, 'w') as f:
            f.write(content)
        
        print(f"✓ Successfully patched {file_path}")
        print("  - register_for_location_updates() is now async")
        print("  - stop_listening() is now async")
        print("  - get_android_id() is now async")
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


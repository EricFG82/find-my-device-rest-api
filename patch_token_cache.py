#!/usr/bin/env python3
"""
Patch script to make token_cache.py tolerate an existing-but-empty
secrets.json.

set_cached_value() raises "Could not read secrets file. Aborting." whenever
secrets.json exists but isn't valid JSON - which includes a brand new empty
file, not just a genuinely corrupt one. That's exactly the state
AUTHENTICATION.md tells users to create before their first start
(`touch auth_data/secrets.json`, so Docker mounts a file instead of an empty
directory) - so following our own documented setup broke the very first
Method 3 (VNC) login attempt. get_cached_value() already treats invalid JSON
as "no value yet" (returns None); set_cached_value() now does the same
(treats it as an empty dict to write into), matching the missing-file case
right below it.
"""

import sys

def patch_token_cache():
    """Patch token_cache.py to treat empty/invalid secrets.json as empty, not fatal."""

    file_path = '/app/GoogleFindMyTools/Auth/token_cache.py'

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        old_snippet = '''    if os.path.exists(secrets_file):
        with open(secrets_file, 'r') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                raise Exception("Could not read secrets file. Aborting.")
    else:
        data = {}'''

        new_snippet = '''    if os.path.exists(secrets_file):
        with open(secrets_file, 'r') as file:
            try:
                data = json.load(file)
            except json.JSONDecodeError:
                # A brand new file (e.g. `touch`'d before the first start, per
                # AUTHENTICATION.md) is empty, not corrupt - treat it the same
                # as a missing file instead of aborting.
                data = {}
    else:
        data = {}'''

        if new_snippet in content:
            print(f"✓ {file_path} is already patched")
            return True

        if old_snippet in content:
            content = content.replace(old_snippet, new_snippet)
        else:
            print("WARNING: Could not find the expected code to patch in token_cache.py")
            print("  The code may have already been updated in the repository.")
            return False

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
    success = patch_token_cache()
    sys.exit(0 if success else 1)

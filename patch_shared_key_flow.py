#!/usr/bin/env python3
"""
Patch script to remove the blocking input() prompt from
KeyBackup/shared_key_retrieval.py.

_retrieve_shared_key() calls input("Press 'Enter' to continue...") before
opening Chrome for a second Google sign-in (needed to decrypt location
reports that come from someone else's phone - see vnc_auth_entrypoint.py,
which now triggers this in the same VNC session as the main login). Same
class of bug as auth_flow.py's original one: fine at a real terminal, but
hangs forever (EOFError on a detached stdin) when triggered programmatically.
The printed explanation above it is still useful (shows up in the container
logs / VNC session), so only the blocking input() call itself is removed.
"""

import sys

def patch_shared_key_flow():
    """Patch shared_key_retrieval.py to not block on stdin before opening Chrome."""

    file_path = '/app/GoogleFindMyTools/KeyBackup/shared_key_retrieval.py'

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        old_prompt = '''    # Press enter to continue
    input("[SharedKeyRetrieval] Press 'Enter' to continue...")'''

        new_prompt = '''    # Press enter to continue (skipped: this may run without an attached
    # terminal, e.g. triggered via the in-browser VNC auth flow)'''

        if new_prompt in content:
            print(f"✓ {file_path} is already patched")
            return True

        if old_prompt in content:
            content = content.replace(old_prompt, new_prompt)
        else:
            print("WARNING: Could not find the expected input() prompt to patch in shared_key_retrieval.py")
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
    success = patch_shared_key_flow()
    sys.exit(0 if success else 1)

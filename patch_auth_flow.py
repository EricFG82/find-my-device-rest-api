#!/usr/bin/env python3
"""
Patch script to remove the blocking input() prompt from auth_flow.py.

request_oauth_account_token_flow() calls input("Press Enter to continue...")
before opening Chrome. That's fine when a human is running main.py at a real
terminal, but it hangs forever (EOFError on a detached stdin) when the OAuth
flow is triggered programmatically - which is exactly what the in-browser VNC
auth flow does (see vnc_auth_entrypoint.py). The printed instructions above it
are still useful (they show up in the container logs), so only the blocking
input() call itself is removed.
"""

import sys

def patch_auth_flow():
    """Patch auth_flow.py to not block on stdin before opening Chrome."""

    file_path = '/app/GoogleFindMyTools/Auth/auth_flow.py'

    try:
        with open(file_path, 'r') as f:
            content = f.read()

        old_prompt = '''    # Press enter to continue
    input("[AuthFlow] Press Enter to continue...")'''

        new_prompt = '''    # Press enter to continue (skipped: this may run without an attached
    # terminal, e.g. triggered via the in-browser VNC auth flow)'''

        if new_prompt in content:
            print(f"✓ {file_path} is already patched")
            return True

        if old_prompt in content:
            content = content.replace(old_prompt, new_prompt)
        else:
            print("WARNING: Could not find the expected input() prompt to patch in auth_flow.py")
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
    success = patch_auth_flow()
    sys.exit(0 if success else 1)

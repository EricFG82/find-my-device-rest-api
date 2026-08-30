"""
In-browser (VNC) authentication service.

Spins up a virtual display (Xvfb) + window manager (Openbox) + VNC server
(x11vnc) + noVNC web bridge (websockify) on demand, then runs
vnc_auth_entrypoint.py against that display so a user can complete Google's
interactive OAuth login (CAPTCHA/2FA included) through a browser tab, without
a local Chrome install. See AUTHENTICATION.md ("Method 3").

Unlike an always-on VNC desktop, this whole stack only runs while a login is
actually in progress: start() launches it, and it's torn down on success,
failure, explicit stop(), or the session timeout.
"""

import asyncio
import logging
import os
import secrets
import signal
import sys
from datetime import datetime, timezone
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'GoogleFindMyTools'))

logger = logging.getLogger(__name__)

DISPLAY = ":99"
VNC_PORT = 5900
NOVNC_PORT = 6080
# Outer safety net. The session can now involve two sequential sign-ins
# (see vnc_auth_entrypoint.py) - the main login and, if not already cached,
# the shared-key login needed to decrypt other-phone location reports -
# each with its own 300s cookie-wait timeout in the underlying library
# (Auth/auth_flow.py, KeyBackup/shared_key_flow.py). This just guarantees
# cleanup with some margin past both.
SESSION_TIMEOUT_SECONDS = 900


class VncAuthService:
    """Manages the on-demand Xvfb/x11vnc/websockify/Chrome stack for browser-based auth."""

    def __init__(self, on_success=None):
        """on_success: optional async callback invoked (fire-and-forget) once
        authentication succeeds - e.g. to re-initialize DeviceService so the
        already-running app picks up the new secrets.json without a restart."""
        self.state = "idle"  # idle | running | succeeded | failed
        self.error: Optional[str] = None
        self.password: Optional[str] = None
        self.started_at: Optional[datetime] = None

        self._on_success = on_success
        self._processes: list = []  # all subprocesses, in start order
        self._entrypoint_process = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self) -> dict:
        """Start a new VNC auth session. Raises RuntimeError if one is already running."""
        async with self._lock:
            if self.state == "running":
                raise RuntimeError("A VNC authentication session is already running")

            self.state = "running"
            self.error = None
            # Classic VNC auth (x11vnc -passwd) caps passwords at 8 characters.
            self.password = secrets.token_urlsafe(8)[:8]
            self.started_at = datetime.now(timezone.utc)
            self._processes = []
            self._entrypoint_process = None

            try:
                await self._spawn_stack()
            except Exception as e:
                logger.error(f"Failed to start VNC auth stack: {e}", exc_info=True)
                self.state = "failed"
                self.error = str(e)
                await self._cleanup()
                raise

            self._watchdog_task = asyncio.create_task(self._watchdog())

            return {
                "password": self.password,
                "novnc_port": NOVNC_PORT,
                "expires_in_seconds": SESSION_TIMEOUT_SECONDS,
            }

    async def _spawn_stack(self):
        env = os.environ.copy()
        env["DISPLAY"] = DISPLAY

        xvfb = await asyncio.create_subprocess_exec(
            "Xvfb", DISPLAY, "-screen", "0", "1280x800x24",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        self._processes.append(xvfb)
        await self._wait_for_x_display()

        openbox = await asyncio.create_subprocess_exec(
            "openbox", "--config-file", "/app/openbox-rc.xml",
            env=env,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        self._processes.append(openbox)

        x11vnc = await asyncio.create_subprocess_exec(
            "x11vnc", "-display", DISPLAY, "-passwd", self.password,
            "-forever", "-shared", "-rfbport", str(VNC_PORT), "-quiet",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        self._processes.append(x11vnc)
        # Give x11vnc a moment to bind its port before websockify connects to it.
        await asyncio.sleep(1)

        websockify = await asyncio.create_subprocess_exec(
            "websockify", "--web=/usr/share/novnc", str(NOVNC_PORT), f"localhost:{VNC_PORT}",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        self._processes.append(websockify)

        entrypoint_env = env.copy()
        entrypoint_env["GOOGLEFINDMY_HEADLESS"] = "false"
        self._entrypoint_process = await asyncio.create_subprocess_exec(
            "python3", "/app/vnc_auth_entrypoint.py",
            env=entrypoint_env,
            start_new_session=True,
        )
        self._processes.append(self._entrypoint_process)
        self._monitor_task = asyncio.create_task(self._monitor_entrypoint())

    async def _wait_for_x_display(self, timeout: float = 10.0):
        socket_path = f"/tmp/.X11-unix/X{DISPLAY.lstrip(':')}"
        elapsed = 0.0
        while not os.path.exists(socket_path) and elapsed < timeout:
            await asyncio.sleep(0.2)
            elapsed += 0.2
        if not os.path.exists(socket_path):
            raise RuntimeError("Xvfb did not create its display socket in time")

    async def _monitor_entrypoint(self):
        """Waits for the auth process to exit and records the outcome. Only
        touches self.state (a terminal success/failure), never resets to idle -
        that's stop()'s job."""
        try:
            returncode = await self._entrypoint_process.wait()
        except asyncio.CancelledError:
            return

        if self.state != "running":
            return  # stop() or the watchdog already handled this session

        if returncode == 0:
            self.state = "succeeded"
            logger.info("VNC authentication succeeded")
            if self._on_success:
                # Fire-and-forget: don't let a slow/failing callback delay
                # cleanup, and don't let it flip this session's own state.
                asyncio.create_task(self._run_on_success())
        else:
            self.state = "failed"
            self.error = f"Authentication process exited with code {returncode}"
            logger.warning(self.error)

        await self._cleanup()

    async def _run_on_success(self):
        try:
            await self._on_success()
        except Exception as e:
            logger.error(f"on_success callback failed: {e}", exc_info=True)

    async def _watchdog(self):
        try:
            await asyncio.sleep(SESSION_TIMEOUT_SECONDS)
        except asyncio.CancelledError:
            return

        if self.state == "running":
            logger.warning("VNC authentication session timed out")
            self.state = "failed"
            self.error = "Session timed out"
            await self._cleanup()

    async def status(self) -> dict:
        try:
            from Auth.username_provider import get_username
            authenticated = bool(get_username())
        except Exception:
            authenticated = False

        return {
            "state": self.state,
            "error": self.error,
            "authenticated": authenticated,
        }

    async def stop(self):
        """Explicitly tear down a running (or already-finished) session.

        Resets state to idle only if a session was actually running - if it
        already finished (succeeded/failed) on its own, that outcome is left
        in place for status() to report.
        """
        async with self._lock:
            if self.state == "running":
                self.state = "idle"
                self.error = None
            await self._cleanup()

    async def _cleanup(self):
        """Kill all spawned processes (and their children) in reverse start order.

        Each process is started with start_new_session=True, making it the
        leader of its own process group (pgid == pid). Signaling just the
        tracked PID isn't enough for the entrypoint process in particular:
        killing the vnc_auth_entrypoint.py Python process doesn't cascade to
        chromedriver/chromium, which Selenium spawns as its own children - they'd
        be orphaned as zombies otherwise. Signaling the whole group fixes that.
        Safe to call repeatedly.
        """
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
        if (
            self._monitor_task
            and not self._monitor_task.done()
            and asyncio.current_task() is not self._monitor_task
        ):
            self._monitor_task.cancel()

        for proc in reversed(self._processes):
            if proc.returncode is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass

        for proc in reversed(self._processes):
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5)
                except asyncio.TimeoutError:
                    pass
            except ProcessLookupError:
                pass

        self._processes = []
        self._entrypoint_process = None

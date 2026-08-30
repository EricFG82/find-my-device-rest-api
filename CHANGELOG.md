# Changelog

All notable changes to this project will be documented in this file.

## [1.2.4] - 2026-08-30

### Fixed

- `secrets.json` existing as an empty file (exactly the state
  `touch auth_data/secrets.json` creates, per this doc's own Docker
  file-mount workaround) made the very first Method 3 (VNC) login fail
  with "Could not read secrets file. Aborting." - upstream's
  `set_cached_value()` treated invalid JSON as fatal instead of just empty,
  unlike its own `get_cached_value()` right above it. Patched to match.
- Location reports from *other* people's phones (i.e. any device currently
  out of range of your own - the common case this project exists for)
  could never decrypt: doing so needs a "shared key" obtained through a
  second, separate Google sign-in, which had no support at all - the
  underlying library's prompt for it hit the same blocking-`input()`
  problem `auth_flow.py` had before, and even patched away, that second
  login had nowhere to run (it needs a real display, and only the VNC
  login process has one). The VNC login flow (`vnc_auth_entrypoint.py`)
  now triggers this second sign-in itself, in the same browser session,
  right after the main login succeeds - see AUTHENTICATION.md. A device
  fetch that needs this key before it's been set up now fails fast with a
  clear message instead of attempting (and failing, since it can't
  actually show a login prompt there) from the main API process.
- Bumped the VNC session timeout (600s → 900s) to comfortably fit two
  sequential sign-ins instead of one.

## [1.2.3] - 2026-08-30

### Added

- `GET /api/v1/devices/{device_id}` now accepts `?force=true` to actively
  request a fresh location from Google instead of the background task's
  cache (takes up to ~30s). Not meant for routine polling - only for an
  explicit, user-triggered "locate now" action.

### Fixed

- The background location update cycle processed devices one at a time, so
  with several devices, some could go stale for much longer than
  `LOCATION_UPDATE_INTERVAL` (up to ~32s of the cycle per device ahead of
  them, on top of any that hit the 30s FCM timeout). Devices are now
  fetched concurrently, so a cycle takes as long as the single slowest
  device instead of the sum of all of them.
- Guarded the FCM connect/register step with a lock so concurrent fetches
  can't re-trigger the race this project's TECHNICAL_FIX.md already
  documents (multiple simultaneous callers all seeing `_listening=False`
  and opening duplicate MCS connections) - only that fast step is
  serialized, not the actual per-device wait for a location response.
- The location cache's freshness check was hardcoded to 300 seconds
  regardless of `LOCATION_UPDATE_INTERVAL` - now follows the configured
  value.

## [1.2.2] - 2026-08-29

### Changed

- Repo renamed from `google-find-my-device-rest-api` to
  `find-my-device-rest-api`; the Docker image moved to
  `ericfg82/find-my-device-rest-api` to match. No functional changes -
  drops "Google" from the project's own naming (repo, image, service
  title/logs) as a trademark-safety precaution; references to the actual
  Google Find My Device service/API being wrapped are unaffected.

## [1.2.1] - 2026-08-29

### Changed

- Repo renamed from `google-findmy-api` to `google-find-my-device-rest-api`;
  the Docker image moved to `ericfg82/google-find-my-device-rest-api` (now
  public, matching the repo) to go with it. No functional changes.

## [1.2.0] - 2026-08-29

### Added

- In-browser authentication ("Method 3") - `POST /auth/vnc/start`,
  `GET /auth/vnc/status`, `POST /auth/vnc/stop`. Spins up a virtual display
  (Xvfb), a real (non-headless) Chrome, and a noVNC web bridge on demand, so a
  full interactive Google login (CAPTCHA/2FA included) can be completed from
  any browser, without a local Chrome install or copying `secrets.json`
  around. See `AUTHENTICATION.md`.
- The running service picks up a successful VNC login
  immediately - if it started without valid credentials, it re-initializes
  itself as soon as login succeeds, no container restart needed. (Left alone
  if it was already authenticated, to avoid starting a second background
  location updater.)

### Fixed

- `KeyError: 'Auth'` (Google rejecting a revoked/expired token)
  surfaced as a bare, confusing exception in both the device-list and
  location-fetch paths. Now raises a clear message pointing at
  re-authenticating.
- A request to `/api/v1/devices` (or the background location
  updater) made while a VNC login was in progress used to independently
  trigger its own unattended, un-completable headless login attempt and hang
  for up to 5 minutes. Now returns `409` immediately instead.
- The VNC login flow used to unconditionally clear the cached
  auth token before every attempt, so an aborted or interrupted session (tab
  closed, session timeout, explicit stop) could leave a previously-working
  container unable to authenticate at all. The old token is now only replaced
  once a new one is confirmed working.
- `patch_chrome_driver.py` no longer matched the current
  upstream `chrome_driver.py` (library drift) - two of its three patches were
  silently no-ops. Rewritten with smaller, more resilient anchors.
- `pkill -f chrome` (a "kill stale Chrome" precaution in
  upstream's `create_driver()`) was found to hang indefinitely in this
  container environment, unrelated to matching anything - removed, since a
  fresh on-demand Xvfb session never has a stale Chrome to kill anyway.
- Orphaned `chromedriver`/`chromium` processes from the VNC flow
  weren't being reaped (the app runs as PID 1, which must reap re-parented
  orphans itself) - added `tini` as the real PID 1.
- `/health`'s unhealthy message and `/`'s endpoint list now
  mention the VNC login option; the VNC-driven Chrome window is maximized and
  undecorated (fills the whole noVNC view); `noVNC`'s bare web root now serves
  `vnc.html` instead of a directory listing.

## [1.1.1] - 2026-08-29

### Fixed

- The `/` root endpoint and the OpenAPI docs (`/docs`) reported a
  hardcoded `"version": "1.0.0"` regardless of the actual image tag being run.
  The version is now injected at build time via `--build-arg APP_VERSION` (set
  automatically from the git tag by `build-and-push.sh` and the GitHub Actions
  workflow) and read from the `APP_VERSION` env var at runtime, so it always
  matches the published image tag.

## [1.1.0] - 2026-08-28

### Fixed

- Fixed a race in the patched FCM receiver (`patch_fcm_receiver.py`) where
  `_listening` was never set to `True` after connecting, causing a new MCS connection to
  be opened for every single device on every background location update cycle. This led
  to overlapping listener tasks, `readexactly()` race errors, and location requests
  timing out for whichever device was in flight when the connection collapsed.
- `/api/v1/devices` no longer crashes with a confusing
  `fromhex() argument must be str, not None` when Google's Nova API rejects a request
  (e.g. expired/revoked auth token). It now raises a clear, actionable error instead.
- `/health` no longer reports `200 healthy` when authentication isn't
  actually configured. `get_username()` can silently return an empty string instead of
  raising, so a missing/invalid `secrets.json` used to pass as "verified". `/health` now
  returns `503` with a `{"status": "unhealthy", "message": "..."}` body describing the
  real cause, and the app no longer crash-loops on a failed startup so the reason stays
  visible.
- **build-and-push.sh**: New script to build and push the Docker image without
  ever baking `secrets.json` into it (temporarily set aside during the build, restored
  after). Also disables buildx provenance/SBOM attestations (`--provenance=false
  --sbom=false`), since the attestation manifest they add was preventing Synology
  Container Manager from detecting new image versions.
- **docker-compose.portainer.yml**: New compose file for Portainer deployments
  that pulls the published image (`image:`) instead of building from source, with
  `secrets.json` mounted from the NAS filesystem rather than baked into the image.

## [1.0.2] - 2025-10-30

### Fixed

- **Dockerfile**: Replaced Google Chrome with Chromium for ARM64 compatibility
  - Issue: Google Chrome only provides amd64 packages, causing build failures on Apple Silicon Macs
  - Solution: Use Chromium which supports both amd64 and arm64 architectures
  - Impact: Docker build now works on Apple Silicon (M1/M2/M3) and Intel Macs
  - Added environment variables: `CHROME_BIN` and `CHROMEDRIVER_PATH`

## [1.0.1] - 2025-10-30

### Fixed

- **Dockerfile**: Fixed Google Chrome installation by replacing deprecated `apt-key` with modern GPG keyring method

  - Issue: `apt-key` command is no longer available in newer Debian/Ubuntu versions
  - Solution: Use `gpg --dearmor` and signed-by in sources.list
  - Impact: Docker build now works on all modern systems

- **docker-compose.yml**: Removed obsolete `version` attribute
  - Issue: Docker Compose v2 shows warning about obsolete version attribute
  - Solution: Removed `version: '3.8'` line
  - Impact: No more warnings during build/run

## [1.0.0] - 2025-10-30

### Added

- Initial release of the REST API service
  - GET /api/v1/devices - List all devices
  - GET /api/v1/devices/{device_id} - Get device details
  - GET /health - Health check endpoint
  - Automatic API documentation (Swagger/ReDoc)
  - 60-second intelligent caching
  - Docker containerization
- Deployment Files
  - Dockerfile with health checks
  - docker-compose.yml for easy deployment
  - test_api.sh for API testing
  - .env.example for configuration
- License
  - GPL-3.0 license (matching GoogleFindMyTools)

### Technical Details

- Python 3.11+ with FastAPI
- Pydantic for data validation
- Async/await patterns throughout
- Thread pool executor for blocking calls
- Proper error handling and logging

---

## Version History

- **1.2.0** (2026-08-29) - In-browser (VNC) authentication
- **1.1.1** (2026-08-29) - Report actual image version
- **1.1.0** (2026-08-28) - FCM async fix, health check fix, Portainer compose
- **1.0.2** (2025-10-30) - ARM64/Apple Silicon compatibility fix
- **1.0.1** (2025-10-30) - Docker build fixes
- **1.0.0** (2025-10-30) - Initial release

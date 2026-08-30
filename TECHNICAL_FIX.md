# Technical Fix: FCM Receiver Async Compatibility

> **Update**: The fix described below (making `fcm_receiver.py` async) was correct
> but incomplete - it dropped the `self._listening = True` state update that the
> original sync code had, so the receiver reconnected to MCS on *every* location
> request instead of reusing one connection. See the "Follow-up fix" section at the
> end of this document.

## Problem Statement

The Find My Device REST API service was crashing on Synology NAS (and potentially other Docker environments) with the following error:

```
RuntimeError: There is no current event loop in thread 'ThreadPoolExecutor_0_0'
```

## Root Cause Analysis

### The Real Problem

The issue was **NOT** with Docker, Synology NAS, or the REST API service itself. The problem was in the upstream `GoogleFindMyTools` library, specifically in `/GoogleFindMyTools/Auth/fcm_receiver.py`.

### Technical Details

The `FcmReceiver` class had synchronous methods that internally called `asyncio.get_event_loop().run_until_complete()`:

```python
# PROBLEMATIC CODE (original)
def register_for_location_updates(self, callback):
    if not self._listening:
        asyncio.get_event_loop().run_until_complete(self._register_for_fcm_and_listen())
    
    self.location_update_callbacks.append(callback)
    return self.credentials['fcm']['registration']['token']
```

### Why This Failed

This is an **anti-pattern** that fails when:

1. **An event loop is already running** - FastAPI runs its own asyncio event loop
2. **Code is executed in a thread pool** - The error message mentions `ThreadPoolExecutor_0_0`
3. **Nested event loops are not supported** - You cannot call `run_until_complete()` from within an already-running event loop

The error manifested more frequently on Synology NAS due to how Docker containers are managed in that environment, but it was a fundamental async/await compatibility issue.

## The Solution

### Proper Fix (Not a Workaround)

Instead of disabling location updates or catching errors, we **fixed the root cause** by patching the library to use proper async/await patterns.

### Implementation

#### 1. Created `patch_fcm_receiver.py`

A patch script that modifies the GoogleFindMyTools library during Docker build:

```python
def patch_fcm_receiver():
    """Patch the fcm_receiver.py file to make it async-compatible"""
    
    file_path = '/app/GoogleFindMyTools/Auth/fcm_receiver.py'
    
    # Convert synchronous method to async
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
    
    # Apply the patch...
```

The patch converts three methods:
- `register_for_location_updates()` → `async def register_for_location_updates()`
- `stop_listening()` → `async def stop_listening()`
- `get_android_id()` → `async def get_android_id()`

#### 2. Updated `Dockerfile`

Applied the patch during Docker build:

```dockerfile
# Clone GoogleFindMyTools repository
RUN git clone https://github.com/leonboe1/GoogleFindMyTools.git /app/GoogleFindMyTools

# Copy patch scripts and apply them
COPY patch_chrome_driver.py /app/
COPY patch_fcm_receiver.py /app/
RUN python3 /app/patch_chrome_driver.py && \
    python3 /app/patch_fcm_receiver.py
```

#### 3. Updated `device_service.py`

Changed to properly await the async methods:

```python
# OLD (caused crashes):
fcm_token = self._fcm_receiver.register_for_location_updates(handle_location_response)

# NEW (proper async):
fcm_token = await self._fcm_receiver.register_for_location_updates(handle_location_response)
```

```python
# OLD (caused crashes):
self._fcm_receiver.stop_listening()

# NEW (proper async):
await self._fcm_receiver.stop_listening()
```

## Results

### Before the Fix

- ❌ Service crashed on Synology NAS with event loop errors
- ❌ Location updates disabled as a workaround
- ❌ Reduced functionality
- ❌ User frustration

### After the Fix

- ✅ Service runs stably on all platforms (Mac, Linux, Synology NAS)
- ✅ All 5 test devices received location updates successfully
- ✅ No event loop errors
- ✅ Full functionality working
- ✅ Proper async/await implementation

### Test Results

```bash
2025-10-31 00:14:25 - INFO - Starting background location update cycle...
2025-10-31 00:14:36 - INFO - Updated location for device Xiaomi Mi 10 lite 5G
2025-10-31 00:14:39 - INFO - Updated location for device Llaves Casa
2025-10-31 00:14:42 - INFO - Updated location for device Pipa
2025-10-31 00:14:45 - INFO - Updated location for device Triumph Street Triple
2025-10-31 00:14:48 - INFO - Updated location for device Ford Focus
2025-10-31 00:14:50 - INFO - Background location update cycle complete
```

All devices now have:
- ✅ Real-time location data (latitude, longitude, accuracy)
- ✅ Last seen timestamps
- ✅ Device metadata (model, image URL, etc.)
- ✅ Automatic updates every 5 minutes

## Backward Compatibility

The `ENABLE_LOCATION_UPDATES` environment variable is still available for users who want to disable location updates for other reasons (e.g., reduce network usage), but it's no longer necessary for stability.

## Lessons Learned

1. **Always investigate root causes** - Workarounds mask problems, proper fixes solve them
2. **Async/await patterns matter** - Mixing sync and async code leads to subtle bugs
3. **Event loop management is critical** - Never call `run_until_complete()` from within an event loop
4. **Patching dependencies is acceptable** - When upstream libraries have issues, patching during build is a valid solution
5. **Test in target environments** - Issues may manifest differently in different Docker environments

## Future Considerations

### Upstream Fix

Consider submitting a pull request to the GoogleFindMyTools repository to fix the async compatibility issue upstream. This would benefit all users of the library.

### Alternative Approaches

If the patch becomes problematic in the future, alternative approaches include:

1. **Fork the library** - Maintain a fork with the async fixes
2. **Wrapper class** - Create an async wrapper around the synchronous methods
3. **Thread pool executor** - Run synchronous methods in a thread pool (less efficient)

However, the current patch approach is clean, maintainable, and works perfectly.

## Conclusion

The "Synology NAS crash" was actually a fundamental async/await compatibility issue in the GoogleFindMyTools library. By patching the library to use proper async patterns, we've created a robust solution that works in all environments.

**The service is now production-ready for deployment on any platform, including Synology NAS!** 🚀

## Follow-up fix (v1.1.0): `_listening` was never set to `True`

The patch above converted `register_for_location_updates()` to:

```python
async def register_for_location_updates(self, callback):
    if not self._listening:
        await self._register_for_fcm_and_listen()

    self.location_update_callbacks.append(callback)
    return self.credentials['fcm']['registration']['token']
```

The **original** sync version set `self._listening = True` after connecting (inside
`_start_listener_in_background()`, which the async rewrite stopped calling). The
patch never added that assignment back anywhere. Since `self._listening` stayed
`False` forever, `if not self._listening` was always true, so **every single
location request** - not just the first - called `_register_for_fcm_and_listen()`
again, opening a brand new MCS connection and a new `_listen()` task on top of the
previous one (`FcmPushClient.start()` overwrites `self.tasks` without cancelling
what was there before).

With multiple devices in one background update cycle, this reliably produced:
- Repeated `Successfully logged in to MCS endpoint` (once per device instead of once
  per cycle)
- `Task was destroyed but it is pending!` warnings (the orphaned previous task)
- `readexactly() called while another coroutine is already waiting for incoming
  data, shutting down FcmPushClient` (two `_listen()` tasks racing on the same
  socket reader)
- Whichever device's request was in flight when that happened would time out with
  no location, even though the request itself was otherwise fine

**Fix**: add `self._listening = True` right after `await
self._register_for_fcm_and_listen()` in both `register_for_location_updates()` and
`get_android_id()`, in `patch_fcm_receiver.py`. Verified afterward: a full
background update cycle across 6 real devices now does exactly one MCS login, zero
task/race warnings, and all 6 locations update successfully.


```json
{
  "issues": [
    {
      "severity": "critical",
      "category": "logic",
      "location": "frontend/src/components/MobilePanel.jsx:35-40",
      "description": "The logic `setData({ ...ios.data, ...android.data })` used to merge mobile rankings will cause immediate data loss. Since both the iOS and Android API responses return objects with identical keys ('free' and 'grossing'), the Android data will overwrite the iOS data in the state object. This ensures the iOS ranking tab will appear empty or contain Android data.",
      "suggestion": "Store the platforms under distinct keys: `setData({ ios: ios.data, android: android.data })` and update the `getItems` function accordingly."
    },
    {
      "severity": "high",
      "category": "error-handling",
      "location": "backend/main.py:64-79",
      "description": "The global exception handler `@app.exception_handler(Exception)` is too broad. In FastAPI, this catches all exceptions including `RequestValidationError` (422) and `HTTPException` (404, 401). By returning a generic 500 error for everything, it masks legitimate client errors and breaks standard REST behavior (e.g., returning 500 instead of 404 for missing routes).",
      "suggestion": "Check the exception type within the handler and re-raise if it is an instance of `Starlette.exceptions.HTTPException` or `FastAPI.exceptions.RequestValidationError`, or use a more specific exception class."
    },
    {
      "severity": "medium",
      "category": "performance",
      "location": "backend/main.py:243-243",
      "description": "The endpoint calls `weekly_digest_scraper._load_cache()`, which performs synchronous file I/O (`with open(...) as f` and `json.load`) inside an `async` function. This blocks the entire FastAPI event loop for the duration of the disk read, preventing the server from handling other concurrent requests.",
      "suggestion": "Use `asyncio.to_thread(weekly_digest_scraper._load_cache)` or implement an asynchronous file read using a library like `aiofiles`."
    },
    {
      "severity": "low",
      "category": "logic",
      "location": "frontend/src/components/NewsPanel.jsx:39-41",
      "description": "Inside `fetchData`, the error state is only set if `prev.length === 0`. If the component previously had news and a subsequent refresh fails, the user is never notified of the failure, and the loading spinner disappears, making the UI look successful but stale.",
      "suggestion": "Show a non-intrusive toast or indicator if a background refresh fails while data is already present."
    }
  ],
  "summary": "The review identified a critical logic bug in mobile data merging and significant issues with broad exception handling and blocking I/O in the backend."
}

```

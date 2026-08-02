---
title: What Is the Recommended Way to Handle Remote Config Fetch Failures? – Unity
  Support Help Center
id: what-is-the-recommended-way-to-handle-remote-config-fetch-failures-unity-support
tags:
- prompt-asset-register-solution-4fbe59
created: '2026-08-02T03:12:18.301103Z'
source: https://support.unity.com/hc/en-us/articles/45376234231828-What-Is-the-Recommended-Way-to-Handle-Remote-Config-Fetch-Failures
source_domain: support.unity.com
fetched_at: '2026-08-02T03:12:18.294106Z'
fetch_provider: builtin
status: draft
type: note
tier: unknown
content_type: unknown
deprecated: false
utility_score: 14.0
---

What Is the Recommended Way to Handle Remote Config Fetch Failures? – Unity Support Help Center
Skip to main content
Overview
Remote Config is designed to be non-blocking and resilient. Games should continue to function smoothly even if a Remote Config fetch is delayed, times out, or returns an error.
The recommended pattern is to define sensible default values in code, read values using
appConfig
getters with a fallback, and continue using the last-known-good values when Remote Config cannot be retrieved. This approach ensures gameplay stability across varying network conditions and temporary service degradation.
Symptoms
Remote Config requests intermittently time out or return errors (for example, 500 responses or request timeouts).
FetchConfigsAsync
fails during periods of high load or poor connectivity.
Features, economy values, or gameplay logic behave unexpectedly when Remote Config values are unavailable.
You want configuration values to persist across sessions even if a fetch fails.
You are unsure whether Remote Config automatically falls back to default or cached values.
Cause
Remote Config fetches depend on network conditions and service latency. During peak traffic, regional variance, or brief interruptions, a fetch may take longer than expected or fail to complete within the configured timeout.
Remote Config is designed to complement your game’s existing configuration logic. To ensure a consistent player experience, best practice is to define local defaults and continue using previously fetched values while new configurations are being retrieved.
Resolution
1. Define defaults in code
Provide a local default for every Remote Config key. These defaults are used automatically when no fetched value is available.
Defaults should represent safe, playable baselines.
Avoid defaults that would block or soft-lock core gameplay if applied.
2. Read values with a fallback
Use
appConfig
getters that include a default parameter (for example,
GetInt
,
GetFloat
,
GetBool
, or
GetString
with a default value).
If the key is missing or the fetch has not completed yet, the default value is returned.
This allows gameplay to proceed without waiting for a fetch result.
3. Fetch Remote Config non-blockingly
Call
FetchConfigsAsync
early (for example, at app start), but do not block gameplay on the result.
Start the game using defaults or cached values.
Apply updated values once the fetch completes successfully.
4. Persist last-known-good values
Remote Config automatically caches the last successful fetch locally on the device. If a subsequent fetch fails or times out, appConfig continues to serve those cached values. In most cases, you do not need to manually persist Remote Config values (for example, using PlayerPrefs) to achieve this behavior.
Continue using previously fetched values across sessions rather than resetting or failing. This helps maintain a consistent experience during temporary latency or regional connectivity issues.
5. Handle failures gracefully
If
FetchConfigsAsync
fails:
Log the error for visibility.
Continue using defaults or cached values.
Retry on a later session or using a backoff strategy.
Avoid tight retry loops or repeated fetch attempts within the same session.
6. Avoid aggressive fetch patterns
Avoid the following patterns:
Calling
FetchConfigsAsync
every frame.
Retrying immediately on failure.
Fetching repeatedly during active gameplay.
Remote Config is intended for session-level or event-driven updates, not continuous polling.
7. Keep startup fetches small (“critical vs. bulk”)
For predictable startup behavior:
Keep latency-sensitive or critical flags in a very small configuration.
Move large JSON payloads or bulk data to a backend or CDN.
Use Remote Config to point to versions or enable/disable content, rather than serving large payloads directly.
8. Short-lived processes (for example, match servers)
For short-lived processes without a persistent local cache:
Pass a small “critical” configuration snapshot at process startup (from a long-lived coordinator or internal service).
Hold those values for the lifetime of the process.
Avoid relying on live refetches during active matches.
Alternative (backend-enforced defaults)
For stricter guarantees, you can:
Store defaults or overrides in your backend.
Return a consolidated “effective configuration” to the client.
Use Remote Config for pointers, versioning, and staged rollout while the backend serves bulk values.
Gotchas
Always provide a fallback value when calling appConfig Get methods.
appConfig
evaluates the current snapshot at fetch time.
Design your game so it can start using defaults while Remote Config is being fetched.
Apply Remote Config values to tune or enhance gameplay without blocking core systems.
Related to
Remote Config
Related articles
How do I unlink my Google account from my Unity ID?
What is CS0619?
What is FOSS?
How do I activate or return my Unity Industry/ Enterprise/ Pro license?
Billing FAQ Unity Gaming Services
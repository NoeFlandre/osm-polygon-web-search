# HTTP status boundary design

`PageFetcher` and `BraveSearchProvider` currently implement the same
successful-response predicate inline. The transport module owns HTTP response
semantics, so it will expose one small `is_success_status` predicate. Both
adapters will delegate to it while retaining their existing domain-specific
error messages and payload handling.

The refactor is behavior-preserving: statuses from 200 through 299 remain
successful, all other statuses remain unsuccessful, and no request or retry
flow changes.

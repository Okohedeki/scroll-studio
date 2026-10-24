Self-hosted fonts download their files in parallel and write the cache atomically, so a cold build of a style with a large CJK face takes seconds instead of minutes.

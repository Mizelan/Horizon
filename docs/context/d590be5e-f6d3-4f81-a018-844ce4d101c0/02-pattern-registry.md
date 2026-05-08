# Pattern Registry

## Active Patterns

- P-2026-05-08-flat-metadata-spoof: Fake subprocess tests can overstate live metadata readiness when they inject fields that the real provider mode may not emit. For `yt-dlp --flat-playlist`, require at least one fixture that mirrors real flat playlist entries or remove flat mode before admitting live/source final_refresh.

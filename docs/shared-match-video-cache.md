# Shared original match videos

Connected helpers use their local source first, then the organization's private Neptune cache, then YouTube. A successfully downloaded original is offered back to the shared cache. Robot preparation, robot detector training, field detector training and robot match testing use this path. Previously installed helpers need an update to use it.

The private store is `neptune_secure/match-video-cache/<organization>/`. It stores original MP4 bytes, SHA-256 fingerprints and video IDs. No resizing, frame-rate conversion or lossy recompression is applied. Transfers are bounded to 512 MiB per individual match, in 8 MiB chunks. Downloads verify each chunk and the complete original before atomic publication on the helper. Uploads are serialized across the cache, resumable and published only after full checksum verification.

The total shared cache cap is 10 GiB across organizations. The server refuses a new upload unless it can retain at least 10 GiB of free disk after that source. It checks free space again while uploading. Completed sources are preserved when full; the cache does not silently evict training sources. A staging upload expires after 30 minutes without activity and is reclaimed by the next upload. This cache is separate from the helper's temporary local cache and its 14-day cleanup.

Completed robot labels with an immutable saved image and its original source fingerprint train directly from those exact saved images. A missing source fingerprint or a legacy frame without a saved image still requires the match video. Dataset provenance and held-out match/source checks are unchanged.

YouTube is still needed for a first source which no helper has cached. A sequential bulk queue waits between uncached downloads and pauses on a bot check. A cached source cannot restore a video that was never downloadable. Browser cookies and account credentials are not stored in the cache.

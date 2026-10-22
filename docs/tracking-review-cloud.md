# Tracking review backup

The connected helper backs up each **saved** robot identity review to Neptune. It uploads compressed review JSON (boxes, approved corrections, roster, source fingerprint, and video ID). The video and extracted frames stay on the helper computer. Human action labels and scouting imports remain in their existing database tables.

The `community_identity_reviews` table is scoped by organization and video SHA-256. The existing owner helper bearer connection authorizes `review_list`, `review_get`, and `review_put`. A revision check rejects stale edits from a second helper. Saving locally succeeds even when the network is down; the viewer shows that cloud backup is pending. Reopening the review retries. Existing local corrected reviews are backed up when the review picker opens.

On another connected helper, cloud reviews appear in the picker. It downloads the source video, checks the video fingerprint, restores the review, and republishes approved samples to that helper's local training library. A cloud review with a conflicting local correction is never silently overwritten. Export the local review before resolving such a conflict.

Deleting a saved model does not touch `community_identity_reviews`. No review is promoted into an action label, and inferred identities remain unapproved. The cloud stores up to 2 MiB compressed / 16 MiB expanded per corrected review. The Q3 sample is about 1.2 MiB compressed.

## Verification

Run `php tests/server/review-storage.php` and the engine tests in the packaged helper Python. The server test checks round trip, organization isolation, retry, stale edit rejection, and preservation of a single review record. Full size Q3 review was also stored and retrieved through the same PHP class with a 1.59 MiB request body.

## Rollback

Restore the previous helper and API files from the release backup. The new table can remain in place: older code does not read it. Preserve the table if saved reviews must be available after reinstallation. No destructive migration is required.

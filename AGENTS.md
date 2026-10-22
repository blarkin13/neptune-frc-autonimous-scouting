# Rules for anyone working here (people, Codex, Claude)

1. **Count scores from the video.** No EPA, no team history, no prior-match priors, no feeding official
   totals back in as inputs. Official results may be used only to *evaluate*.
2. **Q7 (`2026txcmp1_qm7`) is the reserved benchmark.** Never train on it or tune against it.
3. **Preserve labels and imports.** Never rewrite Game Builder codes (`gb:<code>`, `definition_version`) or
   ViperScout imports (`viper-2026-activity-v1`).
4. **Don't weaken gates.** Release/benchmark gates and PU-head gates stay as strict or stricter. Don't force
   predicted points to match the official score, and don't invent reference scores.
5. **Owner-defined rules (applied at prediction, not learned):**
   - A robot visible and stationary for more than 5 s during teleop is `disabled`.
   - A robot with no recorded scoring has a scoring contribution of 0 (marked `zero_by_policy`).
   - Each alliance's contribution percentages total 100% (`contribution_percent`); if no robot on the
     alliance has recorded scoring, all stay 0. This is a separate field from predicted points.
6. **Edit `engine/` only once.** It is installed to two places; `scripts/sync-to-neptune.sh` handles both.
   If you add a file the server needs, add it to `engine/SERVER_FILES.txt`.
7. **No data or secrets in git.** No videos, model weights (`*.pt`), DB dumps, `.cnf` files or tokens. Put
   pointers in `data-pointers/`.
8. **Log your work in `WORK.md`.** Who, what, why, and how it was checked, newest first.
9. Stop when the repo owner says stop.
10. **Keep deployment backups small.** For server code updates, back up only files being replaced. Never recursively copy `public_html/Neptune/community/downloads` into a code rollback directory. For a helper release, retain only the current appcast, checksum manifest, allowlist, website text, and prior current DMG needed for rollback; verify hashes before and after publication. Remove temporary transfer stages after verification.

# Rules for anyone working here (people, Codex, Claude)

1. **Count scores from the video.** No EPA, no team history, no prior-match priors, no feeding official
   totals back in as inputs. Official results may be used only to *evaluate*.
2. **Q7 (`2026txcmp1_qm7`) is the reserved benchmark.** Never train on it or tune against it.
3. **Preserve labels and imports.** Never rewrite Game Builder codes (`gb:<code>`, `definition_version`) or
   ViperScout imports (`viper-2026-activity-v1`).
4. **Don't weaken gates.** Release/benchmark gates and PU-head gates stay as strict or stricter. Don't force
   alliance sums to match, and don't invent reference scores.
5. **Edit `engine/` only once.** It is installed to two places; `scripts/sync-to-neptune.sh` handles both.
   If you add a file the server needs, add it to `engine/SERVER_FILES.txt`.
6. **No data or secrets in git.** No videos, model weights (`*.pt`), DB dumps, `.cnf` files or tokens. Put
   pointers in `data-pointers/`.
7. **Log your work in `WORK.md`.** Who, what, why, and how it was checked, newest first.
8. Stop when the repo owner says stop.

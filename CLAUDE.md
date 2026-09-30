# CLAUDE.md — RoleRadarAI

This repository is designed to be worked on by both Claude Code and Codex without relying on chat memory.

Read and follow these repository files:

@AGENTS.md
@COMMIT_PROTOCOL.md
@BACKLOG.md

If present, also read the product sources of truth before implementing:

@docs/PRD.md
@docs/IMPLEMENTATION_PLAN.md
@docs/ARCHITECTURE.md

## Mandatory behavior

1. Start every session by inspecting Git state.
2. Resume the current `IN_PROGRESS` item in `BACKLOG.md`.
3. Do not silently expand product scope.
4. Do not invent unresolved behavior.
5. Run applicable verification before marking an item done.
6. Update `BACKLOG.md` before every material commit and before ending the session.
7. Update `AGENTS.md` whenever permanent repository commands, structure, or architecture rules change.
8. Commit atomic, working slices using the format defined in `COMMIT_PROTOCOL.md`.
9. When blocked and the human is unavailable, document the blocker and continue with another independent safe item.
10. Before ending, leave an exact handoff in `BACKLOG.md`.

The repository is the memory. Keep it resumable.

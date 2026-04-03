# Session Plan — Code Quality Audit

## Goal
Remove 0.5px hack, audit full codebase, fix correctness and architecture issues, document risks, add missing tests.

## Tasks
1. Remove 0.5px hack from collision.py — replace with clean integer snapping
2. Full codebase audit — document all issues by category
3. Fix Category A (physics correctness) and B (architectural violations)
4. Document Category C (dangerous interactions) and D (stability risks) in DECISIONS_NEEDED.md
5. Fix test coverage gaps (Category E)
6. Constants audit — remove unused, add missing
7. Final verification — tests, game run, SUMMARY.md

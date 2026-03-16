# PRD-003 Rules Engine Improvements Backlog

## 1. Title
This backlog captures post-v1 improvements for the deterministic rules engine.

## 2. Near-term UX Improvements
1. Create rule from transaction in one click from ledger transaction detail.
2. Add conflict detector to identify overlapping matchers and priority collisions.
3. Add confidence-based suggestion queue for candidate rules before activation.
4. Add bulk approve/reject flow for suggested rules.

## 3. Advanced Rule Types
1. Recurring subscription detection with cadence + amount tolerance.
2. Refund pairing against prior expense patterns.
3. Transfer disambiguation between internal vs external transfers.
4. Salary detection windows by expected day range and source signals.
5. Amount-band disambiguation for merchants with multiple purchase intents.
6. Exception clauses (`match X unless Y`) for cleaner deterministic control.
7. Travel or moment auto-tag windows for time-bounded event mapping.

## 4. Governance and Quality
1. Rule linting for unreachable conditions, invalid regex, and duplicate predicates.
2. Dead-rule detection for rules that never match across selected windows.
3. Drift alerts when formerly high-hit rules stop matching expected merchants.
4. Performance guardrails for regex-heavy rules and large rule sets.

## 5. Future Analytics Integration
1. Rule effectiveness metrics: match rate, apply rate, correction rate, revert rate.
2. False-positive review workflow to label and analyze bad auto-mappings.
3. Rollback simulation reports to estimate blast radius before destructive actions.

## Assumptions and Defaults
1. Keep deterministic v1 baseline for core execution.
2. Keep strict split invariants unchanged.
3. Keep append-only, queryable rule lineage as core infrastructure.
4. Keep safe rollback preview-before-confirm as deletion default.


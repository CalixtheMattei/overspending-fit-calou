2) PRD-005 — Moments (v2)
Goal

Enable users to define “Moments” and tag splits to them, with a candidate confirmation flow based on date range (dateOp), so users can isolate irregular spend and optionally exclude moment-tagged splits from analytics baseline.

Non-goals (v2)

Auto-tagging moments via rules engine.

Multi-tagging (a split belonging to multiple moments).

Analytics controls inside Moments tab (toggle lives in Analytics).

Definitions

Moment: user-defined event with metadata (name, date range, description).

Split: the atomic ledger line item. A split can be tagged to 0 or 1 moment.

Candidate: a split that appears relevant to a moment (based on dateOp in range + not already moment-tagged), surfaced for accept/reject.

Core decisions (locked)

Tagging can override date range (e.g., pre-booked train tickets).

Moments represent selected splits only, not “everything in range.”

Candidate discovery uses dateOp (operation date).

Changing a moment’s date range does not alter existing tags; it only changes candidates.

Moments can overlap.

Reassigning a split from one moment to another requires confirmation.

Deleting a moment untags all splits (moment_id -> null).

Data Model
Table: moments

id (uuid / int)

name (text, required)

start_date (date, required)

end_date (date, required)

description (text, nullable)

created_at, updated_at

Indexes:

(start_date, end_date) for range queries (optional)

name (optional search)

Field on splits

moment_id (nullable FK -> moments.id)

Index:

splits(moment_id)

splits(date_op) if not already indexed (dateOp anchor)

Table: moment_candidates

Stores confirmation state per (moment, split). This enables accept/reject persistence instead of recomputing “rejected” forever.

Columns:

id

moment_id (FK)

split_id (FK)

status enum: pending | accepted | rejected

first_seen_at (timestamp)

last_seen_at (timestamp)

decided_at (timestamp, nullable)

decided_by (nullable, if you later add users)

note (nullable, optional)
Constraints:

Unique (moment_id, split_id)

Indexes:

(moment_id, status)

(split_id) (for invalidation checks)

Invariants

If moment_candidates.status = accepted, then splits.moment_id = moment_id must be true (enforced in application logic).

A split can only have one splits.moment_id at a time; moving moments updates it.

Queries & Computation
Candidate selection rule (v2)

A split is a candidate for moment M if:

splits.date_op is between M.start_date and M.end_date (inclusive), AND

splits.moment_id IS NULL, AND

There is no moment_candidates row with status rejected for that (moment_id, split_id), unless user explicitly refreshes and wants rejected visible (UI filter).

Refresh candidates behavior

When user opens Candidates tab or clicks Refresh:

Upsert moment_candidates rows for all matching candidate splits:

new rows → pending

existing rows:

keep accepted/rejected as-is

update last_seen_at

Optional cleanup: do not delete old candidate rows; keep history.

Moment totals (card + detail)

Compute from tagged splits (not range):

expenses_total: sum of absolute values of negative amounts (or sum of negatives and display absolute)

income_total: sum of positive amounts

Category breakdown: group by split.category_id (or category label), using tagged splits only.

Screens & UX
A) Moments List Screen

Content

Grid of moment cards:

Name

Date range

Expenses total + Income total

Top 3 categories

Count of tagged splits

Sort/filter pill:

Sort: Most recent / Highest spend

Filter: Candidates only / Tagged only (optional quick filter affecting card badges / list mode)

Primary actions

Create moment

Click card → open Moment Overlay

Empty state

Explain purpose + CTA.

Loading

Skeleton cards.

B) Moment Overlay (modal / drawer)

Tabs: Tagged | Candidates

Tab 1: Tagged

Summary: expenses + income totals; category breakdown

Table: splits tagged to this moment

dateOp, label/payee, amount, category, account, open detail

Bulk actions:

Remove from moment (set moment_id null)

Move to another moment (select target → confirm)

Edge states:

No tagged splits → empty state + CTA to Candidates tab.

Tab 2: Candidates (confirmation flow)

Filters: Pending / Accepted / Rejected

Table: candidate split rows

Row actions: Accept / Reject

Bulk actions: Accept selected / Reject selected

Refresh candidates button

Unsplit transaction handling
There is an existing ambiguity in your app: some items may exist at transaction-level prior to splitting, and you already have a similar issue with category assignment. The Moments candidate UI must mirror existing behavior used today when assigning categories:

If the app auto-creates a single split when acting at transaction-level → reuse that behavior for “Accept”.

If the app blocks until the transaction is split → show a CTA “Split first” and route user to Transaction Detail.

This is not a new decision; it’s a consistency requirement.

C) Transaction Detail (splits editor)

Each split row has a Moment selector (optional)

Setting moment:

If split already has moment_id → change requires confirmation.

Clearing removes tag.

This manual selector supports out-of-range tagging (train tickets booked earlier).

Edge Cases

Overlapping moments: allowed; candidate sets may overlap; tagging is explicit.

Move split between moments: confirmation required; updates splits.moment_id and candidate statuses accordingly.

Delete moment: confirm; untag all splits; keep candidate history optional (can delete candidates too—v2 recommends delete to avoid orphan records).

Split edited after tagging:

Existing split keeps moment_id.

New splits default to null moment_id.

Refunds/income: included; totals show both expenses & income separately.

Candidates drift: if a split gets tagged elsewhere, it should disappear from pending candidates (or become “not eligible” on refresh).

Performance: indexes above; pagination for tables.

Acceptance Criteria
Creation & tagging

User can create a moment with name + date range.

User can tag a split to a moment in Transaction Detail even if split.dateOp is outside the range.

A split can have at most one moment tag; changing it prompts confirmation.

Moments list

Moments list shows cards with correct expenses/income totals from tagged splits.

Empty state displays when no moments exist.

Tagged tab

Tagged tab lists only splits with splits.moment_id = moment.id.

Bulk remove clears moment_id.

Bulk move prompts confirmation and results in correct reassignment.

Candidates flow

Candidates are derived from dateOp in range and moment_id IS NULL.

Accepting a candidate tags the split (moment_id set), marks candidate accepted.

Rejecting a candidate persists so it won’t reappear as pending unless user views “Rejected” filter.

Refresh candidates upserts pending candidates and updates last_seen_at without losing decisions.

Deletion

Deleting a moment untags all tagged splits and removes moment from list.

Analytics integration

Analytics tab can exclude all moment-tagged splits (global toggle) without needing Moments UI toggles.
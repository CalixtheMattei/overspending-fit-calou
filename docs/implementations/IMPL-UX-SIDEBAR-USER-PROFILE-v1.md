# IMPL-UX-SIDEBAR-USER-PROFILE-v1

## Summary
Replace fake hardcoded user identity in sidebar/header navigation with a single local profile model (frontend-only), add a dedicated `/profile` page for local edits (name, email, avatar URL), and remove dead placeholder account actions.

This implementation is explicitly **no-auth** and **no-backend**. It is UX and state-management polish only.

## Decision Lock (Product)
- Scope: UX polish only.
- Profile data source: local profile store (React context + localStorage).
- Profile entry point: avatar menu only (no primary sidebar nav item).
- Profile mode: local edit only.
- Editable fields: name, email, avatar URL.
- Avatar input mode: URL input with initials fallback.
- Unsupported account actions: hidden (not disabled placeholders).

## Why This Work Exists
Current navigation account UX is demo scaffolding and not user-friendly for a real single-user app:
- hardcoded fake identity appears in multiple components,
- account menu exposes actions that do nothing,
- profile action label exists but there is no profile route,
- account component props imply dynamic data but still render static placeholders.

This creates confusion and trust issues in a finance app UI.

## Current-State Audit (Concrete Findings)

### 1) Hardcoded fake identity across navigation surfaces
- `frontend/src/components/application/app-navigation/base-components/nav-account-card.tsx`
  - `placeholderAccounts` constant includes `Olivia Rhye` test identities.
- `frontend/src/components/application/app-navigation/sidebar-navigation/sidebar-slim.tsx`
  - hardcoded avatar URL + hardcoded name/email text.
- `frontend/src/components/application/app-navigation/header-navigation.tsx`
  - hardcoded avatar alt/src in desktop header dropdown.

### 2) Data-flow defects in account components
- `NavAccountMenu` accepts `accounts?: NavAccountType[]` but maps `placeholderAccounts` directly.
- `NavAccountCard` accepts `items?: NavAccountType[]` but resolves selected account from `placeholderAccounts`, ignoring `items`.

### 3) Dead-end account actions
- Menu contains `Add account`, `Sign out`, and account-switching UI that are not implemented in this product scope.

### 4) No profile route
- `frontend/src/main.tsx` does not define `/profile`.

## Goals
- Show real, user-editable local identity in all account UI surfaces.
- Provide a clear profile destination (`/profile`) from avatar menu.
- Keep behavior consistent across sidebar/header variants.
- Ensure robust fallback behavior for missing/broken avatar images.
- Persist user changes locally across reloads.

## Non-Goals
- Authentication, authorization, sessions.
- Multi-user support or account switching.
- Backend profile APIs or DB migrations.
- Remote avatar uploads or binary media storage.
- Settings/security/privacy features beyond local profile fields.

## UX Requirements

### Navigation UX
- Account surface at sidebar bottom remains present.
- Avatar menu includes only actions that work now:
  - `View profile` (navigates to `/profile`).
- Remove unsupported items from menu:
  - `Switch account` section
  - `Add account`
  - `Sign out`
  - any other unimplemented account actions

### Profile Page UX
- Route: `/profile`.
- Form fields:
  - Name (required)
  - Email (required)
  - Avatar URL (optional)
- Actions:
  - Save changes
  - Reset to defaults
- Live preview card should reflect current draft or saved state (implementation choice below).
- Save must update all nav account surfaces immediately (same render cycle or next tick).

### Avatar UX
- If avatar URL is empty: show initials avatar.
- If avatar URL fails to load: show initials avatar.
- If initials cannot be generated (edge case): fallback to existing icon placeholder.

## Data Model + Storage Contract

### `UserProfile` type
Create a shared frontend type:

```ts
export type UserProfile = {
  id: "local-user";
  name: string;
  email: string;
  avatarUrl: string | null;
};
```

### Defaults
Use neutral, non-demo defaults:
- `id: "local-user"`
- `name: "Personal User"` (or equivalent neutral label)
- `email: "you@example.com"`
- `avatarUrl: null`

### Storage
- localStorage key: `user-profile.v1`
- Stored shape: serialized `UserProfile`
- Read behavior:
  - if key missing: return defaults
  - if JSON parse fails: return defaults
  - if object invalid/partial: merge safe values with defaults
- Write behavior:
  - write only validated profile payload
  - fail silently on storage exceptions (quota/private mode)

### Validation rules (persisted)
- `name`:
  - trim whitespace
  - required
  - length 2..80
- `email`:
  - trim
  - required
  - basic email regex validation
- `avatarUrl`:
  - optional
  - if present, must parse as absolute `http` or `https` URL

## Architecture + State Ownership

### New profile feature module
Add:
- `frontend/src/features/profile/types.ts`
- `frontend/src/features/profile/defaults.ts`
- `frontend/src/features/profile/storage.ts`
- `frontend/src/features/profile/profile-provider.tsx`

### Provider API
Expose:
- `profile: UserProfile`
- `updateProfile(patch: Partial<UserProfile>): void`
- `replaceProfile(next: UserProfile): void`
- `resetProfile(): void`

Implementation notes:
- initialize from storage once on provider mount
- persist on updates
- throw clear error if hook used outside provider

### App integration
- Wrap route tree with profile provider in `frontend/src/main.tsx`.

## File-Level Implementation Spec

### 1) `frontend/src/main.tsx`
- Add import for `ProfilePage`.
- Add import for profile provider.
- Wrap current app providers with profile provider (around routes is sufficient).
- Add route:
  - `<Route path="profile" element={<ProfilePage />} />`

### 2) `frontend/src/components/application/app-navigation/base-components/nav-account-card.tsx`
- Remove `placeholderAccounts` and associated multi-account logic.
- Remove props related to account switching (`selectedAccountId`, `accounts`, `items`) unless reused cleanly for local profile.
- Pull profile from `useUserProfile()`.
- Compute `initials` with existing helper:
  - `frontend/src/components/base/avatar/utils.ts`
- `NavAccountMenu`:
  - keep only functional items in scope
  - wire `View profile` to `/profile`
  - do not render unsupported actions
- Ensure `AvatarLabelGroup` uses profile name/email/avatar with fallback initials.

### 3) `frontend/src/components/application/app-navigation/sidebar-navigation/sidebar-slim.tsx`
- Replace hardcoded identity strings and avatar URLs with profile context values.
- Use same fallback strategy as account card.

### 4) `frontend/src/components/application/app-navigation/header-navigation.tsx`
- Replace hardcoded avatar in top-right trigger with profile context values and initials fallback.

### 5) `frontend/src/pages/profile-page.tsx` (new)
- Add page with:
  - header title + explanatory text
  - profile preview section
  - editable form fields
  - action row (Save, Reset)
- Use existing design system components where possible:
  - `Input`
  - `Button`
  - avatar components
- Error handling:
  - inline field errors for validation
  - disable Save while invalid
- Save behavior:
  - commit trimmed normalized values via provider
  - optional local success message
- Reset behavior:
  - revert to defaults (provider reset)

## Behavioral Contract (Decision Complete)

### Edit lifecycle
- Default state loads saved profile.
- User edits draft fields in `/profile`.
- On Save:
  - validate all fields
  - if valid, commit and persist
  - nav updates immediately
- On Reset:
  - set profile to default contract values
  - persist defaults
  - nav updates immediately

### Navigation lifecycle
- Clicking avatar menu `View profile` navigates to `/profile`.
- No other account-management action appears.

### Fallback lifecycle
- Invalid avatar URL format: block save and show error.
- Valid URL but 404/image error: render initials fallback in avatar component.

## Accessibility Requirements
- All actionable controls keyboard reachable.
- Form fields have labels and associated validation text.
- Avatar menu items remain accessible via keyboard and screen readers.
- `aria-current` behavior unchanged in navigation links.

## Error Handling
- Storage read/write errors must not crash app.
- Profile parse errors must self-heal to defaults.
- Form validation errors must be user-visible before save.

## Performance Constraints
- Profile provider state should be tiny and synchronous.
- Avoid unnecessary re-renders by keeping context value stable where possible.
- No network calls for profile operations.

## Testing Plan

### Unit tests (recommended)
- profile storage parse/validation:
  - missing key -> defaults
  - malformed JSON -> defaults
  - partial object -> merged defaults
  - valid object -> round-trip
- validation helpers:
  - name length bounds
  - email validity
  - avatar URL scheme rules

### Component tests (recommended)
- account card renders current profile values.
- avatar fallback shows initials when image fails.
- menu only shows supported actions.
- `View profile` triggers route navigation.

### Route/page tests (recommended)
- `/profile` renders fields with existing values.
- invalid form prevents save.
- save updates nav identity.
- reset returns to defaults.

### Manual QA checklist (required)
1. Launch app, verify sidebar bottom user card is not fake demo identity.
2. Open avatar menu, verify only supported action(s) appear.
3. Navigate to `/profile` from menu.
4. Change name/email/avatar URL and save.
5. Confirm sidebar/header identity updates without refresh.
6. Refresh page and confirm persistence.
7. Enter invalid avatar URL (`foo`) and confirm save blocked.
8. Enter valid URL to non-image/broken image and confirm initials fallback.
9. Click reset and confirm default values restored.
10. Confirm `npm run build` passes in `frontend`.

## Acceptance Criteria
- No hardcoded demo identity text remains in active nav surfaces.
- `/profile` route exists and is reachable from avatar menu.
- Profile edits persist via localStorage.
- Avatar fallback behavior is deterministic and graceful.
- Unsupported menu actions are hidden.
- Frontend build succeeds.

## Migration + Compatibility Notes
- Existing users with no storage key: seamless default profile.
- Existing users with unexpected key shape: fallback/merge, no crash.
- No backend compatibility impact.

## Risks and Mitigations
- Risk: stale hardcoded identity remains in less-used nav variants.
  - Mitigation: grep audit for known placeholders before merge.
- Risk: overly strict email validation blocks realistic inputs.
  - Mitigation: use permissive basic validation, not RFC-hard strictness.
- Risk: localStorage unavailable in some contexts.
  - Mitigation: fail-safe in-memory behavior and no-throw storage wrapper.

## Out-of-Scope Follow-Ups (Future)
- Replace local profile source with authenticated backend user endpoint.
- Add profile photo upload flow (server storage).
- Introduce settings page structure and account security actions.
- Multi-user account switching and sign-out flows.

## Definition of Done
- All scoped file changes merged.
- Manual QA checklist complete.
- Build passes (`frontend`: `npm run build`).
- Final grep confirms no active demo identity remnants in account UI paths.


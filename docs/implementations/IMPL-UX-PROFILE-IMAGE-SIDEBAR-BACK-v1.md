# IMPL-UX-PROFILE-IMAGE-SIDEBAR-BACK-v1

## Summary
Implement three frontend UX changes:

1. Replace `Avatar URL` editing on `/profile` with profile image import (local upload).
2. Make the left sidebar user card a clickable container that opens `/profile` (instead of relying on the top-right icon menu action).
3. Add a back button on `/profile` that returns to the last non-profile route (explicitly tracked), with fallback to `/imports`.

No backend/auth work. Frontend-only local profile behavior.

---

## Product Decisions (Locked)

- Upload controls appear in **both** places on `/profile`:
  - New `Image` section in the main form, below Email.
  - Upload/Change action inside the live preview container.
- Image constraints:
  - Allowed types: `image/png`, `image/jpeg`, `image/jpg`, `image/webp`
  - Max file size: `2 MB`
- Back button behavior:
  - Explicitly track last non-profile route.
  - Back button on `/profile` routes to tracked route.
  - Fallback: `/imports`.

---

## Scope

### In Scope
- Profile page form/UI updates for image import.
- Profile storage/validation updates to support uploaded image data URLs.
- Sidebar user section behavior update to direct click-to-profile.
- Last route tracking + profile back button.
- Build verification and manual QA.

### Out of Scope
- Backend image upload/storage.
- Auth/session/user management.
- Multi-account switching.

---

## Files to Change

- `frontend/src/pages/profile-page.tsx`
- `frontend/src/features/profile/storage.ts`
- `frontend/src/components/application/app-navigation/base-components/nav-account-card.tsx`
- `frontend/src/components/layouts/app-shell.tsx`
- Optional cleanup:
  - `frontend/src/components/application/app-navigation/header-navigation.tsx` (only if imports/usages need adjustment)

---

## Data/Interface Contract

Keep existing type shape to avoid broad refactor:

```ts
export type UserProfile = {
  id: "local-user";
  name: string;
  email: string;
  avatarUrl: string | null;
};
```

Interpret `avatarUrl` as **avatar source string** (not URL-only):
- Accept legacy absolute `http/https` URLs.
- Accept `data:image/...;base64,...` values (new upload flow).

No route contract changes (`/profile` already exists).

New session storage key:
- `last-non-profile-route.v1`

---

## Detailed Implementation Plan

### 1) Extend profile avatar validation/storage for uploaded images
File: `frontend/src/features/profile/storage.ts`

- Keep existing sanitization/read/write patterns.
- Add avatar-source validation:
  - `isValidHttpUrl(value)` for legacy URLs.
  - `isValidAvatarDataUrl(value)` for uploaded images.
- Update normalization and draft validation:
  - Empty string => `null`
  - Valid `http/https` => allowed
  - Valid `data:image/*;base64,...` => allowed
  - Everything else => validation error and sanitization drop
- Update preview avatar resolver to accept both URL and data URL sources.

---

### 2) Replace Avatar URL input with Image import UI on `/profile`
File: `frontend/src/pages/profile-page.tsx`

- Add top back button (`ArrowLeft`, label `Back`).
- Remove current `Avatar URL` text input field.
- Add `Image` section below Email in the left/form container:
  - Upload/Change button
  - Remove image action
  - Helper text with constraints (PNG/JPG/JPEG/WebP, max 2MB)
  - Inline error text
- Add upload action in live preview container as well (same underlying handler).
- Upload flow:
  1. Open file picker (`accept="image/png,image/jpeg,image/jpg,image/webp"`).
  2. Validate type + size (<= 2MB).
  3. Read file with `FileReader.readAsDataURL`.
  4. Store resulting data URL in draft avatar field.
  5. Clear image errors on success.
- Remove image flow:
  - Clear draft avatar source; fallback to initials in preview/nav.
- Save and Reset:
  - Save validates and persists via profile provider.
  - Reset restores defaults and clears image status/errors.

---

### 3) Make sidebar user section open profile directly
File: `frontend/src/components/application/app-navigation/base-components/nav-account-card.tsx`

- Convert the entire user card container into a click target to `/profile`.
- Remove top-right menu trigger behavior from sidebar card path.
- Preserve avatar/name/email rendering and focus ring styling.
- Keep keyboard accessibility (focusable, clear interactive semantics).

Note:
- Keep/remove `NavAccountMenu` only as needed by other components (do not break header compile path).

---

### 4) Track last non-profile route and wire profile back behavior
Files:
- `frontend/src/components/layouts/app-shell.tsx`
- `frontend/src/pages/profile-page.tsx`

#### `AppShell` tracking
- On route changes, if `pathname !== "/profile"`, write the current route to `sessionStorage["last-non-profile-route.v1"]`.
- Persist path + query + hash.

#### `/profile` back button
- On click:
  1. Read `last-non-profile-route.v1`.
  2. If valid internal route string (starts with `/`), navigate there.
  3. Else navigate to `/imports`.

---

## Edge Cases

- Unsupported format upload: show inline error, do not change avatar.
- File >2MB: show inline error, do not change avatar.
- FileReader failure: show inline error, keep previous avatar.
- Corrupted stored avatar source: sanitize to `null`.
- Direct open of `/profile` in new tab: back goes to `/imports`.
- Existing legacy URL avatars continue to work.

---

## Acceptance Criteria

1. `/profile` no longer uses `Avatar URL` text input.
2. `/profile` has image upload section below Email.
3. Live preview container also allows image upload/change.
4. Sidebar user card is clickable and opens `/profile`.
5. Sidebar card no longer depends on top-right icon for profile navigation.
6. `/profile` has a back button that returns to tracked last route.
7. If no tracked route exists, back button navigates to `/imports`.
8. Uploaded avatar persists locally and appears in sidebar/header surfaces.
9. Build passes in frontend.

---

## Verification Steps

### Build
- Run:
  - `npm run build` (in `frontend/`)

### Manual QA
1. Open app, click sidebar user card -> lands on `/profile`.
2. Upload valid image in Image section -> preview updates.
3. Upload via live preview action -> same state updates.
4. Try invalid type -> inline error shown.
5. Try >2MB file -> inline error shown.
6. Remove image -> initials fallback appears.
7. Save -> avatar/name/email update in nav surfaces.
8. Refresh -> persisted values remain.
9. Navigate from `/ledger/payees` to `/profile`, click Back -> returns to `/ledger/payees`.
10. Open `/profile` directly in fresh tab, click Back -> goes to `/imports`.

---

## Constraints for Implementer

- Do not touch unrelated local changes:
  - `frontend/src/components/foundations/featured-icon/featured-icon.tsx`
  - `frontend/src/pages/moments-page.tsx`
- Keep changes frontend-only and non-destructive.
- Preserve existing styling conventions and component library usage.

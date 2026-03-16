import type { UserProfile } from "./types";

export const USER_PROFILE_STORAGE_KEY = "user-profile.v1";

export const DEFAULT_USER_PROFILE: UserProfile = {
    id: "local-user",
    name: "Personal User",
    email: "you@example.com",
    avatarUrl: null,
};

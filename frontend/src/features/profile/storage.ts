import { DEFAULT_USER_PROFILE } from "./defaults";
import type { UserProfile, UserProfileDraft, UserProfileValidationErrors } from "./types";

const NAME_MIN_LENGTH = 2;
const NAME_MAX_LENGTH = 80;
const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const AVATAR_DATA_URL_REGEX = /^data:image\/(?:png|jpeg|jpg|webp);base64,[a-z0-9+/]+=*$/i;

export const LAST_NON_PROFILE_ROUTE_STORAGE_KEY = "last-non-profile-route.v1";

const isRecord = (value: unknown): value is Record<string, unknown> => {
    return typeof value === "object" && value !== null;
};

const isValidHttpUrl = (value: string) => {
    try {
        const parsed = new URL(value);
        return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch {
        return false;
    }
};

const isValidAvatarDataUrl = (value: string) => {
    return AVATAR_DATA_URL_REGEX.test(value);
};

const isValidAvatarSource = (value: string) => {
    return isValidHttpUrl(value) || isValidAvatarDataUrl(value);
};

const normalizeName = (value: unknown): string | null => {
    if (typeof value !== "string") return null;

    const trimmedValue = value.trim();
    if (trimmedValue.length < NAME_MIN_LENGTH || trimmedValue.length > NAME_MAX_LENGTH) return null;

    return trimmedValue;
};

const normalizeEmail = (value: unknown): string | null => {
    if (typeof value !== "string") return null;

    const trimmedValue = value.trim();
    if (!EMAIL_REGEX.test(trimmedValue)) return null;

    return trimmedValue;
};

const normalizeAvatarUrl = (value: unknown): string | null | undefined => {
    if (value === null || value === undefined) return null;
    if (typeof value !== "string") return undefined;

    const trimmedValue = value.trim();
    if (!trimmedValue) return null;
    if (!isValidAvatarSource(trimmedValue)) return undefined;

    return trimmedValue;
};

export const sanitizeStoredProfile = (value: unknown): UserProfile => {
    if (!isRecord(value)) {
        return { ...DEFAULT_USER_PROFILE };
    }

    const safeProfile: UserProfile = { ...DEFAULT_USER_PROFILE };

    if (value.id === "local-user") {
        safeProfile.id = "local-user";
    }

    const normalizedName = normalizeName(value.name);
    if (normalizedName) {
        safeProfile.name = normalizedName;
    }

    const normalizedEmail = normalizeEmail(value.email);
    if (normalizedEmail) {
        safeProfile.email = normalizedEmail;
    }

    const normalizedAvatarUrl = normalizeAvatarUrl(value.avatarUrl);
    if (normalizedAvatarUrl !== undefined) {
        safeProfile.avatarUrl = normalizedAvatarUrl;
    }

    return safeProfile;
};

export const toUserProfileDraft = (profile: UserProfile): UserProfileDraft => {
    return {
        name: profile.name,
        email: profile.email,
        avatarUrl: profile.avatarUrl ?? "",
    };
};

export const validateUserProfileDraft = (draft: UserProfileDraft): UserProfileValidationErrors => {
    const errors: UserProfileValidationErrors = {};
    const name = draft.name.trim();
    const email = draft.email.trim();
    const avatarUrl = draft.avatarUrl.trim();

    if (!name) {
        errors.name = "Name is required.";
    } else if (name.length < NAME_MIN_LENGTH || name.length > NAME_MAX_LENGTH) {
        errors.name = `Name must be between ${NAME_MIN_LENGTH} and ${NAME_MAX_LENGTH} characters.`;
    }

    if (!email) {
        errors.email = "Email is required.";
    } else if (!EMAIL_REGEX.test(email)) {
        errors.email = "Enter a valid email address.";
    }

    if (avatarUrl && !isValidAvatarSource(avatarUrl)) {
        errors.avatarUrl = "Avatar must be an absolute http/https URL or a valid image data URL.";
    }

    return errors;
};

export const getPreviewAvatarUrl = (avatarInput: string): string | null => {
    const normalizedAvatarInput = avatarInput.trim();
    if (!normalizedAvatarInput) return null;
    return isValidAvatarSource(normalizedAvatarInput) ? normalizedAvatarInput : null;
};

export type UserProfile = {
    id: "local-user";
    name: string;
    email: string;
    avatarUrl: string | null;
};

export type UserProfileDraft = {
    name: string;
    email: string;
    avatarUrl: string;
};

export type UserProfileValidationErrors = {
    name?: string;
    email?: string;
    avatarUrl?: string;
};

import type { PropsWithChildren } from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { DEFAULT_USER_PROFILE } from "./defaults";
import type { UserProfile } from "./types";
import { fetchProfile, updateProfile as apiUpdateProfile, deleteAvatar as apiDeleteAvatar } from "@/services/profile";
import type { RemoteUserProfile } from "@/services/profile";

function remoteToLocal(remote: RemoteUserProfile): UserProfile {
    return {
        id: "local-user",
        name: remote.name,
        email: remote.email,
        avatarUrl: remote.avatar_url,
    };
}

type UserProfileContextValue = {
    profile: UserProfile;
    isLoading: boolean;
    updateProfile: (patch: Partial<UserProfile>) => Promise<void>;
    replaceProfile: (next: UserProfile) => Promise<void>;
    resetProfile: () => Promise<void>;
    refreshProfile: () => Promise<void>;
};

const UserProfileContext = createContext<UserProfileContextValue | undefined>(undefined);

export const UserProfileProvider = ({ children }: PropsWithChildren) => {
    const [profile, setProfile] = useState<UserProfile>(DEFAULT_USER_PROFILE);
    const [isLoading, setIsLoading] = useState(true);

    const refreshProfile = useCallback(async () => {
        try {
            const remote = await fetchProfile();
            setProfile(remoteToLocal(remote));
        } catch {
            // Keep current state on network failure
        }
    }, []);

    useEffect(() => {
        fetchProfile()
            .then((remote) => setProfile(remoteToLocal(remote)))
            .catch(() => {/* keep default */})
            .finally(() => setIsLoading(false));
    }, []);

    const updateProfile = useCallback(async (patch: Partial<UserProfile>) => {
        setProfile((prev) => {
            const merged = { ...prev, ...patch };
            apiUpdateProfile({ name: merged.name, email: merged.email })
                .then((remote) => setProfile(remoteToLocal(remote)))
                .catch(() => {/* revert happens naturally on next refresh */});
            return merged;
        });
    }, []);

    const replaceProfile = useCallback(async (next: UserProfile) => {
        const remote = await apiUpdateProfile({ name: next.name, email: next.email });
        setProfile(remoteToLocal(remote));
    }, []);

    const resetProfile = useCallback(async () => {
        const [remote] = await Promise.all([
            apiUpdateProfile({ name: DEFAULT_USER_PROFILE.name, email: DEFAULT_USER_PROFILE.email }),
            apiDeleteAvatar(),
        ]);
        setProfile(remoteToLocal(remote));
    }, []);

    const contextValue = useMemo(
        () => ({ profile, isLoading, updateProfile, replaceProfile, resetProfile, refreshProfile }),
        [profile, isLoading, updateProfile, replaceProfile, resetProfile, refreshProfile],
    );

    return <UserProfileContext.Provider value={contextValue}>{children}</UserProfileContext.Provider>;
};

export const useUserProfile = () => {
    const context = useContext(UserProfileContext);

    if (!context) {
        throw new Error("useUserProfile must be used within a UserProfileProvider.");
    }

    return context;
};

import { API_BASE_URL, apiFetch } from "./api";

export type RemoteUserProfile = {
    id: number;
    name: string;
    email: string;
    avatar_url: string | null;
};

export const fetchProfile = () => apiFetch<RemoteUserProfile>("/profile");

export const updateProfile = (data: { name: string; email: string }) =>
    apiFetch<RemoteUserProfile>("/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });

export const uploadAvatar = async (file: File): Promise<RemoteUserProfile> => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await fetch(`${API_BASE_URL}/profile/avatar`, {
        method: "POST",
        body: formData,
    });
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        const message = (data?.detail as string | undefined) ?? "Failed to upload avatar.";
        throw new Error(message);
    }
    return response.json() as Promise<RemoteUserProfile>;
};

export const deleteAvatar = () =>
    apiFetch<RemoteUserProfile>("/profile/avatar", { method: "DELETE" });

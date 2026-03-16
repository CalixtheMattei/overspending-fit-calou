import { type ChangeEvent, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { ArrowLeft, Trash01, UploadCloud02 } from "@untitledui/icons";
import { AvatarProfilePhoto } from "@/components/base/avatar/avatar-profile-photo";
import { getInitials } from "@/components/base/avatar/utils";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { DEFAULT_USER_PROFILE } from "@/features/profile/defaults";
import { useUserProfile } from "@/features/profile/profile-provider";
import {
    LAST_NON_PROFILE_ROUTE_STORAGE_KEY,
    getPreviewAvatarUrl,
    toUserProfileDraft,
    validateUserProfileDraft,
} from "@/features/profile/storage";
import type { UserProfileDraft, UserProfileValidationErrors } from "@/features/profile/types";
import { uploadAvatar, deleteAvatar } from "@/services/profile";

const AVATAR_UPLOAD_ACCEPT = "image/png,image/jpeg,image/jpg,image/webp";
const AVATAR_MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024;
const AVATAR_ALLOWED_FILE_TYPES = new Set(["image/png", "image/jpeg", "image/jpg", "image/webp"]);
const PROFILE_BACK_FALLBACK_ROUTE = "/imports";

const hasErrors = (errors: UserProfileValidationErrors) => {
    return Object.values(errors).some(Boolean);
};

const isValidTrackedRoute = (value: string | null): value is string => {
    return Boolean(value && value.startsWith("/") && !value.startsWith("//"));
};

const getAvatarFileValidationError = (file: File): string | null => {
    const fileType = file.type.toLowerCase();

    if (!AVATAR_ALLOWED_FILE_TYPES.has(fileType)) {
        return "Unsupported image format. Use PNG, JPG, JPEG, or WebP.";
    }

    if (file.size > AVATAR_MAX_FILE_SIZE_BYTES) {
        return "Image must be 2MB or smaller.";
    }

    return null;
};

export const ProfilePage = () => {
    const navigate = useNavigate();
    const { profile, replaceProfile, resetProfile, refreshProfile } = useUserProfile();
    const avatarFileInputRef = useRef<HTMLInputElement>(null);
    const [draft, setDraft] = useState<UserProfileDraft>(() => toUserProfileDraft(profile));
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [avatarRemoved, setAvatarRemoved] = useState(false);
    const [statusMessage, setStatusMessage] = useState<string | null>(null);
    const [imageError, setImageError] = useState<string | null>(null);

    const validationErrors = useMemo(() => validateUserProfileDraft(draft), [draft]);
    const isSaveDisabled = hasErrors(validationErrors);

    const previewName = draft.name.trim() || profile.name;
    const previewEmail = draft.email.trim() || profile.email;
    const previewAvatarUrl = getPreviewAvatarUrl(draft.avatarUrl);
    const previewInitials = getInitials(previewName).trim().toUpperCase() || undefined;
    const imageActionLabel = previewAvatarUrl ? "Change image" : "Upload image";

    const handleBack = () => {
        let nextRoute = PROFILE_BACK_FALLBACK_ROUTE;

        if (typeof window !== "undefined") {
            const trackedRoute = window.sessionStorage.getItem(LAST_NON_PROFILE_ROUTE_STORAGE_KEY);
            if (isValidTrackedRoute(trackedRoute)) {
                nextRoute = trackedRoute;
            }
        }

        navigate(nextRoute);
    };

    const handleFieldChange = (field: keyof UserProfileDraft) => (value: string) => {
        setDraft((previous) => ({ ...previous, [field]: value }));
        setStatusMessage(null);
        setImageError(null);
    };

    const openImagePicker = () => {
        avatarFileInputRef.current?.click();
    };

    const handleImageUpload = (event: ChangeEvent<HTMLInputElement>) => {
        const inputElement = event.currentTarget;
        const file = inputElement.files?.[0];
        if (!file) return;

        const fileValidationError = getAvatarFileValidationError(file);
        if (fileValidationError) {
            setImageError(fileValidationError);
            setStatusMessage(null);
            inputElement.value = "";
            return;
        }

        const fileReader = new FileReader();

        fileReader.onload = () => {
            const imageDataUrl = fileReader.result;
            if (typeof imageDataUrl !== "string") {
                setImageError("Could not read image file. Please try a different file.");
                setStatusMessage(null);
                return;
            }

            setDraft((previous) => ({ ...previous, avatarUrl: imageDataUrl }));
            setSelectedFile(file);
            setAvatarRemoved(false);
            setImageError(null);
            setStatusMessage(null);
        };

        fileReader.onerror = () => {
            setImageError("Could not read image file. Please try a different file.");
            setStatusMessage(null);
        };

        fileReader.readAsDataURL(file);
        inputElement.value = "";
    };

    const handleRemoveImage = () => {
        setDraft((previous) => ({ ...previous, avatarUrl: "" }));
        setSelectedFile(null);
        setAvatarRemoved(true);
        setImageError(null);
        setStatusMessage(null);

        if (avatarFileInputRef.current) {
            avatarFileInputRef.current.value = "";
        }
    };

    const handleSave = async () => {
        const nextErrors = validateUserProfileDraft(draft);
        if (hasErrors(nextErrors)) {
            return;
        }

        try {
            await replaceProfile({ id: "local-user", name: draft.name, email: draft.email, avatarUrl: null });

            if (selectedFile) {
                await uploadAvatar(selectedFile);
            } else if (avatarRemoved) {
                await deleteAvatar();
            }

            await refreshProfile();
            setSelectedFile(null);
            setAvatarRemoved(false);
            setImageError(null);
            setStatusMessage("Profile saved.");
        } catch (err) {
            const message = err instanceof Error ? err.message : "Failed to save profile.";
            setStatusMessage(message);
        }
    };

    const handleReset = async () => {
        try {
            await resetProfile();
            setDraft(toUserProfileDraft(DEFAULT_USER_PROFILE));
            setSelectedFile(null);
            setAvatarRemoved(false);
            setImageError(null);
            setStatusMessage("Profile reset to defaults.");

            if (avatarFileInputRef.current) {
                avatarFileInputRef.current.value = "";
            }
        } catch {
            setStatusMessage("Failed to reset profile.");
        }
    };

    return (
        <section className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8">
            <Button className="self-start" color="secondary" iconLeading={ArrowLeft} onClick={handleBack}>
                Back
            </Button>

            <header className="flex flex-col gap-2">
                <h1 className="text-2xl font-semibold text-primary">Profile</h1>
                <p className="text-sm text-tertiary">Update your local identity details used across sidebar and header account surfaces.</p>
            </header>

            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
                <div className="rounded-2xl bg-primary p-6 shadow-xs ring-1 ring-secondary">
                    <div className="flex flex-col gap-4">
                        <Input
                            label="Name"
                            value={draft.name}
                            onChange={handleFieldChange("name")}
                            isRequired
                            isInvalid={Boolean(validationErrors.name)}
                            hint={validationErrors.name}
                        />

                        <Input
                            label="Email"
                            value={draft.email}
                            onChange={handleFieldChange("email")}
                            isRequired
                            isInvalid={Boolean(validationErrors.email)}
                            hint={validationErrors.email}
                        />

                        <div className="rounded-xl bg-secondary px-4 py-3 ring-1 ring-secondary_alt">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <h2 className="text-sm font-semibold text-primary">Image</h2>
                                <div className="flex flex-wrap items-center gap-2">
                                    <Button color="secondary" size="sm" iconLeading={UploadCloud02} onClick={openImagePicker}>
                                        {imageActionLabel}
                                    </Button>
                                    {previewAvatarUrl && (
                                        <Button color="tertiary-destructive" size="sm" iconLeading={Trash01} onClick={handleRemoveImage}>
                                            Remove image
                                        </Button>
                                    )}
                                </div>
                            </div>

                            <p className="mt-2 text-xs text-tertiary">PNG/JPG/JPEG/WebP, max 2MB.</p>
                            {imageError && <p className="mt-2 text-xs text-error-primary">{imageError}</p>}
                            {!imageError && validationErrors.avatarUrl && (
                                <p className="mt-2 text-xs text-error-primary">{validationErrors.avatarUrl}</p>
                            )}
                        </div>
                    </div>

                    <input ref={avatarFileInputRef} type="file" accept={AVATAR_UPLOAD_ACCEPT} className="hidden" onChange={handleImageUpload} />

                    <div className="mt-6 flex flex-wrap items-center gap-3">
                        <Button color="primary" onClick={handleSave} isDisabled={isSaveDisabled}>
                            Save changes
                        </Button>
                        <Button color="secondary" onClick={handleReset}>
                            Reset to defaults
                        </Button>
                    </div>

                    {statusMessage && <p className="mt-4 text-sm text-tertiary">{statusMessage}</p>}
                </div>

                <aside className="rounded-2xl bg-primary p-6 shadow-xs ring-1 ring-secondary">
                    <h2 className="text-sm font-semibold text-secondary">Live preview</h2>
                    <p className="mt-1 text-xs text-tertiary">Preview updates immediately, including initials fallback for missing or broken images.</p>

                    <div className="mt-5 flex flex-col items-center gap-4 rounded-xl bg-secondary px-4 py-6 ring-1 ring-secondary_alt">
                        <AvatarProfilePhoto
                            size="md"
                            src={previewAvatarUrl ?? undefined}
                            alt={previewName}
                            initials={previewInitials}
                        />

                        <div className="text-center">
                            <p className="text-sm font-semibold text-primary">{previewName}</p>
                            <p className="text-sm text-tertiary">{previewEmail}</p>
                        </div>

                        <div className="flex flex-wrap justify-center gap-2">
                            <Button color="secondary" size="sm" iconLeading={UploadCloud02} onClick={openImagePicker}>
                                {imageActionLabel}
                            </Button>
                            {previewAvatarUrl && (
                                <Button color="tertiary-destructive" size="sm" iconLeading={Trash01} onClick={handleRemoveImage}>
                                    Remove
                                </Button>
                            )}
                        </div>
                    </div>
                </aside>
            </div>
        </section>
    );
};

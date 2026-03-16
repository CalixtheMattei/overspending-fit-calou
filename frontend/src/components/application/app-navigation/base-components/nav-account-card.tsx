import type { FC } from "react";
import { useCallback, useEffect, useRef } from "react";
import { User01 } from "@untitledui/icons";
import { useFocusManager } from "react-aria";
import type { DialogProps as AriaDialogProps } from "react-aria-components";
import { Button as AriaButton, Dialog as AriaDialog } from "react-aria-components";
import { useNavigate } from "react-router";
import { AvatarLabelGroup } from "@/components/base/avatar/avatar-label-group";
import { getInitials } from "@/components/base/avatar/utils";
import { useUserProfile } from "@/features/profile/profile-provider";
import { cx } from "@/utils/cx";

export const NavAccountMenu = ({ className, ...dialogProps }: AriaDialogProps & { className?: string }) => {
    const navigate = useNavigate();
    const focusManager = useFocusManager();
    const dialogRef = useRef<HTMLDivElement>(null);

    const onKeyDown = useCallback(
        (event: KeyboardEvent) => {
            if (event.key === "ArrowDown") {
                focusManager?.focusNext({ tabbable: true, wrap: true });
            }

            if (event.key === "ArrowUp") {
                focusManager?.focusPrevious({ tabbable: true, wrap: true });
            }
        },
        [focusManager],
    );

    useEffect(() => {
        const element = dialogRef.current;
        if (element) {
            element.addEventListener("keydown", onKeyDown);
        }

        return () => {
            if (element) {
                element.removeEventListener("keydown", onKeyDown);
            }
        };
    }, [onKeyDown]);

    return (
        <AriaDialog
            {...dialogProps}
            ref={dialogRef}
            className={cx("w-66 rounded-xl bg-secondary_alt shadow-lg ring ring-secondary_alt outline-hidden", className)}
        >
            <div className="rounded-xl bg-primary ring-1 ring-secondary">
                <div className="flex flex-col gap-0.5 py-1.5">
                    <NavAccountCardMenuItem label="View profile" icon={User01} onPress={() => navigate("/profile")} />
                </div>
            </div>
        </AriaDialog>
    );
};

const NavAccountCardMenuItem = ({
    icon: Icon,
    label,
    onPress,
}: {
    icon?: FC<{ className?: string }>;
    label: string;
    onPress?: () => void;
}) => {
    return (
        <AriaButton slot="close" onPress={onPress} className="group/item w-full cursor-pointer px-1.5 focus:outline-hidden">
            <div
                className={cx(
                    "flex w-full items-center justify-between gap-3 rounded-md p-2 group-hover/item:bg-primary_hover",
                    "outline-focus-ring group-focus-visible/item:outline-2 group-focus-visible/item:outline-offset-2",
                )}
            >
                <div className="flex gap-2 text-sm font-semibold text-secondary group-hover/item:text-secondary_hover">
                    {Icon && <Icon className="size-5 text-fg-quaternary" />} {label}
                </div>
            </div>
        </AriaButton>
    );
};

export const NavAccountCard = () => {
    const navigate = useNavigate();
    const { profile } = useUserProfile();
    const profileInitials = getProfileInitials(profile.name);

    return (
        <AriaButton
            onPress={() => navigate("/profile")}
            className={cx(
                "group flex w-full cursor-pointer items-center gap-3 rounded-xl p-3 ring-1 ring-secondary ring-inset",
                "outline-focus-ring transition duration-100 ease-linear hover:bg-primary_hover focus-visible:outline-2 focus-visible:outline-offset-2",
            )}
        >
            <AvatarLabelGroup
                size="md"
                src={profile.avatarUrl ?? undefined}
                title={profile.name}
                subtitle={profile.email}
                initials={profileInitials}
                alt={profile.name}
            />
        </AriaButton>
    );
};

const getProfileInitials = (name: string) => {
    const initials = getInitials(name.trim()).trim().toUpperCase();
    return initials || undefined;
};

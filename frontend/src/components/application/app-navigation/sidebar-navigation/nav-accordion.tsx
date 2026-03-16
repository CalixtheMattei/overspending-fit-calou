import { useEffect, useMemo, useState } from "react";
import type { NavItemType } from "../config";
import { NavItemBase } from "../base-components/nav-item";

const STORAGE_KEY = "nav-accordion-open";

const readStoredState = (): Record<string, boolean> => {
    if (typeof window === "undefined") return {};
    try {
        const raw = window.localStorage.getItem(STORAGE_KEY);
        return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
    } catch {
        return {};
    }
};

const writeStoredState = (state: Record<string, boolean>) => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
};

interface NavAccordionProps {
    item: NavItemType;
    activeUrl?: string;
}

export const NavAccordion = ({ item, activeUrl }: NavAccordionProps) => {
    const isActive = useMemo(
        () =>
            !!activeUrl &&
            (item.href === activeUrl ||
                item.items?.some((child) => child.href === activeUrl) ||
                (!!item.href && activeUrl.startsWith(item.href))),
        [activeUrl, item.href, item.items],
    );

    const [open, setOpen] = useState(() => {
        const stored = readStoredState();
        if (typeof stored[item.label] === "boolean") {
            return stored[item.label];
        }
        return isActive;
    });

    useEffect(() => {
        if (isActive && !open) {
            setOpen(true);
        }
    }, [isActive, open]);

    return (
        <details
            open={open}
            className="appearance-none py-0.5"
            onToggle={(event) => {
                const next = event.currentTarget.open;
                setOpen(next);
                const stored = readStoredState();
                stored[item.label] = next;
                writeStoredState(stored);
            }}
        >
            <NavItemBase href={item.href} badge={item.badge} icon={item.icon} type="collapsible" current={isActive}>
                {item.label}
            </NavItemBase>

            <dd>
                <ul className="py-0.5">
                    {item.items?.map((childItem) => (
                        <li key={childItem.label} className="py-0.5">
                            <NavItemBase
                                href={childItem.href}
                                badge={childItem.badge}
                                type="collapsible-child"
                                current={activeUrl === childItem.href}
                            >
                                {childItem.label}
                            </NavItemBase>
                        </li>
                    ))}
                </ul>
            </dd>
        </details>
    );
};

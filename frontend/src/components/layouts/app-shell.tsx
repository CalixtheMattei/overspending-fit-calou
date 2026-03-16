import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";
import { Calendar, FileCode01, Lock01, SearchLg, Stars02, UploadCloud02 } from "@untitledui/icons";
import type { NavItemType } from "@/components/application/app-navigation/config";
import { SidebarNavigationSimple } from "@/components/application/app-navigation/sidebar-navigation/sidebar-simple";
import { LAST_NON_PROFILE_ROUTE_STORAGE_KEY } from "@/features/profile/storage";

const NAV_ITEMS: NavItemType[] = [
    { label: "Import", href: "/imports", icon: UploadCloud02 },
    {
        label: "Ledger",
        href: "/ledger",
        icon: SearchLg,
        items: [
            { label: "Dashboard", href: "/ledger" },
            { label: "Payees", href: "/ledger/payees" },
            { label: "Internal Accounts", href: "/ledger/internal-accounts" },
            { label: "Categories", href: "/ledger/categories" },
        ],
    },
    { label: "Rules", href: "/rules", icon: FileCode01 },
    { label: "Analytics", href: "/analytics", icon: Stars02 },
    { label: "Moments", href: "/moments", icon: Calendar },
];

const IS_DEMO = import.meta.env.VITE_DEMO_MODE === "true";

export const AppShell = () => {
    const location = useLocation();
    const bannerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!IS_DEMO || !bannerRef.current) return;
        const el = bannerRef.current;
        const update = () => {
            document.documentElement.style.setProperty("--app-banner-height", `${el.getBoundingClientRect().height}px`);
        };
        update();
        const ro = new ResizeObserver(update);
        ro.observe(el);
        return () => {
            ro.disconnect();
            document.documentElement.style.removeProperty("--app-banner-height");
        };
    }, []);

    useEffect(() => {
        if (typeof window === "undefined") return;
        if (location.pathname === "/profile") return;

        const currentRoute = `${location.pathname}${location.search}${location.hash}`;

        try {
            window.sessionStorage.setItem(LAST_NON_PROFILE_ROUTE_STORAGE_KEY, currentRoute);
        } catch {
            // Ignore session storage failures to preserve routing behavior.
        }
    }, [location.hash, location.pathname, location.search]);

    return (
        <div className="flex min-h-dvh flex-col bg-primary">
            {IS_DEMO && (
                <div ref={bannerRef} className="sticky top-0 z-50 flex items-center justify-center gap-2 border-b border-utility-warning-200 bg-utility-warning-50 px-4 py-2 text-sm font-medium text-utility-warning-700">
                    <Lock01 className="size-4 shrink-0" />
                    <span>Demo mode — data is read-only. All write actions are disabled.</span>
                </div>
            )}
            <div className="flex flex-1">
                <SidebarNavigationSimple activeUrl={location.pathname} items={NAV_ITEMS} />
                <div className="flex flex-1 flex-col">
                    <main className="flex flex-1 flex-col px-4 py-8 lg:px-10 lg:py-10">
                        <Outlet />
                    </main>
                </div>
            </div>
        </div>
    );
};

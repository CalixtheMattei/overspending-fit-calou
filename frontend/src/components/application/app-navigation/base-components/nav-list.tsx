import { cx } from "@/utils/cx";
import type { NavItemDividerType, NavItemType } from "../config";
import { NavItemBase } from "./nav-item";
import { NavAccordion } from "../sidebar-navigation/nav-accordion";

interface NavListProps {
    /** URL of the currently active item. */
    activeUrl?: string;
    /** Additional CSS classes to apply to the list. */
    className?: string;
    /** List of items to display. */
    items: (NavItemType | NavItemDividerType)[];
}

export const NavList = ({ activeUrl, items, className }: NavListProps) => {
    return (
        <ul className={cx("mt-4 flex flex-col px-2 lg:px-4", className)}>
            {items.map((item, index) => {
                if (item.divider) {
                    return (
                        <li key={index} className="w-full px-0.5 py-2">
                            <hr className="h-px w-full border-none bg-border-secondary" />
                        </li>
                    );
                }

                if (item.items?.length) {
                    return <NavAccordion key={item.label} item={item} activeUrl={activeUrl} />;
                }

                return (
                    <li key={item.label} className="py-0.5">
                        <NavItemBase
                            type="link"
                            badge={item.badge}
                            icon={item.icon}
                            href={item.href}
                            current={activeUrl === item.href}
                        >
                            {item.label}
                        </NavItemBase>
                    </li>
                );
            })}
        </ul>
    );
};

import { useEffect, useMemo, useState } from "react";
import { Moon01, Sun } from "@untitledui/icons";
import { Switch as AriaSwitch } from "react-aria-components";
import { useTheme } from "@/providers/theme-provider";
import { cx } from "@/utils/cx";

export const ThemeToggle = ({ className }: { className?: string }) => {
    const { theme, setTheme } = useTheme();
    const [systemIsDark, setSystemIsDark] = useState(false);

    useEffect(() => {
        if (typeof window === "undefined" || !window.matchMedia) {
            return;
        }

        const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
        const update = () => setSystemIsDark(mediaQuery.matches);

        update();

        if (theme !== "system") {
            return;
        }

        mediaQuery.addEventListener("change", update);
        return () => mediaQuery.removeEventListener("change", update);
    }, [theme]);

    const isDark = useMemo(() => {
        if (theme === "system") {
            return systemIsDark;
        }
        return theme === "dark";
    }, [theme, systemIsDark]);

    return (
        <div className={cx("rounded-lg bg-secondary_alt p-3 ring-1 ring-secondary ring-inset", className)}>
            <AriaSwitch
                aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
                isSelected={isDark}
                onChange={(selected) => setTheme(selected ? "dark" : "light")}
                className={(renderProps) =>
                    cx(
                        "group inline-flex items-center justify-center rounded-lg p-2 text-fg-secondary transition duration-150 ease-linear",
                        "outline-focus-ring focus-visible:outline-2 focus-visible:outline-offset-2",
                        renderProps.isSelected ? "bg-primary" : "bg-secondary",
                        renderProps.isHovered && "bg-primary_hover",
                        renderProps.isPressed && "bg-primary_hover",
                        renderProps.isDisabled && "cursor-not-allowed opacity-60",
                    )
                }
            >
                {({ isSelected }) => (
                    <span
                        className={cx(
                            "flex size-5 items-center justify-center transition duration-150 ease-linear",
                            isSelected ? "text-fg-primary" : "text-fg-secondary",
                        )}
                    >
                        {isSelected ? <Moon01 className="size-5" /> : <Sun className="size-5" />}
                    </span>
                )}
            </AriaSwitch>
        </div>
    );
};

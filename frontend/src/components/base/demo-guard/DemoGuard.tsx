import type { ReactElement } from "react";
import React from "react";
import { Tooltip } from "@/components/base/tooltip/tooltip";

const IS_DEMO = import.meta.env.VITE_DEMO_MODE === "true";

interface DemoGuardProps {
    children: ReactElement;
    message?: string;
}

/**
 * Wraps any Button (or ButtonUtility) to disable it and show an explanatory
 * tooltip when the app is running in demo mode. Outside demo mode it is a
 * transparent passthrough with zero runtime cost.
 *
 * Usage:
 *   <DemoGuard>
 *     <Button color="primary" onClick={handleCreate}>Create</Button>
 *   </DemoGuard>
 */
export function DemoGuard({ children, message = "Not available in demo mode" }: DemoGuardProps) {
    if (!IS_DEMO) return children;

    // Wrap the disabled child in a <span> so hover events are captured even
    // though react-aria disables pointer interactions on a disabled Button.
    return (
        <Tooltip title={message} placement="top" delay={150}>
            <span className="inline-flex cursor-not-allowed">
                {React.cloneElement(children as React.ReactElement<{ isDisabled?: boolean; className?: string }>, { isDisabled: true, className: `${(children.props as { className?: string }).className ?? ""} pointer-events-none`.trim() })}
            </span>
        </Tooltip>
    );
}

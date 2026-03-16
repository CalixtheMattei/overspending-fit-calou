import { Button } from "@/components/base/buttons/button";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { formatAmount } from "@/utils/format";

type BulkActionColor = "primary" | "secondary" | "secondary-destructive";

export interface MomentsBulkActionItem {
    key: string;
    label: string;
    onPress: () => void;
    isDisabled?: boolean;
    isLoading?: boolean;
    color?: BulkActionColor;
}

interface MomentsBulkActionBarProps {
    selectedCount: number;
    label: string;
    selectedAmount?: number | null;
    onClearSelection: () => void;
    actions: MomentsBulkActionItem[];
}

export const MomentsBulkActionBar = ({ selectedCount, label, selectedAmount, onClearSelection, actions }: MomentsBulkActionBarProps) => {
    if (selectedCount <= 0) return null;

    return (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-secondary bg-secondary px-3 py-2.5">
            <p className="text-xs font-medium text-secondary">
                {selectedCount} selected {label}
                {selectedAmount != null ? <span className="ml-1.5 text-tertiary">· {formatAmount(selectedAmount)}</span> : null}
            </p>
            <div className="flex flex-wrap items-center gap-2">
                {actions.map((action) => (
                    <DemoGuard key={action.key}>
                        <Button
                            color={action.color ?? "secondary"}
                            size="sm"
                            onClick={action.onPress}
                            isDisabled={action.isDisabled}
                            isLoading={action.isLoading}
                        >
                            {action.label}
                        </Button>
                    </DemoGuard>
                ))}
                <Button color="tertiary" size="sm" onClick={onClearSelection}>
                    Clear
                </Button>
            </div>
        </div>
    );
};

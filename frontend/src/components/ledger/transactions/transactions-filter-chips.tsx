import { BadgeWithButton } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";

interface FilterChip {
    id: string;
    label: string;
    onRemove: () => void;
}

interface TransactionsFilterChipsProps {
    chips: FilterChip[];
    hasFilters: boolean;
    statusFilter: string;
    onStatusFilterChange: (value: string) => void;
    onClearAll: () => void;
}

export const TransactionsFilterChips = ({
    chips,
    hasFilters,
    statusFilter,
    onStatusFilterChange,
    onClearAll,
}: TransactionsFilterChipsProps) => {
    const uncategorizedActive = statusFilter === "uncategorized";

    return (
        <div className="flex w-full flex-wrap items-center gap-2">
            {chips.map((chip) => (
                <BadgeWithButton key={chip.id} size="sm" color="gray" buttonLabel={`Remove ${chip.label} filter`} onButtonClick={chip.onRemove}>
                    {chip.label}
                </BadgeWithButton>
            ))}
            {uncategorizedActive ? (
                <BadgeWithButton
                    size="sm"
                    color="warning"
                    buttonLabel="Clear uncategorized quick filter"
                    onButtonClick={() => onStatusFilterChange("all")}
                >
                    Uncategorized
                </BadgeWithButton>
            ) : (
                <Button size="sm" color="tertiary" onClick={() => onStatusFilterChange("uncategorized")}>
                    Uncategorized
                </Button>
            )}
            {hasFilters ? (
                <Button size="sm" color="tertiary" onClick={onClearAll}>
                    Clear all
                </Button>
            ) : null}
        </div>
    );
};

import { Dialog, DialogTrigger, Popover } from "react-aria-components";
import { Button } from "@/components/base/buttons/button";
import { Select } from "@/components/base/select/select";
import { cx } from "@/utils/cx";

type FilterOption = { id: string; label: string };

interface TransactionsFiltersPopoverProps {
    statusFilter: string;
    onStatusFilterChange: (value: string) => void;
    typeFilter: string;
    onTypeFilterChange: (value: string) => void;
    payeeFilter: string;
    onPayeeFilterChange: (value: string) => void;
    categoryFilter: string;
    onCategoryFilterChange: (value: string) => void;
    internalAccountFilter: string;
    onInternalAccountFilterChange: (value: string) => void;
    bankAccountFilter: string;
    onBankAccountFilterChange: (value: string) => void;
    statusOptions: FilterOption[];
    typeOptions: FilterOption[];
    payeeOptions: FilterOption[];
    categoryOptions: FilterOption[];
    internalAccountOptions: FilterOption[];
    bankAccountOptions: FilterOption[];
    onReset: () => void;
    className?: string;
}

export const TransactionsFiltersPopover = ({
    statusFilter,
    onStatusFilterChange,
    typeFilter,
    onTypeFilterChange,
    payeeFilter,
    onPayeeFilterChange,
    categoryFilter,
    onCategoryFilterChange,
    internalAccountFilter,
    onInternalAccountFilterChange,
    bankAccountFilter,
    onBankAccountFilterChange,
    statusOptions,
    typeOptions,
    payeeOptions,
    categoryOptions,
    internalAccountOptions,
    bankAccountOptions,
    onReset,
    className,
}: TransactionsFiltersPopoverProps) => {
    return (
        <DialogTrigger>
            <Button size="sm" color="secondary" aria-label="Open transaction filters">
                + Filter
            </Button>
            <Popover
                placement="bottom right"
                offset={8}
                className={({ isEntering, isExiting }) =>
                    cx(
                        "z-20 w-[min(92vw,340px)] origin-(--trigger-anchor-point) will-change-transform",
                        isEntering &&
                            "duration-150 ease-out animate-in fade-in placement-right:slide-in-from-left-0.5 placement-top:slide-in-from-bottom-0.5 placement-bottom:slide-in-from-top-0.5",
                        isExiting &&
                            "duration-100 ease-in animate-out fade-out placement-right:slide-out-to-left-0.5 placement-top:slide-out-to-bottom-0.5 placement-bottom:slide-out-to-top-0.5",
                    )
                }
            >
                <Dialog
                    aria-label="Transaction filters"
                    className={cx("rounded-xl bg-primary p-4 shadow-xl ring-1 ring-secondary_alt focus:outline-hidden", className)}
                >
                    <div className="flex flex-col gap-3">
                        <Select
                            aria-label="Filter transactions by status"
                            items={statusOptions}
                            selectedKey={statusFilter}
                            onSelectionChange={(key) => key && onStatusFilterChange(String(key))}
                            placeholder="Status"
                        >
                            {(item) => <Select.Item id={item.id} label={item.label} />}
                        </Select>
                        <Select
                            aria-label="Filter transactions by type"
                            items={typeOptions}
                            selectedKey={typeFilter}
                            onSelectionChange={(key) => key && onTypeFilterChange(String(key))}
                            placeholder="Type"
                        >
                            {(item) => <Select.Item id={item.id} label={item.label} />}
                        </Select>
                        <Select
                            aria-label="Filter transactions by payee"
                            items={payeeOptions}
                            selectedKey={payeeFilter}
                            onSelectionChange={(key) => key && onPayeeFilterChange(String(key))}
                            placeholder="Payee"
                        >
                            {(item) => <Select.Item id={item.id} label={item.label} />}
                        </Select>
                        <Select
                            aria-label="Filter transactions by category"
                            items={categoryOptions}
                            selectedKey={categoryFilter}
                            onSelectionChange={(key) => key && onCategoryFilterChange(String(key))}
                            placeholder="Category"
                        >
                            {(item) => <Select.Item id={item.id} label={item.label} />}
                        </Select>
                        <Select
                            aria-label="Filter transactions by internal account"
                            items={internalAccountOptions}
                            selectedKey={internalAccountFilter}
                            onSelectionChange={(key) => key && onInternalAccountFilterChange(String(key))}
                            placeholder="Internal account"
                        >
                            {(item) => <Select.Item id={item.id} label={item.label} />}
                        </Select>
                        <Select
                            aria-label="Filter transactions by bank account"
                            items={bankAccountOptions}
                            selectedKey={bankAccountFilter}
                            onSelectionChange={(key) => key && onBankAccountFilterChange(String(key))}
                            placeholder="Bank account"
                        >
                            {(item) => <Select.Item id={item.id} label={item.label} />}
                        </Select>
                        <Button size="sm" color="tertiary" onClick={onReset}>
                            Clear all
                        </Button>
                    </div>
                </Dialog>
            </Popover>
        </DialogTrigger>
    );
};

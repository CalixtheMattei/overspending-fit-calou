import { SearchLg } from "@untitledui/icons";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";

// Deprecated: replaced by TransactionsFiltersPopover in the ledger dashboard.
type FilterOption = { id: string; label: string };

interface TransactionsFiltersProps {
    searchQuery: string;
    onSearchQueryChange: (value: string) => void;
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
}

export const TransactionsFilters = ({
    searchQuery,
    onSearchQueryChange,
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
}: TransactionsFiltersProps) => {
    return (
        <div className="rounded-2xl bg-primary p-4 shadow-xs ring-1 ring-secondary">
            <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-[220px] flex-1">
                    <Input
                        label="Search"
                        icon={SearchLg}
                        placeholder="Search label or payee"
                        value={searchQuery}
                        onChange={(value) => onSearchQueryChange(value)}
                    />
                </div>
                <Select
                    label="Status"
                    items={statusOptions}
                    selectedKey={statusFilter}
                    onSelectionChange={(key) => key && onStatusFilterChange(String(key))}
                    className="min-w-[180px]"
                >
                    {(item) => <Select.Item id={item.id} label={item.label} />}
                </Select>
                <Select
                    label="Type"
                    items={typeOptions}
                    selectedKey={typeFilter}
                    onSelectionChange={(key) => key && onTypeFilterChange(String(key))}
                    className="min-w-[170px]"
                >
                    {(item) => <Select.Item id={item.id} label={item.label} />}
                </Select>
                <Select
                    label="Payee"
                    items={payeeOptions}
                    selectedKey={payeeFilter}
                    onSelectionChange={(key) => key && onPayeeFilterChange(String(key))}
                    className="min-w-[190px]"
                >
                    {(item) => <Select.Item id={item.id} label={item.label} />}
                </Select>
                <Select
                    label="Category"
                    items={categoryOptions}
                    selectedKey={categoryFilter}
                    onSelectionChange={(key) => key && onCategoryFilterChange(String(key))}
                    className="min-w-[190px]"
                >
                    {(item) => <Select.Item id={item.id} label={item.label} />}
                </Select>
                <Select
                    label="Internal account"
                    items={internalAccountOptions}
                    selectedKey={internalAccountFilter}
                    onSelectionChange={(key) => key && onInternalAccountFilterChange(String(key))}
                    className="min-w-[210px]"
                >
                    {(item) => <Select.Item id={item.id} label={item.label} />}
                </Select>
                <Select
                    label="Bank account"
                    items={bankAccountOptions}
                    selectedKey={bankAccountFilter}
                    onSelectionChange={(key) => key && onBankAccountFilterChange(String(key))}
                    className="min-w-[210px]"
                >
                    {(item) => <Select.Item id={item.id} label={item.label} />}
                </Select>
                <Button size="sm" color="tertiary" onClick={onReset}>
                    Reset filters
                </Button>
            </div>
        </div>
    );
};

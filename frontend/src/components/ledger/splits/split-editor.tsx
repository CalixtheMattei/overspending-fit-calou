import { useMemo, type MouseEvent } from "react";
import { Trash01 } from "@untitledui/icons";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { ButtonUtility } from "@/components/base/buttons/button-utility";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";
import { getCategoryDisplayLabel } from "@/components/ledger/categories/category-visuals";
import { CategoryTreePicker } from "@/components/ledger/categories/category-tree-picker";
import { cx } from "@/utils/cx";
import { amountClass, formatAmount } from "@/utils/format";
import type { Category } from "@/services/categories";
import type { InternalAccount } from "@/services/internal-accounts";
import type { Moment } from "@/services/moments";
import type { SplitDraft, SplitTotals, SplitValidation } from "./use-split-draft";

interface SplitEditorProps {
    transactionAmount: number;
    currency: string;
    splitDrafts: SplitDraft[];
    splitTotals: SplitTotals;
    splitValidation: SplitValidation;
    activeSplitIndex: number | null;
    categories: Category[];
    moments: Moment[];
    internalAccounts: InternalAccount[];
    onActiveSplitIndexChange: (index: number) => void;
    onAddSplit: () => void;
    onFillRemaining: () => void;
    onSingleSplit: () => void;
    onSplitFieldChange: (index: number, field: keyof SplitDraft, value: string | number | null) => void;
    onSplitDelete: (index: number) => void;
    onCreateCategoryRequest: (index: number) => void;
    onCreateInternalAccountRequest: (index: number) => void;
}

export const SplitEditor = ({
    transactionAmount,
    currency,
    splitDrafts,
    splitTotals,
    splitValidation,
    activeSplitIndex,
    categories,
    moments,
    internalAccounts,
    onActiveSplitIndexChange,
    onAddSplit,
    onFillRemaining,
    onSingleSplit,
    onSplitFieldChange,
    onSplitDelete,
    onCreateCategoryRequest,
    onCreateInternalAccountRequest,
}: SplitEditorProps) => {
    const categoryById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);

    /** IDs of deprecated categories that are currently selected on splits. */
    const forceVisibleIds = useMemo(() => {
        const ids = new Set<number>();
        for (const split of splitDrafts) {
            if (split.category_id !== null) {
                const cat = categoryById.get(split.category_id);
                if (cat?.is_deprecated) {
                    ids.add(cat.id);
                    if (cat.parent_id !== null) ids.add(cat.parent_id);
                }
            }
        }
        return ids;
    }, [splitDrafts, categoryById]);

    return (
        <div className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-secondary">Splits</span>
                <div className="flex flex-wrap gap-2">
                    <Button size="sm" color="secondary" onClick={onSingleSplit}>
                        Single split
                    </Button>
                    <Button size="sm" color="secondary" isDisabled={splitTotals.remaining === 0} onClick={onAddSplit}>
                        Add remaining
                    </Button>
                    <Button
                        size="sm"
                        color="tertiary"
                        isDisabled={activeSplitIndex === null || splitTotals.remaining === 0}
                        onClick={onFillRemaining}
                    >
                        Fill remaining
                    </Button>
                </div>
            </div>

            <div className="flex flex-col gap-3">
                {splitDrafts.length === 0 && (
                    <div className="rounded-lg border border-dashed border-secondary p-4 text-sm text-tertiary">
                        No splits yet. Add remaining to start categorizing.
                    </div>
                )}
                {splitDrafts.map((split, index) => {
                    const availableInternalAccounts = internalAccounts.filter(
                        (account) => !account.is_archived || account.id === split.internal_account_id,
                    );
                    const selectedCategory = split.category_id ? categoryById.get(split.category_id) ?? null : null;
                    const isDeprecatedSelection = Boolean(selectedCategory?.is_deprecated);
                    const canFixDeprecated = Boolean(
                        selectedCategory?.is_deprecated && selectedCategory.canonical_id !== null && selectedCategory.canonical_id !== undefined,
                    );
                    const canonicalCategory = canFixDeprecated
                        ? categoryById.get(selectedCategory?.canonical_id as number) ?? null
                        : null;

                    return (
                        <div
                            key={`${split.id ?? "new"}-${index}`}
                            className={cx(
                                "grid gap-3 rounded-xl bg-primary p-3 ring-1 ring-secondary",
                                activeSplitIndex === index && "ring-2 ring-brand",
                            )}
                            onClick={() => onActiveSplitIndexChange(index)}
                        >
                            {isDeprecatedSelection && (
                                <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-warning-subtle bg-warning-primary/10 px-3 py-2">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Badge size="sm" color="warning">
                                            Deprecated
                                        </Badge>
                                        <span className="text-xs text-warning-primary">
                                            {canFixDeprecated && canonicalCategory
                                                ? `Use ${getCategoryDisplayLabel(canonicalCategory)} instead.`
                                                : "This category is deprecated and hidden from pickers."}
                                        </span>
                                    </div>
                                    {canFixDeprecated && selectedCategory?.canonical_id && (
                                        <Button
                                            size="sm"
                                            color="tertiary"
                                            onClick={(event: MouseEvent<HTMLButtonElement>) => {
                                                event.stopPropagation();
                                                onSplitFieldChange(index, "category_id", selectedCategory.canonical_id as number);
                                            }}
                                        >
                                            Fix
                                        </Button>
                                    )}
                                </div>
                            )}
                            <div className="grid gap-3 md:grid-cols-[140px_1fr_1fr]">
                                <Input
                                    aria-label="Split amount"
                                    placeholder="Amount"
                                    value={split.amount}
                                    onChange={(value) => onSplitFieldChange(index, "amount", value)}
                                    inputMode="decimal"
                                />
                                <CategoryTreePicker
                                    aria-label="Split category"
                                    categories={categories}
                                    selectedCategoryId={split.category_id}
                                    onSelect={(id) => onSplitFieldChange(index, "category_id", id)}
                                    onCreateCategory={() => onCreateCategoryRequest(index)}
                                    placeholder="Category"
                                    hideDeprecated
                                    forceVisibleIds={forceVisibleIds.size > 0 ? forceVisibleIds : undefined}
                                />
                                <Select
                                    aria-label="Split moment"
                                    items={[
                                        { id: "none", label: "No moment" },
                                        ...moments.map((moment) => ({
                                            id: String(moment.id),
                                            label: moment.name,
                                        })),
                                    ]}
                                    selectedKey={split.moment_id ? String(split.moment_id) : "none"}
                                    onSelectionChange={(key) => {
                                        if (!key || String(key) === "none") {
                                            onSplitFieldChange(index, "moment_id", null);
                                            return;
                                        }
                                        onSplitFieldChange(index, "moment_id", Number(key));
                                    }}
                                    placeholder="Moment"
                                >
                                    {(item) => <Select.Item id={item.id} label={item.label} />}
                                </Select>
                            </div>
                            <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
                                <Select
                                    aria-label="Internal account"
                                    items={[
                                        { id: "none", label: "No internal account" },
                                        { id: "create", label: "Create internal account" },
                                        ...availableInternalAccounts.map((account) => ({
                                            id: String(account.id),
                                            label: account.name,
                                        })),
                                    ]}
                                    selectedKey={split.internal_account_id ? String(split.internal_account_id) : "none"}
                                    onSelectionChange={(key) => {
                                        if (!key) return;
                                        if (String(key) === "create") {
                                            onCreateInternalAccountRequest(index);
                                            return;
                                        }
                                        if (String(key) === "none") {
                                            onSplitFieldChange(index, "internal_account_id", null);
                                            return;
                                        }
                                        onSplitFieldChange(index, "internal_account_id", Number(key));
                                    }}
                                    placeholder="Internal account"
                                >
                                    {(item) => <Select.Item id={item.id} label={item.label} />}
                                </Select>
                                <Input
                                    aria-label="Split note"
                                    placeholder="Note"
                                    value={split.note}
                                    onChange={(value) => onSplitFieldChange(index, "note", value)}
                                />
                                <ButtonUtility
                                    icon={Trash01}
                                    tooltip="Delete split"
                                    onClick={(event: MouseEvent<HTMLButtonElement>) => {
                                        event.stopPropagation();
                                        onSplitDelete(index);
                                    }}
                                />
                            </div>
                        </div>
                    );
                })}
            </div>

            <div className="rounded-xl bg-primary p-4 ring-1 ring-secondary">
                <div className="grid gap-2 text-sm text-tertiary">
                    <div className="flex items-center justify-between">
                        <span>Transaction total</span>
                        <span className={cx("font-semibold", amountClass(transactionAmount))}>
                            {formatAmount(transactionAmount, currency)}
                        </span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span>Splits sum</span>
                        <span>{formatAmount(splitTotals.sum, currency)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                        <span>Remaining</span>
                        <span
                            className={cx(
                                "font-semibold",
                                splitTotals.remaining === 0 ? "text-success-primary" : "text-error-primary",
                            )}
                        >
                            {formatAmount(splitTotals.remaining, currency)}
                        </span>
                    </div>
                </div>
            </div>

            {splitValidation.message && (
                <div className="rounded-lg border border-warning-subtle bg-warning-primary/10 p-3 text-xs text-warning-primary">
                    {splitValidation.message}
                </div>
            )}
        </div>
    );
};

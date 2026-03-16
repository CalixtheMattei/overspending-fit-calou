import type { MouseEvent, ReactNode } from "react";
import { SearchLg } from "@untitledui/icons";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { PaginationCardMinimal } from "@/components/application/pagination/pagination";
import { Table, TableCard } from "@/components/application/table/table";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { getCategoryDisplayLabel, resolveCategoryIcon } from "@/components/ledger/categories/category-visuals";
import { cx } from "@/utils/cx";
import { amountClass, formatAmount, formatDate } from "@/utils/format";
import type { Category } from "@/services/categories";
import type { TransactionSummary } from "@/services/transactions";

const TRANSACTIONS_COLUMNS = [
    { id: "date", name: "Date" },
    { id: "label", name: "Label" },
    { id: "payee", name: "Payee" },
    { id: "category", name: "Category" },
    { id: "amount", name: "Amount" },
    { id: "split_action", name: "Split action" },
] as const;

type EmptyStateVariant = "filtered_empty" | "true_empty";

type ResolvedCategory = {
    name: string;
    display_name?: string | null;
    icon?: string | null;
    color?: string | null;
};

const getCategoryCell = (row: TransactionSummary, categoryById: Map<number, Category>) => {
    if (row.splits_count === 0) {
        return { kind: "uncategorized" as const, label: "Uncategorized" };
    }
    if (row.splits_count > 1) {
        return { kind: "split" as const, label: `Split (${row.splits_count})` };
    }
    if (row.single_category_id) {
        const category: ResolvedCategory | null =
            categoryById.get(row.single_category_id) ?? row.single_category ?? null;
        if (category) {
            return {
                kind: "category" as const,
                label: getCategoryDisplayLabel(category),
                icon: category.icon ?? "tag",
                color: category.color ?? "#9CA3AF",
            };
        }
        return {
            kind: "category" as const,
            label: `Category #${row.single_category_id}`,
            icon: "tag",
            color: "#9CA3AF",
        };
    }
    return { kind: "uncategorized" as const, label: "Uncategorized" };
};

const formatTypeLabel = (value: string) => value.charAt(0).toUpperCase() + value.slice(1);

const CategoryPill = ({ label, color, icon }: { label: string; color: string; icon: string }) => {
    const Icon = resolveCategoryIcon(icon);
    return (
        <span className="inline-flex max-w-full items-center gap-1.5 rounded-full bg-secondary px-2 py-0.5 text-xs font-medium text-primary ring-1 ring-secondary">
            <span className="size-2 rounded-full ring-1 ring-secondary" style={{ backgroundColor: color }} />
            <Icon className="size-3.5 shrink-0 text-fg-quaternary" />
            <span className="truncate">{label}</span>
        </span>
    );
};

interface TransactionsTableProps {
    transactions: TransactionSummary[];
    loading: boolean;
    error: string | null;
    transactionsEmpty: boolean;
    emptyStateVariant: EmptyStateVariant;
    onClearFilters: () => void;
    onRowSelect: (id: number) => void;
    onSplitAction: (id: number) => void;
    categoryById: Map<number, Category>;
    transactionsPage: number;
    totalPages: number;
    onPageChange: (page: number) => void;
    toolbar?: ReactNode;
}

export const TransactionsTable = ({
    transactions,
    loading,
    error,
    transactionsEmpty,
    emptyStateVariant,
    onClearFilters,
    onRowSelect,
    onSplitAction,
    categoryById,
    transactionsPage,
    totalPages,
    onPageChange,
    toolbar,
}: TransactionsTableProps) => {
    return (
        <TableCard.Root>
            <TableCard.Header
                title="Transactions"
                description="Click a row to review metadata. Use the split action to create or edit splits."
                contentTrailing={toolbar}
            />
            {loading ? (
                <div className="flex justify-center py-12">
                    <LoadingIndicator label="Loading transactions..." />
                </div>
            ) : error ? (
                <div className="px-6 pb-6 text-sm text-error-primary">{error}</div>
            ) : transactionsEmpty ? (
                <div className="px-6 pb-10">
                    <EmptyState>
                        <EmptyState.Header>
                            <EmptyState.FeaturedIcon icon={SearchLg} color="brand" />
                        </EmptyState.Header>
                        <EmptyState.Content>
                            <EmptyState.Title>
                                {emptyStateVariant === "filtered_empty" ? "No transactions match your filters" : "No transactions yet"}
                            </EmptyState.Title>
                            <EmptyState.Description>
                                {emptyStateVariant === "filtered_empty"
                                    ? "Try widening the filters or clear all filters."
                                    : "Import transactions to start categorizing and reviewing payees."}
                            </EmptyState.Description>
                        </EmptyState.Content>
                        {emptyStateVariant === "filtered_empty" ? (
                            <EmptyState.Footer>
                                <Button size="sm" color="secondary" onClick={onClearFilters}>
                                    Clear all filters
                                </Button>
                            </EmptyState.Footer>
                        ) : null}
                    </EmptyState>
                </div>
            ) : (
                <>
                    <Table aria-label="Ledger transactions">
                        <Table.Header columns={TRANSACTIONS_COLUMNS}>
                            {(column) => (
                                <Table.Head>
                                    <span className="text-xs font-semibold text-secondary">{column.name}</span>
                                </Table.Head>
                            )}
                        </Table.Header>
                        <Table.Body items={transactions}>
                            {(row) => (
                                <Table.Row id={String(row.id)} columns={TRANSACTIONS_COLUMNS} className="cursor-pointer" onAction={() => onRowSelect(row.id)}>
                                    {(column) => (
                                        <Table.Cell>
                                            {column.id === "date" && <span className="text-sm text-primary">{formatDate(row.posted_at)}</span>}
                                            {column.id === "label" && (
                                                <div className="flex flex-col gap-1">
                                                    <span className="text-sm font-medium text-primary">{row.label_raw || "Untitled"}</span>
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <span className="text-xs text-tertiary">{row.supplier_raw || row.payee?.name || "-"}</span>
                                                        {row.type !== "expense" ? (
                                                            <Badge size="sm" color="gray">
                                                                {formatTypeLabel(row.type)}
                                                            </Badge>
                                                        ) : null}
                                                    </div>
                                                </div>
                                            )}
                                            {column.id === "payee" && <span className="text-sm text-primary">{row.payee?.name || "Unassigned"}</span>}
                                            {column.id === "category" && (
                                                <>
                                                    {(() => {
                                                        const categoryCell = getCategoryCell(row, categoryById);
                                                        if (categoryCell.kind === "uncategorized") {
                                                            return (
                                                                <Badge size="sm" color="warning">
                                                                    {categoryCell.label}
                                                                </Badge>
                                                            );
                                                        }
                                                        if (categoryCell.kind === "split") {
                                                            return (
                                                                <Badge size="sm" color="gray">
                                                                    {categoryCell.label}
                                                                </Badge>
                                                            );
                                                        }
                                                        return <CategoryPill label={categoryCell.label} color={categoryCell.color} icon={categoryCell.icon} />;
                                                    })()}
                                                </>
                                            )}
                                            {column.id === "amount" && (
                                                <span className={cx("text-sm font-semibold", amountClass(row.amount))}>
                                                    {formatAmount(row.amount, row.currency)}
                                                </span>
                                            )}
                                            {column.id === "split_action" && (
                                                <Button
                                                    size="sm"
                                                    color="secondary"
                                                    onMouseDown={(event: MouseEvent<HTMLButtonElement>) => event.stopPropagation()}
                                                    onClick={(event: MouseEvent<HTMLButtonElement>) => {
                                                        event.stopPropagation();
                                                        onSplitAction(row.id);
                                                    }}
                                                >
                                                    {row.splits_count === 0 ? "Create split" : "Edit split"}
                                                </Button>
                                            )}
                                        </Table.Cell>
                                    )}
                                </Table.Row>
                            )}
                        </Table.Body>
                    </Table>
                    <div className="flex items-center justify-between gap-4 px-6 py-4">
                        <span className="text-xs text-tertiary">Showing {transactions.length} results</span>
                        <PaginationCardMinimal page={transactionsPage} total={totalPages} onPageChange={(page) => onPageChange(Math.max(1, page))} />
                    </div>
                </>
            )}
        </TableCard.Root>
    );
};

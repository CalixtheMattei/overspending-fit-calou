import { useMemo, type ReactNode } from "react";
import { SearchLg } from "@untitledui/icons";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { PaginationCardMinimal } from "@/components/application/pagination/pagination";
import { Table, TableCard } from "@/components/application/table/table";
import { Button } from "@/components/base/buttons/button";
import { getCategoryDisplayLabel } from "@/components/ledger/categories/category-visuals";
import type { MomentTaggedSplitRow } from "@/services/moments";
import { amountClass, formatAmount, formatDate } from "@/utils/format";

type TxGroupHeader = {
    type: "tx-header";
    transactionId: number;
    date: string;
    label: string;
    supplier: string | null | undefined;
    totalAmount: number;
};
type TaggedSplitItem = { type: "split-row" } & MomentTaggedSplitRow;
type RenderItem = TxGroupHeader | TaggedSplitItem;

const groupByTransaction = (rows: MomentTaggedSplitRow[]): RenderItem[] => {
    const order: number[] = [];
    const groups = new Map<number, MomentTaggedSplitRow[]>();
    for (const row of rows) {
        if (!groups.has(row.transaction_id)) {
            order.push(row.transaction_id);
            groups.set(row.transaction_id, []);
        }
        groups.get(row.transaction_id)!.push(row);
    }
    const result: RenderItem[] = [];
    for (const txId of order) {
        const splits = groups.get(txId)!;
        const first = splits[0];
        const totalAmount = splits.reduce((sum, s) => sum + Number(s.amount), 0);
        if (splits.length > 1) {
            result.push({
                type: "tx-header",
                transactionId: txId,
                date: first.operation_at,
                label: first.label_raw,
                supplier: first.supplier_raw,
                totalAmount,
            });
        }
        for (const split of splits) {
            result.push({ type: "split-row", ...split });
        }
    }
    return result;
};

const TAGGED_COLUMNS = [
    { id: "date", name: "Date" },
    { id: "label", name: "Label" },
    { id: "amount", name: "Amount" },
    { id: "category", name: "Category" },
    { id: "account", name: "Account" },
    { id: "action", name: "Action" },
] as const;

interface MomentTaggedTableProps {
    rows: MomentTaggedSplitRow[];
    loading: boolean;
    error: string | null;
    page: number;
    totalPages: number;
    selectedKeys: Set<string>;
    onPageChange: (page: number) => void;
    onSelectedKeysChange: (keys: Set<string>) => void;
    onOpenTransaction?: (transactionId: number) => void;
    bulkActionBar?: ReactNode;
}

const normalizeSelection = (selection: "all" | Set<string | number>, rows: MomentTaggedSplitRow[]) => {
    if (selection === "all") {
        return new Set(rows.map((row) => String(row.split_id)));
    }
    return new Set(Array.from(selection).map((key) => String(key)));
};

const getMomentCategoryLabel = (categoryName: string | null | undefined): string => {
    const name = categoryName?.trim();
    if (!name) return "Uncategorized";
    return getCategoryDisplayLabel({ name });
};

export const MomentTaggedTable = ({
    rows,
    loading,
    error,
    page,
    totalPages,
    selectedKeys,
    onPageChange,
    onSelectedKeysChange,
    onOpenTransaction,
    bulkActionBar,
}: MomentTaggedTableProps) => {
    const renderItems = useMemo(() => groupByTransaction(rows), [rows]);

    return (
        <TableCard.Root>
            <TableCard.Header title="Tagged Splits" description="Splits currently attached to this moment." />
            <div className="px-4 pt-4 md:px-6">{bulkActionBar}</div>
            {loading ? (
                <div className="flex justify-center py-12">
                    <LoadingIndicator label="Loading tagged rows..." />
                </div>
            ) : error ? (
                <div className="px-6 pb-6 text-sm text-error-primary">{error}</div>
            ) : rows.length === 0 ? (
                <div className="px-6 pb-10">
                    <EmptyState>
                        <EmptyState.Header>
                            <EmptyState.FeaturedIcon icon={SearchLg} color="brand" />
                        </EmptyState.Header>
                        <EmptyState.Content>
                            <EmptyState.Title>No tagged splits</EmptyState.Title>
                            <EmptyState.Description>This moment has no tagged split rows in the current filter context.</EmptyState.Description>
                        </EmptyState.Content>
                    </EmptyState>
                </div>
            ) : (
                <>
                    <Table
                        aria-label="Moment tagged splits"
                        selectionMode="multiple"
                        selectionBehavior="toggle"
                        selectedKeys={selectedKeys}
                        onSelectionChange={(selection) => onSelectedKeysChange(normalizeSelection(selection, rows))}
                    >
                        <Table.Header columns={TAGGED_COLUMNS}>
                            {(column) => (
                                <Table.Head>
                                    <span className="text-xs font-semibold text-secondary">{column.name}</span>
                                </Table.Head>
                            )}
                        </Table.Header>
                        <Table.Body items={renderItems}>
                            {(item) => {
                                if (item.type === "tx-header") {
                                    return (
                                        <Table.Row id={`tx-${item.transactionId}`} columns={TAGGED_COLUMNS} isDisabled>
                                            {(column) => (
                                                <Table.Cell>
                                                    {column.id === "date" && (
                                                        <span className="text-xs text-tertiary">{formatDate(item.date)}</span>
                                                    )}
                                                    {column.id === "label" && (
                                                        <div className="flex flex-col gap-0.5">
                                                            <span className="text-xs font-semibold text-secondary">{item.label || "Untitled"}</span>
                                                            {item.supplier ? <span className="text-xs text-quaternary">{item.supplier}</span> : null}
                                                        </div>
                                                    )}
                                                    {column.id === "amount" && (
                                                        <span className={`text-xs font-semibold ${amountClass(item.totalAmount)}`}>
                                                            {formatAmount(item.totalAmount)}
                                                        </span>
                                                    )}
                                                    {(column.id === "category" || column.id === "account" || column.id === "action") && null}
                                                </Table.Cell>
                                            )}
                                        </Table.Row>
                                    );
                                }
                                const row = item;
                                const isMultiSplit = renderItems.some((r) => r.type === "tx-header" && r.transactionId === row.transaction_id);
                                return (
                                    <Table.Row id={String(row.split_id)} columns={TAGGED_COLUMNS}>
                                        {(column) => (
                                            <Table.Cell>
                                                {column.id === "date" && (
                                                    isMultiSplit
                                                        ? <span className="text-xs text-tertiary pl-3">↳</span>
                                                        : <span className="text-sm text-primary">{formatDate(row.operation_at)}</span>
                                                )}
                                                {column.id === "label" && (
                                                    <div className={`flex flex-col gap-1 ${isMultiSplit ? "pl-3" : ""}`}>
                                                        {!isMultiSplit && <span className="text-sm font-medium text-primary">{row.label_raw || "Untitled"}</span>}
                                                        {!isMultiSplit && <span className="text-xs text-tertiary">{row.supplier_raw || "-"}</span>}
                                                        {isMultiSplit && <span className="text-xs text-tertiary">Split #{row.position ?? 1}</span>}
                                                    </div>
                                                )}
                                                {column.id === "amount" && (
                                                    <span className={`text-sm font-semibold ${amountClass(row.amount)}`}>
                                                        {formatAmount(row.amount, row.currency)}
                                                    </span>
                                                )}
                                                {column.id === "category" && (
                                                    <span className="text-sm text-primary">{getMomentCategoryLabel(row.category_name)}</span>
                                                )}
                                                {column.id === "account" && <span className="text-sm text-primary">{row.account_label || "-"}</span>}
                                                {column.id === "action" && (
                                                    <Button
                                                        size="sm"
                                                        color="secondary"
                                                        isDisabled={!onOpenTransaction}
                                                        onClick={() => onOpenTransaction?.(row.transaction_id)}
                                                    >
                                                        Open tx
                                                    </Button>
                                                )}
                                            </Table.Cell>
                                        )}
                                    </Table.Row>
                                );
                            }}
                        </Table.Body>
                    </Table>
                    <div className="flex items-center justify-between gap-4 px-6 py-4">
                        <span className="text-xs text-tertiary">Showing {rows.length} results</span>
                        <PaginationCardMinimal page={page} total={totalPages} onPageChange={(nextPage) => onPageChange(Math.max(1, nextPage))} />
                    </div>
                </>
            )}
        </TableCard.Root>
    );
};

import { useMemo, type ReactNode } from "react";
import { SearchLg } from "@untitledui/icons";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { PaginationCardMinimal } from "@/components/application/pagination/pagination";
import { Table, TableCard } from "@/components/application/table/table";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import type { MomentCandidateRow, MomentCandidateStatus } from "@/services/moments";
import { amountClass, formatAmount, formatDate } from "@/utils/format";

type TxGroupHeader = {
    type: "tx-header";
    transactionId: number;
    date: string;
    label: string;
    supplier: string | null | undefined;
    totalAmount: number;
};
type SplitItem = { type: "split-row" } & MomentCandidateRow;
type RenderItem = TxGroupHeader | SplitItem;

const groupByTransaction = (rows: MomentCandidateRow[]): RenderItem[] => {
    const order: number[] = [];
    const groups = new Map<number, MomentCandidateRow[]>();
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

const CANDIDATE_COLUMNS = [
    { id: "date", name: "Date" },
    { id: "label", name: "Label" },
    { id: "amount", name: "Amount" },
    { id: "status", name: "Status" },
    { id: "action", name: "Action" },
] as const;

interface MomentCandidatesTableProps {
    rows: MomentCandidateRow[];
    loading: boolean;
    error: string | null;
    page: number;
    totalPages: number;
    selectedKeys: Set<string>;
    statusFilter: "all" | MomentCandidateStatus;
    actionBusy: boolean;
    onPageChange: (page: number) => void;
    onSelectedKeysChange: (keys: Set<string>) => void;
    onDecideSplit: (splitId: number, decision: "accepted" | "rejected") => void;
    onOpenTransactionSplit?: (transactionId: number) => void;
    bulkActionBar?: ReactNode;
}

const normalizeSelection = (selection: "all" | Set<string | number>, rows: MomentCandidateRow[]) => {
    if (selection === "all") {
        return new Set(rows.map((row) => String(row.split_id)));
    }
    return new Set(Array.from(selection).map((key) => String(key)));
};

const getStatusColor = (status: MomentCandidateStatus) => {
    if (status === "accepted") return "success";
    if (status === "rejected") return "error";
    return "warning";
};

export const MomentCandidatesTable = ({
    rows,
    loading,
    error,
    page,
    totalPages,
    selectedKeys,
    statusFilter,
    actionBusy,
    onPageChange,
    onSelectedKeysChange,
    onDecideSplit,
    onOpenTransactionSplit,
    bulkActionBar,
}: MomentCandidatesTableProps) => {
    const renderItems = useMemo(() => groupByTransaction(rows), [rows]);

    return (
        <TableCard.Root>
            <TableCard.Header title="Candidate Rows" description="Review and confirm candidate splits for this moment." />
            <div className="px-4 pt-4 md:px-6">{bulkActionBar}</div>
            {loading ? (
                <div className="flex justify-center py-12">
                    <LoadingIndicator label="Loading candidates..." />
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
                            <EmptyState.Title>No candidates</EmptyState.Title>
                            <EmptyState.Description>
                                {statusFilter === "all"
                                    ? "No candidate rows are available for this moment."
                                    : `No ${statusFilter} candidate rows for this moment.`}
                            </EmptyState.Description>
                        </EmptyState.Content>
                    </EmptyState>
                </div>
            ) : (
                <>
                    <Table
                        aria-label="Moment candidates"
                        selectionMode="multiple"
                        selectionBehavior="toggle"
                        selectedKeys={selectedKeys}
                        onSelectionChange={(selection) => onSelectedKeysChange(normalizeSelection(selection, rows))}
                    >
                        <Table.Header columns={CANDIDATE_COLUMNS}>
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
                                        <Table.Row id={`tx-${item.transactionId}`} columns={CANDIDATE_COLUMNS} isDisabled>
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
                                                    {(column.id === "status" || column.id === "action") && null}
                                                </Table.Cell>
                                            )}
                                        </Table.Row>
                                    );
                                }
                                const row = item;
                                const isMultiSplit = renderItems.some((r) => r.type === "tx-header" && r.transactionId === row.transaction_id);
                                return (
                                    <Table.Row id={String(row.split_id)} columns={CANDIDATE_COLUMNS}>
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
                                                {column.id === "status" && (
                                                    <Badge color={getStatusColor(row.status)} size="sm">
                                                        {row.status}
                                                    </Badge>
                                                )}
                                                {column.id === "action" && (
                                                    <div className="flex gap-1.5">
                                                        <Button
                                                            size="sm"
                                                            color="secondary"
                                                            isDisabled={actionBusy}
                                                            onClick={() => onDecideSplit(row.split_id, "accepted")}
                                                        >
                                                            Accept
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            color="secondary-destructive"
                                                            isDisabled={actionBusy}
                                                            onClick={() => onDecideSplit(row.split_id, "rejected")}
                                                        >
                                                            Reject
                                                        </Button>
                                                        {onOpenTransactionSplit && (
                                                            <Button
                                                                size="sm"
                                                                color="tertiary"
                                                                onClick={() => onOpenTransactionSplit(row.transaction_id)}
                                                            >
                                                                Edit splits
                                                            </Button>
                                                        )}
                                                    </div>
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

import { useCallback, useEffect, useMemo, useState } from "react";
import { parseDate, toCalendarDate } from "@internationalized/date";
import { ArrowLeft } from "@untitledui/icons";
import type { DateValue } from "react-aria-components";
import type { ListData } from "react-stately";
import { useListData } from "react-stately";
import { Link, useParams, useSearchParams } from "react-router";
import { DateRangePicker } from "@/components/application/date-picker/date-range-picker";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { MultiSelect } from "@/components/base/select/multi-select";
import type { SelectItemType } from "@/components/base/select/select";
import {
    SANKEY_PRESET_OPTIONS_WITH_TODAY,
    getPresetDateRange,
} from "@/features/analytics/filters";
import { SankeyChart } from "@/components/ledger/charts/sankey-chart";
import { buildSankeyData } from "@/components/ledger/charts/sankey-utils";
import { amountClass, formatAmount, formatDate } from "@/utils/format";
import type { CategoryDrilldownResponse, DrilldownTransactionRow } from "@/services/analytics";
import { fetchCategoryDrilldown, fetchCategoryDrilldownTransactions } from "@/services/analytics";

const PAGE_SIZE = 50;

type DateRangeValue = { start: DateValue; end: DateValue };

const toDateRangeValue = (start: string | undefined, end: string | undefined): DateRangeValue | null => {
    if (!start || !end) return null;
    try {
        return { start: parseDate(start), end: parseDate(end) };
    } catch {
        return null;
    }
};

const clearMultiSelect = (selectedItems: ListData<SelectItemType>) => {
    const keys = selectedItems.items.map((item) => String(item.id));
    keys.forEach((key) => selectedItems.remove(key));
};

const syncMultiSelectItems = (selectedItems: ListData<SelectItemType>, options: SelectItemType[]) => {
    const validIds = new Set(options.map((option) => option.id));
    const staleIds = selectedItems.items.map((item) => String(item.id)).filter((id) => !validIds.has(id));
    staleIds.forEach((id) => selectedItems.remove(id));
};

const normalizeTextFilterValue = (value: string | null) => (value && value.trim().length > 0 ? value : "Unknown");

export const CategoryDrilldownPage = () => {
    const { categoryRef } = useParams<{ categoryRef: string }>();
    const [searchParams, setSearchParams] = useSearchParams();

    const startDate = searchParams.get("start_date") ?? undefined;
    const endDate = searchParams.get("end_date") ?? undefined;
    const excludeTransfers = searchParams.get("exclude_transfers") !== "false";
    const excludeMomentTagged = searchParams.get("exclude_moment_tagged") === "true";
    const from = searchParams.get("from") ?? "analytics";

    const [drilldown, setDrilldown] = useState<CategoryDrilldownResponse | null>(null);
    const [rows, setRows] = useState<DrilldownTransactionRow[]>([]);
    const [totalRows, setTotalRows] = useState(0);
    const [offset, setOffset] = useState(0);
    const [loading, setLoading] = useState(true);
    const [txLoading, setTxLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [filtersModalOpen, setFiltersModalOpen] = useState(false);
    const [dateRangeDraft, setDateRangeDraft] = useState<DateRangeValue | null>(() => toDateRangeValue(startDate, endDate));
    const [activePresetId, setActivePresetId] = useState<string | null>(null);

    const selectedTypeItems = useListData<SelectItemType>({ initialItems: [] });
    const selectedPayeeItems = useListData<SelectItemType>({ initialItems: [] });
    const selectedAccountItems = useListData<SelectItemType>({ initialItems: [] });

    useEffect(() => {
        setDateRangeDraft(toDateRangeValue(startDate, endDate));
    }, [startDate, endDate]);

    const applyGlobalFilters = useCallback(
        (next: { startDate?: string; endDate?: string; excludeTransfers?: boolean; excludeMomentTagged?: boolean }) => {
            const nextParams = new URLSearchParams(searchParams);

            if (next.startDate) {
                nextParams.set("start_date", next.startDate);
            } else {
                nextParams.delete("start_date");
            }

            if (next.endDate) {
                nextParams.set("end_date", next.endDate);
            } else {
                nextParams.delete("end_date");
            }

            if (next.excludeTransfers !== undefined) {
                nextParams.set("exclude_transfers", String(next.excludeTransfers));
            }

            if (next.excludeMomentTagged !== undefined) {
                nextParams.set("exclude_moment_tagged", String(next.excludeMomentTagged));
            }

            setSearchParams(nextParams, { replace: true });
        },
        [searchParams, setSearchParams],
    );

    const handlePresetChange = (presetId: string) => {
        setActivePresetId(presetId);
        const range = getPresetDateRange(presetId as "7D" | "1M" | "3M" | "6M" | "TODAY");
        applyGlobalFilters({ startDate: range.start, endDate: range.end });
    };

    const handleApplyDateRange = () => {
        if (!dateRangeDraft) return;
        const start = toCalendarDate(dateRangeDraft.start).toString();
        const end = toCalendarDate(dateRangeDraft.end).toString();
        applyGlobalFilters({ startDate: start, endDate: end });
        setActivePresetId(null);
    };

    const handleResetAll = () => {
        const range = getPresetDateRange("3M");
        applyGlobalFilters({
            startDate: range.start,
            endDate: range.end,
            excludeTransfers: true,
            excludeMomentTagged: false,
        });
        clearMultiSelect(selectedTypeItems);
        clearMultiSelect(selectedPayeeItems);
        clearMultiSelect(selectedAccountItems);
        setActivePresetId("3M");
    };

    const filterParams = {
        start_date: startDate,
        end_date: endDate,
        exclude_transfers: excludeTransfers,
        exclude_moment_tagged: excludeMomentTagged,
    };

    useEffect(() => {
        if (!categoryRef) return;
        let active = true;
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const [dd, tx] = await Promise.all([
                    fetchCategoryDrilldown(categoryRef, filterParams),
                    fetchCategoryDrilldownTransactions(categoryRef, {
                        ...filterParams,
                        limit: PAGE_SIZE,
                        offset: 0,
                    }),
                ]);
                if (!active) return;
                setDrilldown(dd);
                setRows(tx.rows);
                setTotalRows(tx.total);
                setOffset(0);
            } catch (err) {
                if (!active) return;
                setError(err instanceof Error ? err.message : "Failed to load drilldown data.");
            } finally {
                if (active) setLoading(false);
            }
        };
        load();
        return () => {
            active = false;
        };
    }, [categoryRef, startDate, endDate, excludeTransfers, excludeMomentTagged]);

    const loadMore = useCallback(async () => {
        if (!categoryRef || txLoading) return;
        const nextOffset = offset + PAGE_SIZE;
        setTxLoading(true);
        try {
            const tx = await fetchCategoryDrilldownTransactions(categoryRef, {
                ...filterParams,
                limit: PAGE_SIZE,
                offset: nextOffset,
            });
            setRows((prev) => [...prev, ...tx.rows]);
            setOffset(nextOffset);
        } catch {
            // Silently fail pagination.
        } finally {
            setTxLoading(false);
        }
    }, [categoryRef, offset, txLoading, startDate, endDate, excludeTransfers, excludeMomentTagged]);

    const typeOptions = useMemo<SelectItemType[]>(() => {
        return Array.from(new Set(rows.map((row) => row.type).filter((value) => value && value.length > 0)))
            .sort((a, b) => a.localeCompare(b))
            .map((value) => ({ id: value, label: value }));
    }, [rows]);

    const payeeOptions = useMemo<SelectItemType[]>(() => {
        return Array.from(new Set(rows.map((row) => normalizeTextFilterValue(row.payee))))
            .sort((a, b) => a.localeCompare(b))
            .map((value) => ({ id: `payee:${value}`, label: value }));
    }, [rows]);

    const accountOptions = useMemo<SelectItemType[]>(() => {
        return Array.from(new Set(rows.map((row) => normalizeTextFilterValue(row.account))))
            .sort((a, b) => a.localeCompare(b))
            .map((value) => ({ id: `account:${value}`, label: value }));
    }, [rows]);

    useEffect(() => {
        syncMultiSelectItems(selectedTypeItems, typeOptions);
    }, [selectedTypeItems, typeOptions]);

    useEffect(() => {
        syncMultiSelectItems(selectedPayeeItems, payeeOptions);
    }, [selectedPayeeItems, payeeOptions]);

    useEffect(() => {
        syncMultiSelectItems(selectedAccountItems, accountOptions);
    }, [selectedAccountItems, accountOptions]);

    const selectedTypes = useMemo(
        () => new Set(selectedTypeItems.items.map((item) => String(item.id))),
        [selectedTypeItems.items],
    );
    const selectedPayees = useMemo(
        () => new Set(selectedPayeeItems.items.map((item) => String(item.id).replace(/^payee:/, ""))),
        [selectedPayeeItems.items],
    );
    const selectedAccounts = useMemo(
        () => new Set(selectedAccountItems.items.map((item) => String(item.id).replace(/^account:/, ""))),
        [selectedAccountItems.items],
    );

    const filteredRows = useMemo(() => {
        return rows.filter((row) => {
            if (selectedTypes.size > 0 && !selectedTypes.has(row.type)) {
                return false;
            }

            const payeeLabel = normalizeTextFilterValue(row.payee);
            if (selectedPayees.size > 0 && !selectedPayees.has(payeeLabel)) {
                return false;
            }

            const accountLabel = normalizeTextFilterValue(row.account);
            if (selectedAccounts.size > 0 && !selectedAccounts.has(accountLabel)) {
                return false;
            }

            return true;
        });
    }, [rows, selectedTypes, selectedPayees, selectedAccounts]);

    const backHref = from === "ledger" ? "/ledger" : "/analytics";

    const sankeyData =
        drilldown && drilldown.branch_nodes.length > 0 && drilldown.branch_links.length > 0
            ? buildSankeyData(
                  {
                      nodes: drilldown.branch_nodes,
                      links: drilldown.branch_links,
                      totals: { income: 0, expenses: 0, refunds: 0, transfers: 0 },
                  },
                  {
                      hiddenCategoryIds: new Set<string>(),
                      hiddenTypeIds: new Set<string>(),
                  },
              )
            : null;

    if (loading) {
        return (
            <section className="flex flex-1 items-center justify-center">
                <LoadingIndicator label="Loading category drilldown..." />
            </section>
        );
    }

    if (error || !drilldown) {
        return (
            <section className="flex flex-1 flex-col gap-4 p-6">
                <Link to={backHref} className="inline-flex items-center gap-1.5 text-sm text-tertiary hover:text-primary">
                    <ArrowLeft className="size-4" /> Back
                </Link>
                <div className="rounded-2xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                    {error ?? "Category not found."}
                </div>
            </section>
        );
    }

    const { totals, transaction_count, category } = drilldown;

    return (
        <section className="relative flex flex-1 flex-col gap-6 pb-24">
            <header className="flex flex-col gap-2">
                <Link to={backHref} className="inline-flex items-center gap-1.5 text-sm text-tertiary hover:text-primary">
                    <ArrowLeft className="size-4" /> Back to {from === "ledger" ? "Ledger" : "Analytics"}
                </Link>
                <h1 className="text-2xl font-semibold text-primary">{category.name}</h1>
                <div className="flex flex-wrap items-center gap-2 text-xs text-tertiary">
                    {startDate && (
                        <Badge size="sm" color="gray">
                            From {startDate}
                        </Badge>
                    )}
                    {endDate && (
                        <Badge size="sm" color="gray">
                            To {endDate}
                        </Badge>
                    )}
                    {excludeTransfers && (
                        <Badge size="sm" color="gray">
                            Excl. transfers
                        </Badge>
                    )}
                    {excludeMomentTagged && (
                        <Badge size="sm" color="gray">
                            Excl. moment-tagged
                        </Badge>
                    )}
                </div>
            </header>

            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <div className="rounded-xl bg-primary p-4 shadow-xs ring-1 ring-secondary">
                    <p className="text-xs text-tertiary">Expenses</p>
                    <p className="text-lg font-semibold text-primary">{formatAmount(totals.expense_abs)}</p>
                </div>
                <div className="rounded-xl bg-primary p-4 shadow-xs ring-1 ring-secondary">
                    <p className="text-xs text-tertiary">Income</p>
                    <p className="text-lg font-semibold text-primary">{formatAmount(totals.income_abs)}</p>
                </div>
                <div className="rounded-xl bg-primary p-4 shadow-xs ring-1 ring-secondary">
                    <p className="text-xs text-tertiary">Refunds</p>
                    <p className="text-lg font-semibold text-primary">{formatAmount(totals.refund_abs)}</p>
                </div>
                <div className="rounded-xl bg-primary p-4 shadow-xs ring-1 ring-secondary">
                    <p className="text-xs text-tertiary">Transactions</p>
                    <p className="text-lg font-semibold text-primary">{transaction_count}</p>
                </div>
            </div>

            {sankeyData && sankeyData.nodes.length > 1 && (
                <div className="rounded-2xl bg-primary p-4 shadow-xs ring-1 ring-secondary">
                    <h2 className="mb-3 text-sm font-medium text-primary">Category branch flow</h2>
                    <SankeyChart data={sankeyData} height={250} />
                </div>
            )}

            <div className="rounded-2xl bg-primary shadow-xs ring-1 ring-secondary">
                <div className="border-b border-secondary px-4 py-3 md:px-6">
                    <h2 className="text-sm font-medium text-primary">Impacted transactions ({totalRows})</h2>
                    {(selectedTypes.size > 0 || selectedPayees.size > 0 || selectedAccounts.size > 0) && (
                        <p className="mt-1 text-xs text-tertiary">Showing {filteredRows.length} loaded rows after local filters.</p>
                    )}
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                        <thead>
                            <tr className="border-b border-secondary text-xs text-tertiary">
                                <th className="px-4 py-2 font-medium">Date</th>
                                <th className="px-4 py-2 font-medium">Label</th>
                                <th className="px-4 py-2 font-medium">Payee</th>
                                <th className="px-4 py-2 font-medium">Account</th>
                                <th className="px-4 py-2 font-medium">Type</th>
                                <th className="px-4 py-2 font-medium text-right">Amount</th>
                                <th className="px-4 py-2 font-medium text-right">Branch</th>
                                <th className="px-4 py-2 font-medium text-right">Splits</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filteredRows.map((row) => (
                                <tr
                                    key={`${row.transaction_id}-${row.posted_at}`}
                                    className="border-b border-secondary last:border-b-0"
                                >
                                    <td className="whitespace-nowrap px-4 py-2 text-tertiary">{formatDate(row.posted_at)}</td>
                                    <td className="max-w-[200px] truncate px-4 py-2 text-primary">{row.label_raw}</td>
                                    <td className="px-4 py-2 text-secondary">{row.payee ?? "-"}</td>
                                    <td className="px-4 py-2 text-secondary">{row.account ?? "-"}</td>
                                    <td className="px-4 py-2 text-secondary">{row.type}</td>
                                    <td className={`whitespace-nowrap px-4 py-2 text-right ${amountClass(row.transaction_amount)}`}>
                                        {formatAmount(row.transaction_amount)}
                                    </td>
                                    <td className="whitespace-nowrap px-4 py-2 text-right text-primary">
                                        {formatAmount(row.branch_amount_abs)}
                                    </td>
                                    <td className="px-4 py-2 text-right text-tertiary">{row.matched_split_count}</td>
                                </tr>
                            ))}
                            {filteredRows.length === 0 && (
                                <tr>
                                    <td colSpan={8} className="px-4 py-8 text-center text-sm text-tertiary">
                                        No transactions found.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
                {rows.length < totalRows && (
                    <div className="flex justify-center border-t border-secondary px-4 py-3">
                        <Button color="tertiary" size="sm" isDisabled={txLoading} onClick={loadMore}>
                            {txLoading ? "Loading..." : `Load more (${rows.length} / ${totalRows})`}
                        </Button>
                    </div>
                )}
            </div>

            <div className="fixed right-6 bottom-6 z-30">
                <Button size="md" color="primary" onClick={() => setFiltersModalOpen(true)}>
                    Filters
                </Button>
            </div>

            <ModalOverlay isOpen={filtersModalOpen} onOpenChange={setFiltersModalOpen}>
                <Modal>
                    <Dialog className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex w-full flex-col gap-5">
                            <header className="space-y-1">
                                <h2 className="text-lg font-semibold text-primary">Drilldown filters</h2>
                                <p className="text-sm text-tertiary">Global analytics filters plus local table filters for this screen.</p>
                            </header>

                            <section className="space-y-3 rounded-xl bg-secondary/40 p-4 ring-1 ring-secondary">
                                <h3 className="text-sm font-semibold text-primary">Date range</h3>
                                <div className="flex flex-wrap items-center gap-2">
                                    {SANKEY_PRESET_OPTIONS_WITH_TODAY.map((preset) => (
                                        <Button
                                            key={preset.id}
                                            size="sm"
                                            color={activePresetId === preset.id ? "secondary" : "tertiary"}
                                            onClick={() => handlePresetChange(preset.id)}
                                        >
                                            {preset.label}
                                        </Button>
                                    ))}
                                </div>
                                <DateRangePicker
                                    value={dateRangeDraft}
                                    onChange={setDateRangeDraft}
                                    onApply={handleApplyDateRange}
                                    onCancel={() => setDateRangeDraft(toDateRangeValue(startDate, endDate))}
                                />
                                <div className="flex flex-wrap gap-2">
                                    <Button
                                        size="sm"
                                        color={excludeTransfers ? "secondary" : "tertiary"}
                                        onClick={() =>
                                            applyGlobalFilters({
                                                startDate,
                                                endDate,
                                                excludeTransfers: !excludeTransfers,
                                                excludeMomentTagged,
                                            })
                                        }
                                    >
                                        {excludeTransfers ? "Transfers excluded" : "Transfers included"}
                                    </Button>
                                    <Button
                                        size="sm"
                                        color={excludeMomentTagged ? "secondary" : "tertiary"}
                                        onClick={() =>
                                            applyGlobalFilters({
                                                startDate,
                                                endDate,
                                                excludeTransfers,
                                                excludeMomentTagged: !excludeMomentTagged,
                                            })
                                        }
                                    >
                                        {excludeMomentTagged ? "Moment-tagged excluded" : "Moment-tagged included"}
                                    </Button>
                                </div>
                            </section>

                            <section className="space-y-3 rounded-xl bg-secondary/40 p-4 ring-1 ring-secondary">
                                <h3 className="text-sm font-semibold text-primary">Local table filters</h3>
                                <div className="grid gap-3 md:grid-cols-2">
                                    <MultiSelect
                                        aria-label="Filter transactions by type"
                                        label="Types"
                                        items={typeOptions}
                                        selectedItems={selectedTypeItems}
                                        placeholder="All types"
                                    >
                                        {(item) => <MultiSelect.Item id={item.id} label={item.label} />}
                                    </MultiSelect>
                                    <MultiSelect
                                        aria-label="Filter transactions by payee"
                                        label="Payees"
                                        items={payeeOptions}
                                        selectedItems={selectedPayeeItems}
                                        placeholder="All payees"
                                    >
                                        {(item) => <MultiSelect.Item id={item.id} label={item.label} />}
                                    </MultiSelect>
                                    <MultiSelect
                                        aria-label="Filter transactions by account"
                                        label="Accounts"
                                        items={accountOptions}
                                        selectedItems={selectedAccountItems}
                                        placeholder="All accounts"
                                    >
                                        {(item) => <MultiSelect.Item id={item.id} label={item.label} />}
                                    </MultiSelect>
                                </div>
                            </section>

                            <footer className="flex items-center justify-end gap-2 border-t border-secondary pt-3">
                                <Button color="tertiary" onClick={handleResetAll}>
                                    Reset all
                                </Button>
                                <Button color="primary" onClick={() => setFiltersModalOpen(false)}>
                                    Done
                                </Button>
                            </footer>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </section>
    );
};

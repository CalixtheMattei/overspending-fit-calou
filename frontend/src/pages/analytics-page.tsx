import { useEffect, useMemo, useState } from "react";
import { parseDate, toCalendarDate } from "@internationalized/date";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DateValue } from "react-aria-components";
import type { ListData } from "react-stately";
import { useListData } from "react-stately";
import { DateRangePicker } from "@/components/application/date-picker/date-range-picker";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Button } from "@/components/base/buttons/button";
import { MultiSelect } from "@/components/base/select/multi-select";
import { Select, type SelectItemType } from "@/components/base/select/select";
import {
    GRANULARITY_OPTIONS,
    MODE_OPTIONS,
    SANKEY_PRESET_OPTIONS_WITH_TODAY,
    getPresetDateRange,
} from "@/features/analytics/filters";
import { useAnalyticsFilters } from "@/features/analytics/use-analytics-filters";
import type {
    AnalyticsGranularity,
    AnalyticsGroupedResponse,
    AnalyticsMode,
    FlowResponse,
} from "@/services/analytics";
import {
    fetchAnalyticsFlow,
    fetchAnalyticsInternalAccounts,
    fetchAnalyticsPayees,
} from "@/services/analytics";
import { amountClass, formatAmount, formatDate } from "@/utils/format";

type DateRangeValue = { start: DateValue; end: DateValue };

const TOP_ROWS_DISPLAY_LIMIT = 8;
const ENTITY_FILTER_FETCH_LIMIT = 200;
const VALID_SANKEY_PRESET_IDS = new Set<string>(SANKEY_PRESET_OPTIONS_WITH_TODAY.map((option) => option.id));

const toDateRangeValue = (start: string, end: string): DateRangeValue | null => {
    if (!start || !end) return null;
    try {
        return { start: parseDate(start), end: parseDate(end) };
    } catch {
        return null;
    }
};

const buildEntityFilterId = (scope: "payee" | "internal-account", entityId: number | null, entityName: string) => {
    return `${scope}:${entityId ?? "null"}:${entityName}`;
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

export const AnalyticsPage = () => {
    const {
        filters,
        setGranularity,
        setMode,
        setExcludeTransfers,
        setExcludeMomentTagged,
        applyPreset,
        applyCustomRange,
        reset,
    } = useAnalyticsFilters({ syncWithUrl: true });

    const { startDate, endDate, granularity, mode, excludeTransfers, excludeMomentTagged } = filters;

    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [flowData, setFlowData] = useState<FlowResponse | null>(null);
    const [payeeData, setPayeeData] = useState<AnalyticsGroupedResponse | null>(null);
    const [internalAccountData, setInternalAccountData] = useState<AnalyticsGroupedResponse | null>(null);

    const [filtersModalOpen, setFiltersModalOpen] = useState(false);
    const [dateRangeDraft, setDateRangeDraft] = useState<DateRangeValue | null>(() => toDateRangeValue(startDate, endDate));
    const [activePresetId, setActivePresetId] = useState<string | null>(() =>
        filters.presetId && VALID_SANKEY_PRESET_IDS.has(filters.presetId) ? filters.presetId : null,
    );

    const selectedSpendCategoryItems = useListData<SelectItemType>({ initialItems: [] });
    const selectedPayeeItems = useListData<SelectItemType>({ initialItems: [] });
    const selectedInternalAccountItems = useListData<SelectItemType>({ initialItems: [] });

    useEffect(() => {
        setDateRangeDraft(toDateRangeValue(startDate, endDate));
    }, [startDate, endDate]);

    useEffect(() => {
        if (filters.presetId && VALID_SANKEY_PRESET_IDS.has(filters.presetId)) {
            setActivePresetId(filters.presetId);
            return;
        }
        setActivePresetId(null);
    }, [filters.presetId]);

    useEffect(() => {
        let isActive = true;
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const [flow, payees, internalAccounts] = await Promise.all([
                    fetchAnalyticsFlow({
                        start_date: startDate,
                        end_date: endDate,
                        exclude_transfers: excludeTransfers,
                        exclude_moment_tagged: excludeMomentTagged,
                    }),
                    fetchAnalyticsPayees({
                        start_date: startDate,
                        end_date: endDate,
                        granularity,
                        mode,
                        exclude_transfers: excludeTransfers,
                        exclude_moment_tagged: excludeMomentTagged,
                        limit: ENTITY_FILTER_FETCH_LIMIT,
                    }),
                    fetchAnalyticsInternalAccounts({
                        start_date: startDate,
                        end_date: endDate,
                        granularity,
                        mode,
                        exclude_transfers: excludeTransfers,
                        exclude_moment_tagged: excludeMomentTagged,
                        limit: ENTITY_FILTER_FETCH_LIMIT,
                    }),
                ]);
                if (!isActive) return;
                setFlowData(flow);
                setPayeeData(payees);
                setInternalAccountData(internalAccounts);
            } catch (loadError) {
                if (!isActive) return;
                setError(loadError instanceof Error ? loadError.message : "Failed to load analytics.");
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };

        load();

        return () => {
            isActive = false;
        };
    }, [startDate, endDate, granularity, mode, excludeTransfers, excludeMomentTagged]);

    const spendByCategory = useMemo(() => {
        if (!flowData) return [];
        const nodeNames = new Map(flowData.nodes.map((node) => [node.id, node.name]));
        const totals = new Map<string, number>();
        for (const link of flowData.links) {
            if (link.source !== "expense") continue;
            const label = nodeNames.get(link.target) ?? link.target;
            totals.set(label, (totals.get(label) ?? 0) + link.value);
        }
        return Array.from(totals.entries())
            .map(([name, value]) => ({ name, value }))
            .sort((a, b) => b.value - a.value);
    }, [flowData]);

    const spendCategoryOptions = useMemo<SelectItemType[]>(
        () => spendByCategory.map((entry) => ({ id: entry.name, label: entry.name })),
        [spendByCategory],
    );

    const payeeOptions = useMemo<SelectItemType[]>(
        () =>
            (payeeData?.rows ?? []).map((row) => ({
                id: buildEntityFilterId("payee", row.entity_id, row.entity_name),
                label: row.entity_name,
            })),
        [payeeData],
    );

    const internalAccountOptions = useMemo<SelectItemType[]>(
        () =>
            (internalAccountData?.rows ?? []).map((row) => ({
                id: buildEntityFilterId("internal-account", row.entity_id, row.entity_name),
                label: row.entity_name,
            })),
        [internalAccountData],
    );

    useEffect(() => {
        syncMultiSelectItems(selectedSpendCategoryItems, spendCategoryOptions);
    }, [selectedSpendCategoryItems, spendCategoryOptions]);

    useEffect(() => {
        syncMultiSelectItems(selectedPayeeItems, payeeOptions);
    }, [selectedPayeeItems, payeeOptions]);

    useEffect(() => {
        syncMultiSelectItems(selectedInternalAccountItems, internalAccountOptions);
    }, [selectedInternalAccountItems, internalAccountOptions]);

    const selectedSpendCategoryIds = useMemo(
        () => new Set(selectedSpendCategoryItems.items.map((item) => String(item.id))),
        [selectedSpendCategoryItems.items],
    );
    const selectedPayeeIds = useMemo(
        () => new Set(selectedPayeeItems.items.map((item) => String(item.id))),
        [selectedPayeeItems.items],
    );
    const selectedInternalAccountIds = useMemo(
        () => new Set(selectedInternalAccountItems.items.map((item) => String(item.id))),
        [selectedInternalAccountItems.items],
    );

    const filteredSpendByCategory = useMemo(() => {
        if (selectedSpendCategoryIds.size === 0) return spendByCategory;
        return spendByCategory.filter((entry) => selectedSpendCategoryIds.has(entry.name));
    }, [spendByCategory, selectedSpendCategoryIds]);

    const filteredPayeeRows = useMemo(() => {
        const rows = payeeData?.rows ?? [];
        if (selectedPayeeIds.size === 0) return rows;
        return rows.filter((row) => selectedPayeeIds.has(buildEntityFilterId("payee", row.entity_id, row.entity_name)));
    }, [payeeData, selectedPayeeIds]);

    const filteredInternalAccountRows = useMemo(() => {
        const rows = internalAccountData?.rows ?? [];
        if (selectedInternalAccountIds.size === 0) return rows;
        return rows.filter((row) =>
            selectedInternalAccountIds.has(buildEntityFilterId("internal-account", row.entity_id, row.entity_name)),
        );
    }, [internalAccountData, selectedInternalAccountIds]);

    const visiblePayeeRows = useMemo(
        () => filteredPayeeRows.slice(0, TOP_ROWS_DISPLAY_LIMIT),
        [filteredPayeeRows],
    );
    const visibleInternalAccountRows = useMemo(
        () => filteredInternalAccountRows.slice(0, TOP_ROWS_DISPLAY_LIMIT),
        [filteredInternalAccountRows],
    );

    const maxSpend = filteredSpendByCategory[0]?.value ?? 0;
    const netSeries = payeeData?.series_totals ?? [];
    const totals = flowData?.totals;
    const netTotal = payeeData?.totals.net ?? 0;

    const handlePresetChange = (presetId: string) => {
        setActivePresetId(presetId);
        if (presetId === "TODAY") {
            const todayRange = getPresetDateRange("TODAY");
            applyCustomRange(todayRange.start, todayRange.end);
            return;
        }
        applyPreset(presetId as "7D" | "1M" | "3M" | "6M");
    };

    const handleApplyDateRange = () => {
        if (!dateRangeDraft) return;
        const start = toCalendarDate(dateRangeDraft.start).toString();
        const end = toCalendarDate(dateRangeDraft.end).toString();
        applyCustomRange(start, end);
        setActivePresetId(null);
    };

    const handleResetAll = () => {
        reset();
        clearMultiSelect(selectedSpendCategoryItems);
        clearMultiSelect(selectedPayeeItems);
        clearMultiSelect(selectedInternalAccountItems);
    };

    return (
        <section className="relative flex flex-1 flex-col gap-8 pb-24">
            <header className="flex flex-col gap-2">
                <h1 className="text-2xl font-semibold text-primary">Analytics</h1>
                <p className="text-sm text-tertiary">
                    Split-based analytics with coherent flow totals and optional counterparty sign projection.
                </p>
            </header>

            {loading ? (
                <div className="flex justify-center py-20">
                    <LoadingIndicator label="Loading analytics..." />
                </div>
            ) : error ? (
                <div className="rounded-xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">{error}</div>
            ) : (
                <>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <SummaryCard label="Income" value={totals?.income ?? 0} supporting="Flow totals" />
                        <SummaryCard label="Expenses" value={totals?.expenses ?? 0} supporting="Flow totals" />
                        <SummaryCard label="Refunds" value={totals?.refunds ?? 0} supporting="Flow totals" />
                        <SummaryCard label="Net cashflow" value={netTotal} supporting="Time series aggregate" />
                    </div>

                    <div className="grid gap-6 lg:grid-cols-2">
                        <div className="rounded-2xl bg-primary p-5 shadow-xs ring-1 ring-secondary">
                            <h2 className="text-base font-semibold text-primary">Spend by category</h2>
                            <p className="mt-1 text-xs text-tertiary">Split-based expense totals for selected filters.</p>
                            <div className="mt-4 flex flex-col gap-3">
                                {filteredSpendByCategory.length === 0 ? (
                                    <span className="text-sm text-tertiary">No expense splits for this period.</span>
                                ) : (
                                    filteredSpendByCategory.slice(0, 8).map((entry) => {
                                        const width = maxSpend > 0 ? Math.max(8, (entry.value / maxSpend) * 100) : 0;
                                        return (
                                            <div key={entry.name} className="flex flex-col gap-1">
                                                <div className="flex items-center justify-between gap-3 text-sm">
                                                    <span className="truncate text-primary">{entry.name}</span>
                                                    <span className="font-medium text-primary">{formatAmount(entry.value)}</span>
                                                </div>
                                                <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
                                                    <div className="h-full rounded-full bg-brand-solid" style={{ width: `${width}%` }} />
                                                </div>
                                            </div>
                                        );
                                    })
                                )}
                            </div>
                        </div>

                        <div className="rounded-2xl bg-primary p-5 shadow-xs ring-1 ring-secondary">
                            <h2 className="text-base font-semibold text-primary">Net cashflow line</h2>
                            <p className="mt-1 text-xs text-tertiary">
                                {mode === "user" ? "User sign convention." : "Counterparty sign convention."}
                            </p>
                            <div className="mt-4 h-72">
                                {netSeries.length === 0 ? (
                                    <div className="flex h-full items-center justify-center text-sm text-tertiary">
                                        No split time-series data for this period.
                                    </div>
                                ) : (
                                    <ResponsiveContainer>
                                        <LineChart
                                            data={netSeries.map((point) => ({
                                                ...point,
                                                label: formatDate(point.bucket, "en-US"),
                                            }))}
                                        >
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis dataKey="label" minTickGap={24} />
                                            <YAxis />
                                            <Tooltip
                                                formatter={(value: number) => formatAmount(value)}
                                                labelFormatter={(label) => String(label)}
                                            />
                                            <Line type="monotone" dataKey="net" stroke="#0b6ef6" strokeWidth={2} dot={false} />
                                        </LineChart>
                                    </ResponsiveContainer>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="grid gap-6 lg:grid-cols-2">
                        <TopRowsCard
                            title="Top payees"
                            description="Ranked by absolute split amount."
                            rows={visiblePayeeRows}
                        />
                        <TopRowsCard
                            title="Top internal accounts"
                            description="Grouped by split internal account."
                            rows={visibleInternalAccountRows}
                        />
                    </div>
                </>
            )}

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
                                <h2 className="text-lg font-semibold text-primary">Analytics filters</h2>
                                <p className="text-sm text-tertiary">Configure global analytics filters and per-screen selections.</p>
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
                            </section>

                            <section className="grid gap-3 rounded-xl bg-secondary/40 p-4 ring-1 ring-secondary md:grid-cols-2">
                                <Select
                                    label="Granularity"
                                    items={GRANULARITY_OPTIONS}
                                    selectedKey={granularity}
                                    onSelectionChange={(key) => key && setGranularity(String(key) as AnalyticsGranularity)}
                                >
                                    {(item) => <Select.Item id={item.id} label={item.label} />}
                                </Select>
                                <Select
                                    label="Mode"
                                    items={MODE_OPTIONS}
                                    selectedKey={mode}
                                    onSelectionChange={(key) => key && setMode(String(key) as AnalyticsMode)}
                                >
                                    {(item) => <Select.Item id={item.id} label={item.label} />}
                                </Select>
                                <Button
                                    size="sm"
                                    color={excludeTransfers ? "secondary" : "tertiary"}
                                    onClick={() => setExcludeTransfers((prev) => !prev)}
                                >
                                    {excludeTransfers ? "Transfers excluded" : "Transfers included"}
                                </Button>
                                <Button
                                    size="sm"
                                    color={excludeMomentTagged ? "secondary" : "tertiary"}
                                    onClick={() => setExcludeMomentTagged((prev) => !prev)}
                                >
                                    {excludeMomentTagged ? "Moment-tagged excluded" : "Moment-tagged included"}
                                </Button>
                            </section>

                            <section className="space-y-3 rounded-xl bg-secondary/40 p-4 ring-1 ring-secondary">
                                <h3 className="text-sm font-semibold text-primary">Spend by category filters</h3>
                                <MultiSelect
                                    aria-label="Filter spend by category"
                                    label="Categories"
                                    items={spendCategoryOptions}
                                    selectedItems={selectedSpendCategoryItems}
                                    placeholder="All categories"
                                >
                                    {(item) => <MultiSelect.Item id={item.id} label={item.label} />}
                                </MultiSelect>
                            </section>

                            <section className="space-y-3 rounded-xl bg-secondary/40 p-4 ring-1 ring-secondary">
                                <h3 className="text-sm font-semibold text-primary">Top payees filters</h3>
                                <MultiSelect
                                    aria-label="Filter top payees"
                                    label="Payees"
                                    items={payeeOptions}
                                    selectedItems={selectedPayeeItems}
                                    placeholder="All payees"
                                >
                                    {(item) => <MultiSelect.Item id={item.id} label={item.label} />}
                                </MultiSelect>
                            </section>

                            <section className="space-y-3 rounded-xl bg-secondary/40 p-4 ring-1 ring-secondary">
                                <h3 className="text-sm font-semibold text-primary">Top internal accounts filters</h3>
                                <MultiSelect
                                    aria-label="Filter top internal accounts"
                                    label="Internal accounts"
                                    items={internalAccountOptions}
                                    selectedItems={selectedInternalAccountItems}
                                    placeholder="All internal accounts"
                                >
                                    {(item) => <MultiSelect.Item id={item.id} label={item.label} />}
                                </MultiSelect>
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

const SummaryCard = ({ label, value, supporting }: { label: string; value: number; supporting: string }) => (
    <div className="rounded-xl bg-primary p-4 ring-1 ring-secondary">
        <span className="text-xs text-tertiary">{label}</span>
        <div className={`text-lg font-semibold ${amountClass(value)}`}>{formatAmount(value)}</div>
        <span className="text-xs text-tertiary">{supporting}</span>
    </div>
);

const TopRowsCard = ({
    title,
    description,
    rows,
}: {
    title: string;
    description: string;
    rows: { entity_id: number | null; entity_name: string; income: number; expense: number; net: number }[];
}) => (
    <div className="rounded-2xl bg-primary p-5 shadow-xs ring-1 ring-secondary">
        <h2 className="text-base font-semibold text-primary">{title}</h2>
        <p className="mt-1 text-xs text-tertiary">{description}</p>
        {rows.length === 0 ? (
            <div className="mt-4 text-sm text-tertiary">No rows for this period.</div>
        ) : (
            <div className="mt-4 overflow-x-auto">
                <table className="min-w-full text-sm">
                    <thead>
                        <tr className="border-b border-secondary text-left text-xs text-secondary">
                            <th className="px-2 py-2 font-semibold">Name</th>
                            <th className="px-2 py-2 font-semibold">Income</th>
                            <th className="px-2 py-2 font-semibold">Expense</th>
                            <th className="px-2 py-2 font-semibold">Net</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row) => (
                            <tr key={`${row.entity_id ?? "null"}-${row.entity_name}`} className="border-b border-secondary">
                                <td className="px-2 py-2 text-primary">{row.entity_name}</td>
                                <td className="px-2 py-2 text-primary">{formatAmount(row.income)}</td>
                                <td className="px-2 py-2 text-primary">{formatAmount(row.expense)}</td>
                                <td className={`px-2 py-2 font-medium ${amountClass(row.net)}`}>{formatAmount(row.net)}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        )}
    </div>
);

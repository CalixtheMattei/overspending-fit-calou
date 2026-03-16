import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { parseDate, toCalendarDate } from "@internationalized/date";
import { SearchLg } from "@untitledui/icons";
import type { DateValue } from "react-aria-components";
import { useNavigate, useSearchParams } from "react-router";
import { DateRangePicker } from "@/components/application/date-picker/date-range-picker";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { SlideoutMenu } from "@/components/application/slideout-menus/slideout-menu";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";
import { SankeyChart, type SankeyNodeClickPayload } from "@/components/ledger/charts/sankey-chart";
import { buildSankeyData } from "@/components/ledger/charts/sankey-utils";
import { getCategoryDisplayLabel } from "@/components/ledger/categories/category-visuals";
import { CategoryTreePicker } from "@/components/ledger/categories/category-tree-picker";
import { SplitEditorModal } from "@/components/ledger/splits/split-editor-modal";
import type { SplitDraft } from "@/components/ledger/splits/use-split-draft";
import { TRANSACTION_TYPE_OPTIONS } from "@/components/ledger/constants";
import { TransactionsFilterChips } from "@/components/ledger/transactions/transactions-filter-chips";
import { TransactionsFiltersPopover } from "@/components/ledger/transactions/transactions-filters-popover";
import { TransactionsTable } from "@/components/ledger/transactions/transactions-table";
import { cx } from "@/utils/cx";
import { amountClass, formatAmount, formatDate } from "@/utils/format";
import type { BankAccount } from "@/services/accounts";
import { fetchAccounts } from "@/services/accounts";
import type { Category, CategoryPresets } from "@/services/categories";
import { createCategory, fetchCategoryPresets } from "@/services/categories";
import type { FlowResponse } from "@/services/analytics";
import { fetchAnalyticsFlow } from "@/services/analytics";
import {
    type AnalyticsFilterState,
    type SankeyPresetId,
    SANKEY_PRESET_OPTIONS_WITH_TODAY,
    getPresetDateRange,
    serializeFilters,
} from "@/features/analytics/filters";
import { useAnalyticsFilters } from "@/features/analytics/use-analytics-filters";
import type { InternalAccount } from "@/services/internal-accounts";
import { createInternalAccount, fetchInternalAccounts } from "@/services/internal-accounts";
import type { Moment } from "@/services/moments";
import { fetchMoments } from "@/services/moments";
import type { Payee } from "@/services/payees";
import { createPayee, fetchPayees } from "@/services/payees";
import { fetchTransactionRuleHistory, type TransactionRuleHistoryRow } from "@/services/rules";
import type { TransactionDetail, TransactionSummary } from "@/services/transactions";
import {
    fetchTransaction,
    fetchTransactions,
    isSplitReassignConflictError,
    mapSplitErrorMessage,
    replaceTransactionSplits,
    updateTransaction,
} from "@/services/transactions";

const DEFAULT_LIMIT = 25;
const DEFAULT_FLOW_PRESET: SankeyPresetId = "1M";
const ALL_FILTER_VALUE = "all";

/** Build a URL to the full analytics page preserving the current filter state. */
const buildAnalyticsUrl = (filters: AnalyticsFilterState): string => {
    const params = serializeFilters(filters);
    return `/analytics?${params.toString()}`;
};
const STATUS_STORAGE_KEY = "ledger-dashboard-status-filter";
const FALLBACK_CATEGORY_PRESETS: CategoryPresets = {
    colors: ["#9CA3AF"],
    icons: ["tag"],
    default_color: "#9CA3AF",
    default_icon: "tag",
    categories: [],
    tree: [],
};

const STATUS_OPTIONS = [
    { id: "uncategorized", label: "Uncategorized" },
    { id: "categorized", label: "Categorized" },
    { id: "all", label: "All" },
];
const STATUS_FILTER_IDS = new Set(STATUS_OPTIONS.map((option) => option.id));

type DateRangeValue = { start: DateValue; end: DateValue };

const readStoredStatusFilter = (): string | null => {
    if (typeof window === "undefined") return null;
    try {
        const value = window.localStorage.getItem(STATUS_STORAGE_KEY);
        if (!value || !STATUS_FILTER_IDS.has(value)) {
            return null;
        }
        return value;
    } catch {
        return null;
    }
};

const writeStoredStatusFilter = (value: string) => {
    if (typeof window === "undefined") return;
    try {
        window.localStorage.setItem(STATUS_STORAGE_KEY, value);
    } catch {
        // Ignore storage errors and keep in-memory behavior.
    }
};

const toDateRangeValue = (start: string, end: string): DateRangeValue | null => {
    if (!start || !end) return null;
    try {
        return { start: parseDate(start), end: parseDate(end) };
    } catch {
        return null;
    }
};

const formatDateTime = (value: string | null) => {
    if (!value) return "Unknown";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return "Unknown";
    return parsed.toLocaleString();
};


export const LedgerDashboardPage = () => {
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    // Shared analytics filter state — drives excludeTransfers / excludeMomentTagged
    // and syncs the Sankey date range with the URL.
    const {
        filters: analyticsFilters,
        applyPreset: applyAnalyticsPreset,
        applyCustomRange: applyAnalyticsCustomRange,
    } = useAnalyticsFilters({
        syncWithUrl: true,
        supportsGranularity: false,
        supportsMode: false,
        initialPresetId: "1M",
    });

    // The Sankey compact controls include a "TODAY" chip that is not a standard
    // analytics preset, so we keep a local preset id for the chip highlight.
    const [defaultStatusFilter] = useState(() => readStoredStatusFilter() ?? "all");

    const [flowData, setFlowData] = useState<FlowResponse | null>(null);
    const [flowLoading, setFlowLoading] = useState(true);
    const [flowError, setFlowError] = useState<string | null>(null);
    const flowStart = analyticsFilters.startDate;
    const flowEnd = analyticsFilters.endDate;
    const [flowPresetId, setFlowPresetId] = useState<SankeyPresetId | null>(
        (analyticsFilters.presetId as SankeyPresetId | null) ?? DEFAULT_FLOW_PRESET,
    );
    const [flowDateRangeDraft, setFlowDateRangeDraft] = useState<DateRangeValue | null>(() =>
        toDateRangeValue(flowStart, flowEnd),
    );

    const [transactions, setTransactions] = useState<TransactionSummary[]>([]);
    const [transactionsTotal, setTransactionsTotal] = useState(0);
    const [transactionsLoading, setTransactionsLoading] = useState(false);
    const [transactionsError, setTransactionsError] = useState<string | null>(null);
    const [transactionsPage, setTransactionsPage] = useState(1);
    const [transactionsLimit] = useState(DEFAULT_LIMIT);
    const [tableRefreshKey, setTableRefreshKey] = useState(0);
    const [flowRefreshKey, setFlowRefreshKey] = useState(0);
    const flowRefreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const bumpTableRefresh = useCallback(() => setTableRefreshKey((k) => k + 1), []);
    const bumpFlowRefreshDeferred = useCallback(() => {
        if (flowRefreshTimerRef.current) clearTimeout(flowRefreshTimerRef.current);
        flowRefreshTimerRef.current = setTimeout(() => setFlowRefreshKey((k) => k + 1), 2000);
    }, []);
    const bumpBothRefresh = useCallback(() => {
        bumpTableRefresh();
        if (flowRefreshTimerRef.current) clearTimeout(flowRefreshTimerRef.current);
        setFlowRefreshKey((k) => k + 1);
    }, [bumpTableRefresh]);

    const [statusFilter, setStatusFilter] = useState(defaultStatusFilter);
    const [typeFilter, setTypeFilter] = useState(ALL_FILTER_VALUE);
    const [searchQuery, setSearchQuery] = useState("");
    const [payeeFilter, setPayeeFilter] = useState(ALL_FILTER_VALUE);
    const [categoryFilter, setCategoryFilter] = useState(ALL_FILTER_VALUE);
    const [internalAccountFilter, setInternalAccountFilter] = useState(ALL_FILTER_VALUE);
    const [bankAccountFilter, setBankAccountFilter] = useState(ALL_FILTER_VALUE);

    const [payees, setPayees] = useState<Payee[]>([]);
    const [categories, setCategories] = useState<Category[]>([]);
    const [categoryPresets, setCategoryPresets] = useState<CategoryPresets>(FALLBACK_CATEGORY_PRESETS);
    const [internalAccounts, setInternalAccounts] = useState<InternalAccount[]>([]);
    const [moments, setMoments] = useState<Moment[]>([]);
    const [accounts, setAccounts] = useState<BankAccount[]>([]);

    const [drawerTransactionId, setDrawerTransactionId] = useState<number | null>(null);
    const [drawerData, setDrawerData] = useState<TransactionDetail | null>(null);
    const [drawerLoading, setDrawerLoading] = useState(false);
    const [drawerError, setDrawerError] = useState<string | null>(null);
    const [drawerCategorySaving, setDrawerCategorySaving] = useState(false);
    const [drawerRuleHistory, setDrawerRuleHistory] = useState<TransactionRuleHistoryRow[]>([]);
    const [drawerRuleHistoryLoading, setDrawerRuleHistoryLoading] = useState(false);
    const [drawerRuleHistoryError, setDrawerRuleHistoryError] = useState<string | null>(null);
    const [showAuditTrail, setShowAuditTrail] = useState(false);

    const [splitModalTransactionId, setSplitModalTransactionId] = useState<number | null>(null);
    const [splitModalOpen, setSplitModalOpen] = useState(false);
    const [splitModalData, setSplitModalData] = useState<TransactionDetail | null>(null);
    const [splitModalLoading, setSplitModalLoading] = useState(false);
    const [splitModalError, setSplitModalError] = useState<string | null>(null);
    const [splitSaving, setSplitSaving] = useState(false);

    const [payeeSearch, setPayeeSearch] = useState("");

    const categoryById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);

    useEffect(() => {
        setFlowDateRangeDraft(toDateRangeValue(flowStart, flowEnd));
    }, [flowStart, flowEnd]);

    useEffect(() => {
        writeStoredStatusFilter(statusFilter);
    }, [statusFilter]);

    useEffect(() => {
        let isActive = true;
        const loadFlow = async () => {
            setFlowLoading(true);
            setFlowError(null);
            try {
                const data = await fetchAnalyticsFlow({
                    start_date: flowStart || undefined,
                    end_date: flowEnd || undefined,
                    exclude_transfers: analyticsFilters.excludeTransfers,
                    exclude_moment_tagged: analyticsFilters.excludeMomentTagged,
                });
                if (!isActive) return;
                setFlowData(data);
            } catch (error) {
                if (!isActive) return;
                setFlowError(error instanceof Error ? error.message : "Failed to load flow data.");
            } finally {
                if (isActive) {
                    setFlowLoading(false);
                }
            }
        };

        loadFlow();

        return () => {
            isActive = false;
        };
    }, [flowStart, flowEnd, analyticsFilters.excludeTransfers, analyticsFilters.excludeMomentTagged, flowRefreshKey]);

    useEffect(() => {
        const loadOptions = async () => {
            try {
                const [payeesResult, categoryPresetsResult, internalAccountsResult, momentsResult, accountsResult] = await Promise.all([
                    fetchPayees({ limit: 200 }),
                    fetchCategoryPresets(),
                    fetchInternalAccounts(),
                    fetchMoments({ limit: 200 }),
                    fetchAccounts(),
                ]);

                setPayees(payeesResult);
                setCategories(categoryPresetsResult.categories);
                setCategoryPresets(categoryPresetsResult);
                setInternalAccounts(internalAccountsResult);
                setMoments(momentsResult);
                setAccounts(accountsResult);
            } catch (error) {
                setTransactionsError(error instanceof Error ? error.message : "Failed to load ledger data.");
            }
        };

        loadOptions();
    }, []);
    useEffect(() => {
        let isActive = true;
        const loadTransactions = async () => {
            setTransactionsLoading(true);
            setTransactionsError(null);
            try {
                const data = await fetchTransactions({
                    status: statusFilter,
                    type: typeFilter,
                    q: searchQuery.trim() || undefined,
                    payee_id: payeeFilter !== ALL_FILTER_VALUE ? Number(payeeFilter) : undefined,
                    category_id: categoryFilter !== ALL_FILTER_VALUE ? Number(categoryFilter) : undefined,
                    internal_account_id: internalAccountFilter !== ALL_FILTER_VALUE ? Number(internalAccountFilter) : undefined,
                    bank_account_id: bankAccountFilter !== ALL_FILTER_VALUE ? Number(bankAccountFilter) : undefined,
                    limit: transactionsLimit,
                    offset: (transactionsPage - 1) * transactionsLimit,
                });
                if (!isActive) return;
                setTransactions(data.rows);
                setTransactionsTotal(data.total);
            } catch (error) {
                if (!isActive) return;
                setTransactionsError(error instanceof Error ? error.message : "Failed to load transactions.");
            } finally {
                if (isActive) {
                    setTransactionsLoading(false);
                }
            }
        };

        loadTransactions();

        return () => {
            isActive = false;
        };
    }, [
        statusFilter,
        typeFilter,
        searchQuery,
        payeeFilter,
        categoryFilter,
        internalAccountFilter,
        bankAccountFilter,
        transactionsLimit,
        transactionsPage,
        tableRefreshKey,
    ]);

    useEffect(() => {
        if (!drawerTransactionId) {
            setDrawerData(null);
            setDrawerRuleHistory([]);
            setDrawerRuleHistoryError(null);
            return;
        }

        let isActive = true;
        const loadTransaction = async () => {
            setDrawerLoading(true);
            setDrawerError(null);
            try {
                const data = await fetchTransaction(drawerTransactionId);
                if (!isActive) return;
                setDrawerData(data);
                setPayeeSearch("");
            } catch (error) {
                if (!isActive) return;
                setDrawerError(error instanceof Error ? error.message : "Failed to load transaction.");
            } finally {
                if (isActive) {
                    setDrawerLoading(false);
                }
            }
        };

        loadTransaction();

        return () => {
            isActive = false;
        };
    }, [drawerTransactionId]);

    useEffect(() => {
        if (!drawerTransactionId) {
            setDrawerRuleHistory([]);
            setDrawerRuleHistoryError(null);
            setDrawerRuleHistoryLoading(false);
            return;
        }

        let isActive = true;
        const loadRuleHistory = async () => {
            setDrawerRuleHistoryLoading(true);
            setDrawerRuleHistoryError(null);
            try {
                const response = await fetchTransactionRuleHistory(drawerTransactionId, { limit: 5, offset: 0 });
                if (!isActive) return;
                setDrawerRuleHistory(response.rows);
            } catch (error) {
                if (!isActive) return;
                setDrawerRuleHistoryError(error instanceof Error ? error.message : "Failed to load rule history.");
            } finally {
                if (isActive) {
                    setDrawerRuleHistoryLoading(false);
                }
            }
        };

        loadRuleHistory();

        return () => {
            isActive = false;
        };
    }, [drawerTransactionId, tableRefreshKey]);

    useEffect(() => {
        if (!splitModalOpen || !splitModalTransactionId) {
            setSplitModalData(null);
            return;
        }

        let isActive = true;
        const loadSplitModalTransaction = async () => {
            setSplitModalLoading(true);
            setSplitModalError(null);
            try {
                const data = await fetchTransaction(splitModalTransactionId);
                if (!isActive) return;
                setSplitModalData(data);
            } catch (error) {
                if (!isActive) return;
                setSplitModalError(error instanceof Error ? error.message : "Failed to load split editor data.");
            } finally {
                if (isActive) {
                    setSplitModalLoading(false);
                }
            }
        };

        loadSplitModalTransaction();

        return () => {
            isActive = false;
        };
    }, [splitModalOpen, splitModalTransactionId]);

    // Deep-link support: open transaction drawer (and optionally split editor) from URL params.
    useEffect(() => {
        const txParam = searchParams.get("tx");
        if (!txParam) return;

        const txId = Number(txParam);
        if (!Number.isFinite(txId) || txId <= 0) return;

        const action = searchParams.get("action");

        // Clear URL params so this only triggers once.
        setSearchParams({}, { replace: true });

        setDrawerTransactionId(txId);

        if (action === "split") {
            setTimeout(() => openSplitModal(txId), 300);
        }
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const totalPages = Math.max(1, Math.ceil(transactionsTotal / transactionsLimit));
    const statusLabelById = useMemo(() => new Map(STATUS_OPTIONS.map((option) => [option.id, option.label])), []);
    const typeLabelById = useMemo(
        () => new Map(TRANSACTION_TYPE_OPTIONS.map((option) => [option.id, option.label])),
        [],
    );
    const payeeLabelById = useMemo(() => new Map(payees.map((payee) => [String(payee.id), payee.name])), [payees]);
    const categoryLabelById = useMemo(
        () => new Map(categories.map((category) => [String(category.id), getCategoryDisplayLabel(category)])),
        [categories],
    );
    const internalAccountLabelById = useMemo(
        () => new Map(internalAccounts.map((account) => [String(account.id), account.name])),
        [internalAccounts],
    );
    const bankAccountLabelById = useMemo(
        () => new Map(accounts.map((account) => [String(account.id), account.label])),
        [accounts],
    );

    const handleFlowPresetChange = (presetId: SankeyPresetId) => {
        setFlowPresetId(presetId);
        if (presetId === "TODAY") {
            // "TODAY" is not a standard analytics preset — apply as custom range.
            const todayRange = getPresetDateRange("TODAY");
            applyAnalyticsCustomRange(todayRange.start, todayRange.end);
        } else {
            applyAnalyticsPreset(presetId);
        }
    };

    const handleApplyCustomFlowRange = () => {
        if (!flowDateRangeDraft) return;
        const start = toCalendarDate(flowDateRangeDraft.start).toString();
        const end = toCalendarDate(flowDateRangeDraft.end).toString();
        applyAnalyticsCustomRange(start, end);
        setFlowPresetId(null);
    };

    const handleFiltersReset = () => {
        setStatusFilter(defaultStatusFilter);
        setTypeFilter(ALL_FILTER_VALUE);
        setSearchQuery("");
        setPayeeFilter(ALL_FILTER_VALUE);
        setCategoryFilter(ALL_FILTER_VALUE);
        setInternalAccountFilter(ALL_FILTER_VALUE);
        setBankAccountFilter(ALL_FILTER_VALUE);
        setTransactionsPage(1);
    };

    const handleDrawerClose = () => {
        setDrawerTransactionId(null);
        setDrawerData(null);
        setDrawerCategorySaving(false);
        setDrawerRuleHistory([]);
        setDrawerRuleHistoryError(null);
        setShowAuditTrail(false);
    };

    const navigateToCategoryCreate = useCallback(() => {
        navigate("/ledger/categories?create=1");
    }, [navigate]);

    const closeSplitModal = () => {
        setSplitModalOpen(false);
        setSplitModalTransactionId(null);
        setSplitModalData(null);
        setSplitModalError(null);
        setSplitModalLoading(false);
    };

    const openSplitModal = (transactionId: number) => {
        setSplitModalTransactionId(transactionId);
        setSplitModalOpen(true);
        setSplitModalError(null);
    };

    const handleSaveSplits = async (
        splitDrafts: SplitDraft[],
        options?: { confirmReassign?: boolean },
    ): Promise<"saved" | "conflict_required" | "error"> => {
        if (!splitModalData) return "error";
        setSplitSaving(true);
        setSplitModalError(null);
        try {
            const payload = {
                splits: splitDrafts.map((split) => ({
                    id: split.id,
                    amount: split.amount,
                    category_id: split.category_id,
                    moment_id: split.moment_id ?? null,
                    internal_account_id: split.internal_account_id ?? null,
                    note: split.note || null,
                })),
                confirm_reassign: options?.confirmReassign ?? false,
            };
            const data = await replaceTransactionSplits(splitModalData.transaction.id, payload);
            setSplitModalData(data);
            if (drawerData?.transaction.id === data.transaction.id) {
                setDrawerData(data);
            }
            // Optimistic row patch for split modal save
            setTransactions((prev) =>
                prev.map((tx) =>
                    tx.id === data.transaction.id
                        ? {
                              ...tx,
                              splits_count: data.splits_count,
                              is_categorized: data.splits.some((s) => s.category_id !== null),
                              single_category_id: data.splits_count === 1 ? (data.splits[0]?.category_id ?? null) : null,
                              single_category: data.splits_count === 1 ? (data.splits[0]?.category ?? null) : null,
                          }
                        : tx,
                ),
            );
            bumpTableRefresh();
            bumpFlowRefreshDeferred();
            closeSplitModal();
            return "saved";
        } catch (error) {
            if (isSplitReassignConflictError(error) && !options?.confirmReassign) {
                setSplitModalError(null);
                return "conflict_required";
            }

            setSplitModalError(mapSplitErrorMessage(error));
            return "error";
        } finally {
            setSplitSaving(false);
        }
    };

    const handleCreateInternalAccountForSplit = async (payload: { name: string; type: string | null }) => {
        const created = await createInternalAccount(payload);
        setInternalAccounts((prev) => [...prev, created].sort((a, b) => a.position - b.position));
        return created;
    };

    const handleCreateCategoryForSplit = async (payload: {
        name: string;
        parent_id?: number | null;
        color?: string | null;
        icon?: string | null;
    }) => {
        const created = await createCategory(payload);
        setCategories((prev) => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
        return created;
    };

    const handleTypeChange = async (nextType: string) => {
        if (!drawerData) return;
        try {
            const data = await updateTransaction(drawerData.transaction.id, { type: nextType });
            setDrawerData(data);
            bumpBothRefresh();
        } catch (error) {
            setDrawerError(mapSplitErrorMessage(error));
        }
    };

    const handlePayeeSelection = async (key: string | null) => {
        if (!drawerData) return;
        if (!key) return;
        setDrawerError(null);

        try {
            if (key === "none") {
                const data = await updateTransaction(drawerData.transaction.id, { payee_id: null });
                setDrawerData(data);
                bumpBothRefresh();
                return;
            }

            if (key.startsWith("create:")) {
                const name = key.replace("create:", "").trim();
                if (!name) return;
                const created = await createPayee({ name });
                setPayees((prev) => {
                    const exists = prev.some((item) => item.id === created.id);
                    const next = exists ? prev.map((item) => (item.id === created.id ? created : item)) : [created, ...prev];
                    return next.sort((a, b) => a.name.localeCompare(b.name));
                });
                const data = await updateTransaction(drawerData.transaction.id, { payee_id: created.id });
                setDrawerData(data);
                bumpBothRefresh();
                return;
            }

            const payeeId = Number(key);
            if (Number.isNaN(payeeId)) return;
            const data = await updateTransaction(drawerData.transaction.id, { payee_id: payeeId });
            setDrawerData(data);
            bumpBothRefresh();
        } catch (error) {
            setDrawerError(mapSplitErrorMessage(error));
        }
    };

    const handleDrawerCategoryChange = async (key: string | null) => {
        if (!drawerData || !key) return;
        if (drawerData.splits_count > 1) {
            setDrawerError("Edit categories from the split editor for multi-split transactions.");
            return;
        }

        const nextCategoryId = key === "none" ? null : Number(key);
        if (key !== "none" && Number.isNaN(nextCategoryId)) {
            return;
        }
        if (drawerData.splits_count === 0 && nextCategoryId === null) {
            return;
        }
        if (drawerData.splits_count === 1 && !drawerData.splits[0]) {
            return;
        }

        setDrawerCategorySaving(true);
        setDrawerError(null);
        try {
            const splitsPayload =
                drawerData.splits_count === 0
                    ? [
                          {
                              amount: drawerData.transaction.amount,
                              category_id: nextCategoryId,
                              moment_id: null,
                              internal_account_id: null,
                              note: null,
                          },
                      ]
                    : [
                          {
                              id: drawerData.splits[0].id,
                              amount: drawerData.splits[0].amount,
                              category_id: nextCategoryId,
                              moment_id: drawerData.splits[0].moment_id,
                              internal_account_id: drawerData.splits[0].internal_account_id,
                              note: drawerData.splits[0].note,
                          },
                      ];

            const data = await replaceTransactionSplits(drawerData.transaction.id, { splits: splitsPayload });
            setDrawerData(data);
            if (splitModalData?.transaction.id === data.transaction.id) {
                setSplitModalData(data);
            }
            // Optimistic row patch: update the transaction in the local list immediately
            setTransactions((prev) =>
                prev.map((tx) =>
                    tx.id === data.transaction.id
                        ? {
                              ...tx,
                              splits_count: data.splits_count,
                              is_categorized: data.splits.some((s) => s.category_id !== null),
                              single_category_id: data.splits_count === 1 ? (data.splits[0]?.category_id ?? null) : null,
                              single_category: data.splits_count === 1 ? (data.splits[0]?.category ?? null) : null,
                          }
                        : tx,
                ),
            );
            bumpTableRefresh();
            bumpFlowRefreshDeferred();

            try {
                const history = await fetchTransactionRuleHistory(data.transaction.id, { limit: 5, offset: 0 });
                setDrawerRuleHistory(history.rows);
                setDrawerRuleHistoryError(null);
            } catch (error) {
                setDrawerRuleHistoryError(error instanceof Error ? error.message : "Failed to load rule history.");
            }
        } catch (error) {
            setDrawerError(mapSplitErrorMessage(error));
        } finally {
            setDrawerCategorySaving(false);
        }
    };

    const payeeFilterOptions = [
        { id: ALL_FILTER_VALUE, label: "All payees" },
        ...payees.map((payee) => ({ id: String(payee.id), label: payee.name })),
    ];

    const categoryFilterOptions = [
        { id: ALL_FILTER_VALUE, label: "All categories" },
        ...categories
            .filter((category) => !category.is_deprecated || categoryFilter === String(category.id))
            .map((category) => ({
                id: String(category.id),
                label: getCategoryDisplayLabel(category),
            }))
            .sort((a, b) => a.label.localeCompare(b.label)),
    ];
    const internalAccountFilterOptions = [
        { id: ALL_FILTER_VALUE, label: "All internal accounts" },
        ...internalAccounts.map((account) => ({ id: String(account.id), label: account.name })),
    ];

    const bankAccountFilterOptions = [
        { id: ALL_FILTER_VALUE, label: "All bank accounts" },
        ...accounts.map((account) => ({ id: String(account.id), label: account.label })),
    ];

    const filteredPayeeOptions = payees.filter((payee) =>
        payee.name.toLowerCase().includes(payeeSearch.trim().toLowerCase()),
    );

    const payeeComboBoxOptions = [
        { id: "none", label: "No payee" },
        ...filteredPayeeOptions.map((payee) => ({ id: String(payee.id), label: payee.name })),
    ];

    if (payeeSearch.trim()) {
        const normalized = payeeSearch.trim().toLowerCase();
        const exists = filteredPayeeOptions.some((payee) => payee.name.toLowerCase() === normalized);
        if (!exists) {
            payeeComboBoxOptions.push({ id: `create:${payeeSearch.trim()}`, label: `Create "${payeeSearch.trim()}"` });
        }
    }

    const sankeyData = useMemo(
        () =>
            buildSankeyData(flowData, {
                hiddenCategoryIds: new Set<string>(),
                hiddenTypeIds: new Set<string>(),
            }),
        [flowData],
    );

    const handleSankeyNodeClick = useCallback(
        (payload: SankeyNodeClickPayload) => {
            if (payload.kind !== "category_bucket") return;
            const categoryRef = payload.categoryId != null ? String(payload.categoryId) : "uncategorized";
            const params = new URLSearchParams();
            if (flowStart) params.set("start_date", flowStart);
            if (flowEnd) params.set("end_date", flowEnd);
            params.set("exclude_transfers", String(analyticsFilters.excludeTransfers));
            params.set("exclude_moment_tagged", String(analyticsFilters.excludeMomentTagged));
            params.set("from", "ledger");
            const query = params.toString();
            navigate(`/analytics/category/${categoryRef}${query ? `?${query}` : ""}`);
        },
        [navigate, flowStart, flowEnd, analyticsFilters.excludeTransfers, analyticsFilters.excludeMomentTagged],
    );

    const activeFilterChips = [
        searchQuery.trim()
            ? {
                  id: "search",
                  label: `Search: ${searchQuery.trim()}`,
                  onRemove: () => {
                      setSearchQuery("");
                      setTransactionsPage(1);
                  },
              }
            : null,
        statusFilter !== defaultStatusFilter && statusFilter !== "uncategorized"
            ? {
                  id: "status",
                  label: statusLabelById.get(statusFilter) || "Status",
                  onRemove: () => {
                      setStatusFilter(defaultStatusFilter);
                      setTransactionsPage(1);
                  },
              }
            : null,
        typeFilter !== ALL_FILTER_VALUE
            ? {
                  id: "type",
                  label: typeLabelById.get(typeFilter) || "Type",
                  onRemove: () => {
                      setTypeFilter(ALL_FILTER_VALUE);
                      setTransactionsPage(1);
                  },
              }
            : null,
        payeeFilter !== ALL_FILTER_VALUE
            ? {
                  id: "payee",
                  label: payeeLabelById.get(payeeFilter) || "Payee",
                  onRemove: () => {
                      setPayeeFilter(ALL_FILTER_VALUE);
                      setTransactionsPage(1);
                  },
              }
            : null,
        categoryFilter !== ALL_FILTER_VALUE
            ? {
                  id: "category",
                  label: categoryLabelById.get(categoryFilter) || "Category",
                  onRemove: () => {
                      setCategoryFilter(ALL_FILTER_VALUE);
                      setTransactionsPage(1);
                  },
              }
            : null,
        internalAccountFilter !== ALL_FILTER_VALUE
            ? {
                  id: "internal-account",
                  label: internalAccountLabelById.get(internalAccountFilter) || "Internal account",
                  onRemove: () => {
                      setInternalAccountFilter(ALL_FILTER_VALUE);
                      setTransactionsPage(1);
                  },
              }
            : null,
        bankAccountFilter !== ALL_FILTER_VALUE
            ? {
                  id: "bank-account",
                  label: bankAccountLabelById.get(bankAccountFilter) || "Bank account",
                  onRemove: () => {
                      setBankAccountFilter(ALL_FILTER_VALUE);
                      setTransactionsPage(1);
                  },
              }
            : null,
    ].filter((chip): chip is { id: string; label: string; onRemove: () => void } => chip !== null);

    const hasAnyFilters = activeFilterChips.length > 0 || statusFilter === "uncategorized";
    const transactionsEmpty = !transactionsLoading && transactions.length === 0 && !transactionsError;
    const emptyStateVariant = hasAnyFilters ? "filtered_empty" : "true_empty";
    const transactionsToolbar = (
        <div className="flex w-full flex-col items-stretch gap-2 md:w-auto">
            <div className="flex w-full flex-wrap items-center justify-end gap-2">
                <Input
                    aria-label="Search transactions"
                    size="sm"
                    icon={SearchLg}
                    placeholder="Search label or payee"
                    value={searchQuery}
                    onChange={(value) => {
                        setSearchQuery(value);
                        setTransactionsPage(1);
                    }}
                    className="w-full min-w-[220px] md:w-72"
                />
                <TransactionsFiltersPopover
                    statusFilter={statusFilter}
                    onStatusFilterChange={(value) => {
                        setStatusFilter(value);
                        setTransactionsPage(1);
                    }}
                    typeFilter={typeFilter}
                    onTypeFilterChange={(value) => {
                        setTypeFilter(value);
                        setTransactionsPage(1);
                    }}
                    payeeFilter={payeeFilter}
                    onPayeeFilterChange={(value) => {
                        setPayeeFilter(value);
                        setTransactionsPage(1);
                    }}
                    categoryFilter={categoryFilter}
                    onCategoryFilterChange={(value) => {
                        setCategoryFilter(value);
                        setTransactionsPage(1);
                    }}
                    internalAccountFilter={internalAccountFilter}
                    onInternalAccountFilterChange={(value) => {
                        setInternalAccountFilter(value);
                        setTransactionsPage(1);
                    }}
                    bankAccountFilter={bankAccountFilter}
                    onBankAccountFilterChange={(value) => {
                        setBankAccountFilter(value);
                        setTransactionsPage(1);
                    }}
                    statusOptions={STATUS_OPTIONS}
                    typeOptions={TRANSACTION_TYPE_OPTIONS}
                    payeeOptions={payeeFilterOptions}
                    categoryOptions={categoryFilterOptions}
                    internalAccountOptions={internalAccountFilterOptions}
                    bankAccountOptions={bankAccountFilterOptions}
                    onReset={handleFiltersReset}
                />
            </div>
            <TransactionsFilterChips
                chips={activeFilterChips}
                hasFilters={hasAnyFilters}
                statusFilter={statusFilter}
                onStatusFilterChange={(value) => {
                    setStatusFilter(value);
                    setTransactionsPage(1);
                }}
                onClearAll={handleFiltersReset}
            />
        </div>
    );

    return (
        <section className="flex flex-1 flex-col gap-6">
            <header className="flex flex-col gap-2">
                <h1 className="text-2xl font-semibold text-primary">Ledger</h1>
                <p className="text-sm text-tertiary">
                    Review uncategorized transactions, assign payees, and balance splits against your imported bank data.
                </p>
            </header>

            <div className="rounded-2xl bg-primary p-4 shadow-xs ring-1 ring-secondary">
                <div className="flex flex-wrap items-center gap-2">
                    {SANKEY_PRESET_OPTIONS_WITH_TODAY.map((preset) => (
                        <Button
                            key={preset.id}
                            size="sm"
                            color={flowPresetId === preset.id ? "secondary" : "tertiary"}
                            onClick={() => handleFlowPresetChange(preset.id)}
                            aria-label={`Show ${preset.label} flow range`}
                        >
                            {preset.label}
                        </Button>
                    ))}
                    <DateRangePicker
                        value={flowDateRangeDraft}
                        onChange={setFlowDateRangeDraft}
                        onApply={handleApplyCustomFlowRange}
                        onCancel={() => setFlowDateRangeDraft(toDateRangeValue(flowStart, flowEnd))}
                    />
                    <div className="ml-auto">
                        <Button
                            size="sm"
                            color="tertiary"
                            onClick={() => navigate(buildAnalyticsUrl(analyticsFilters))}
                        >
                            Advanced filters
                        </Button>
                    </div>
                </div>
                <div className="mt-5">
                    {flowLoading ? (
                        <div className="flex justify-center py-10">
                            <LoadingIndicator label="Loading flow..." />
                        </div>
                    ) : flowError ? (
                        <div className="rounded-xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                            {flowError}
                        </div>
                    ) : sankeyData.nodes.length === 0 ? (
                        <div className="rounded-xl border border-dashed border-secondary p-6 text-sm text-tertiary">
                            No flow data available for this date range.
                        </div>
                    ) : (
                        <SankeyChart data={sankeyData} onNodeClick={handleSankeyNodeClick} />
                    )}
                </div>
            </div>

            <div className="grid gap-6">
                <TransactionsTable
                    transactions={transactions}
                    loading={transactionsLoading}
                    error={transactionsError}
                    transactionsEmpty={transactionsEmpty}
                    emptyStateVariant={emptyStateVariant}
                    onClearFilters={handleFiltersReset}
                    onRowSelect={(id) => setDrawerTransactionId(id)}
                    onSplitAction={openSplitModal}
                    categoryById={categoryById}
                    transactionsPage={transactionsPage}
                    totalPages={totalPages}
                    onPageChange={(page) => setTransactionsPage(Math.max(1, page))}
                    toolbar={transactionsToolbar}
                />
            </div>
            <SlideoutMenu isOpen={drawerTransactionId !== null} onOpenChange={(open) => (!open ? handleDrawerClose() : null)}>
                {({ close }) => (
                    <>
                        <SlideoutMenu.Header onClose={close}>
                            <div className="flex flex-col gap-2">
                                <h3 className="text-lg font-semibold text-primary">Transaction detail</h3>
                                {drawerData && (
                                    <div className="flex flex-wrap items-center gap-3 text-sm text-tertiary">
                                        <span>{formatDate(drawerData.transaction.posted_at)}</span>
                                        {drawerData.transaction.account && (
                                            <Badge size="sm" color="gray">
                                                {drawerData.transaction.account.label}
                                            </Badge>
                                        )}
                                        <span className={cx("font-semibold", amountClass(drawerData.transaction.amount))}>
                                            {formatAmount(drawerData.transaction.amount, drawerData.transaction.currency)}
                                        </span>
                                    </div>
                                )}
                            </div>
                        </SlideoutMenu.Header>
                        <SlideoutMenu.Content>
                            {drawerLoading ? (
                                <div className="flex justify-center py-10">
                                    <LoadingIndicator label="Loading transaction..." />
                                </div>
                            ) : drawerError ? (
                                <div className="rounded-xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                                    {drawerError}
                                </div>
                            ) : drawerData ? (
                                <div className="flex flex-col gap-6">
                                    {/* Payee */}
                                    <div className="rounded-xl bg-primary p-4 ring-1 ring-secondary">
                                        <div className="flex flex-col gap-3">
                                            <span className="text-sm font-semibold text-secondary">Payee</span>
                                            <Select.ComboBox
                                                aria-label="Select payee"
                                                items={payeeComboBoxOptions}
                                                selectedKey={drawerData.transaction.payee?.id ? String(drawerData.transaction.payee.id) : "none"}
                                                onSelectionChange={(key) => handlePayeeSelection(key ? String(key) : null)}
                                                onInputChange={(value) => setPayeeSearch(value)}
                                                placeholder="Search or create a payee"
                                            >
                                                {(item) => <Select.Item id={item.id} label={item.label} />}
                                            </Select.ComboBox>
                                        </div>
                                    </div>

                                    {/* Category */}
                                    <div className="rounded-xl bg-primary p-4 ring-1 ring-secondary">
                                        <div className="flex flex-col gap-3">
                                            <span className="text-sm font-semibold text-secondary">Category</span>
                                            {drawerData.splits_count > 1 ? (
                                                <div className="flex flex-col gap-2">
                                                    {drawerData.splits.map((split) => (
                                                        <div key={split.id} className="flex items-center justify-between text-xs">
                                                            <span className="text-tertiary">
                                                                {split.category ? getCategoryDisplayLabel(split.category) : "Uncategorized"}
                                                            </span>
                                                            <span className={cx("font-medium tabular-nums", amountClass(split.amount))}>
                                                                {formatAmount(split.amount, drawerData.transaction.currency)}
                                                            </span>
                                                        </div>
                                                    ))}
                                                    <Button color="secondary" size="sm" onClick={() => openSplitModal(drawerData.transaction.id)}>
                                                        Edit splits
                                                    </Button>
                                                </div>
                                            ) : (
                                                <>
                                                    <CategoryTreePicker
                                                        aria-label="Transaction category"
                                                        categories={categories}
                                                        selectedCategoryId={
                                                            drawerData.splits_count === 1 && drawerData.splits[0]?.category_id
                                                                ? drawerData.splits[0].category_id
                                                                : null
                                                        }
                                                        isDisabled={drawerCategorySaving}
                                                        onSelect={(id) => handleDrawerCategoryChange(String(id))}
                                                        onCreateCategory={navigateToCategoryCreate}
                                                        placeholder="Uncategorized"
                                                        hideDeprecated
                                                    />
                                                    {drawerData.category_provenance.source === "rule" && drawerData.category_provenance.rule ? (
                                                        <span className="text-xs text-tertiary">
                                                            Set by rule "{drawerData.category_provenance.rule.name}"
                                                        </span>
                                                    ) : null}
                                                    <div className="flex items-center justify-between">
                                                        <button
                                                            type="button"
                                                            className="text-xs text-brand-primary hover:text-brand-primary-alt"
                                                            onClick={navigateToCategoryCreate}
                                                        >
                                                            Create category
                                                        </button>
                                                        <button
                                                            type="button"
                                                            className="text-xs text-tertiary hover:text-secondary"
                                                            onClick={() => openSplitModal(drawerData.transaction.id)}
                                                        >
                                                            {drawerData.splits_count > 0 ? "Edit split" : "Split transaction"}
                                                        </button>
                                                    </div>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    {/* Type */}
                                    <div className="rounded-xl bg-primary p-4 ring-1 ring-secondary">
                                        <div className="flex flex-col gap-3">
                                            <span className="text-sm font-semibold text-secondary">Type</span>
                                            <Select
                                                aria-label="Transaction type"
                                                items={TRANSACTION_TYPE_OPTIONS.filter((item) => item.id !== "all")}
                                                selectedKey={drawerData.transaction.type}
                                                onSelectionChange={(key) => key && handleTypeChange(String(key))}
                                            >
                                                {(item) => <Select.Item id={item.id} label={item.label} />}
                                            </Select>
                                        </div>
                                    </div>

                                    {/* Categorization history — collapsible */}
                                    <div className="overflow-hidden rounded-xl bg-primary ring-1 ring-secondary">
                                        <button
                                            type="button"
                                            className="flex w-full items-center justify-between px-4 py-3 text-left"
                                            onClick={() => setShowAuditTrail((v) => !v)}
                                        >
                                            <span className="text-sm font-medium text-secondary">Categorization history</span>
                                            <span className="text-xs text-tertiary">{showAuditTrail ? "▲" : "▼"}</span>
                                        </button>
                                        {showAuditTrail && (
                                            <div className="flex flex-col gap-2 border-t border-secondary px-4 pb-4 pt-3">
                                                <span className="text-xs text-tertiary">
                                                    Last applied: {formatDateTime(drawerData.category_provenance.last_applied_at)}
                                                </span>
                                                {drawerData.category_provenance.rule ? (
                                                    <div className="flex items-center justify-between gap-3 rounded-lg bg-secondary px-3 py-2">
                                                        <span className="text-xs text-tertiary">
                                                            Applied by rule: {drawerData.category_provenance.rule.name}
                                                        </span>
                                                        <Button size="sm" color="secondary" href="/rules">
                                                            Open rules
                                                        </Button>
                                                    </div>
                                                ) : null}
                                                {drawerRuleHistoryLoading ? (
                                                    <span className="text-xs text-tertiary">Loading history...</span>
                                                ) : drawerRuleHistoryError ? (
                                                    <span className="text-xs text-error-primary">{drawerRuleHistoryError}</span>
                                                ) : drawerRuleHistory.length === 0 ? (
                                                    <span className="text-xs text-tertiary">No rule history for this transaction.</span>
                                                ) : (
                                                    <div className="space-y-2">
                                                        {drawerRuleHistory.map((row) => (
                                                            <div key={row.id} className="rounded-lg bg-secondary px-3 py-2 text-xs text-tertiary">
                                                                {row.rule?.name || `Rule #${row.rule_id}`} — {row.status} —{" "}
                                                                {formatDateTime(row.applied_at)}
                                                            </div>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                <span className="text-sm text-tertiary">Select a transaction to review metadata.</span>
                            )}
                        </SlideoutMenu.Content>
                    </>
                )}
            </SlideoutMenu>

            <SplitEditorModal
                isOpen={splitModalOpen}
                loading={splitModalLoading}
                saving={splitSaving}
                error={splitModalError}
                transactionDetail={splitModalData}
                categories={categories}
                categoryPresets={categoryPresets}
                moments={moments}
                internalAccounts={internalAccounts}
                onOpenChange={(open) => (open ? setSplitModalOpen(true) : closeSplitModal())}
                onSaveSplits={handleSaveSplits}
                onCreateCategory={handleCreateCategoryForSplit}
                onCreateInternalAccount={handleCreateInternalAccountForSplit}
            />
        </section>
    );
};

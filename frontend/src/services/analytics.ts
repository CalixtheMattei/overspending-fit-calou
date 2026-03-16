import { apiFetch } from "./api";

export type AnalyticsGranularity = "day" | "week" | "month";
export type AnalyticsMode = "user" | "counterparty";

export type FlowNode = {
    id: string;
    name: string;
    label: string;
    type: "source" | "expense";
    kind: "transaction_type" | "category_bucket";
    transaction_type?: string;
    category_id?: number;
};

export type FlowLink = {
    source: string;
    target: string;
    value: number;
};

export type FlowTotals = {
    income: number;
    expenses: number;
    refunds: number;
    transfers: number;
};

export type FlowResponse = {
    nodes: FlowNode[];
    links: FlowLink[];
    totals: FlowTotals;
};

export type AnalyticsTimePoint = {
    bucket: string;
    income: number;
    expense: number;
    net: number;
};

export type AnalyticsGroupedRow = {
    entity_id: number | null;
    entity_name: string;
    income: number;
    expense: number;
    net: number;
    absolute_total: number;
    series: AnalyticsTimePoint[];
};

export type AnalyticsGroupedResponse = {
    rows: AnalyticsGroupedRow[];
    total_rows: number;
    totals: {
        income: number;
        expense: number;
        net: number;
    };
    series_totals: AnalyticsTimePoint[];
};

export const fetchAnalyticsFlow = async (
    params: { start_date?: string; end_date?: string; exclude_transfers?: boolean; exclude_moment_tagged?: boolean } = {},
) => {
    const search = new URLSearchParams();
    if (params.start_date) search.set("start_date", params.start_date);
    if (params.end_date) search.set("end_date", params.end_date);
    if (params.exclude_transfers !== undefined) search.set("exclude_transfers", String(params.exclude_transfers));
    if (params.exclude_moment_tagged !== undefined) {
        search.set("exclude_moment_tagged", String(params.exclude_moment_tagged));
    }
    const query = search.toString();
    return apiFetch<FlowResponse>(`/analytics/flow${query ? `?${query}` : ""}`);
};

export const fetchAnalyticsPayees = async (
    params: {
        start_date?: string;
        end_date?: string;
        granularity?: AnalyticsGranularity;
        exclude_transfers?: boolean;
        exclude_moment_tagged?: boolean;
        mode?: AnalyticsMode;
        limit?: number;
    } = {},
) => {
    const search = new URLSearchParams();
    if (params.start_date) search.set("start_date", params.start_date);
    if (params.end_date) search.set("end_date", params.end_date);
    if (params.granularity) search.set("granularity", params.granularity);
    if (params.exclude_transfers !== undefined) search.set("exclude_transfers", String(params.exclude_transfers));
    if (params.exclude_moment_tagged !== undefined) {
        search.set("exclude_moment_tagged", String(params.exclude_moment_tagged));
    }
    if (params.mode) search.set("mode", params.mode);
    if (params.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiFetch<AnalyticsGroupedResponse>(`/analytics/payees${query ? `?${query}` : ""}`);
};

// --- Category drilldown types and functions ---

export type CategoryDrilldownTotals = {
    income_abs: number;
    expense_abs: number;
    refund_abs: number;
    transfer_abs: number;
    net: number;
    absolute_total: number;
};

export type CategoryDrilldownResponse = {
    category: {
        id: number | null;
        name: string;
        parent_id?: number | null;
        scope_type: "parent" | "child" | "uncategorized";
    };
    scope_category_ids: number[];
    totals: CategoryDrilldownTotals;
    transaction_count: number;
    branch_nodes: FlowNode[];
    branch_links: FlowLink[];
};

export type DrilldownTransactionRow = {
    transaction_id: number;
    posted_at: string;
    label_raw: string;
    type: string;
    payee: string | null;
    account: string | null;
    transaction_amount: number;
    branch_amount_abs: number;
    matched_split_count: number;
};

export type DrilldownTransactionsResponse = {
    rows: DrilldownTransactionRow[];
    total: number;
    limit: number;
    offset: number;
};

export const fetchCategoryDrilldown = async (
    categoryRef: string,
    params: {
        start_date?: string;
        end_date?: string;
        exclude_transfers?: boolean;
        exclude_moment_tagged?: boolean;
        include_children?: boolean;
    } = {},
) => {
    const search = new URLSearchParams();
    if (params.start_date) search.set("start_date", params.start_date);
    if (params.end_date) search.set("end_date", params.end_date);
    if (params.exclude_transfers !== undefined) search.set("exclude_transfers", String(params.exclude_transfers));
    if (params.exclude_moment_tagged !== undefined)
        search.set("exclude_moment_tagged", String(params.exclude_moment_tagged));
    if (params.include_children !== undefined) search.set("include_children", String(params.include_children));
    const query = search.toString();
    return apiFetch<CategoryDrilldownResponse>(`/analytics/category/${encodeURIComponent(categoryRef)}${query ? `?${query}` : ""}`);
};

export const fetchCategoryDrilldownTransactions = async (
    categoryRef: string,
    params: {
        start_date?: string;
        end_date?: string;
        exclude_transfers?: boolean;
        exclude_moment_tagged?: boolean;
        include_children?: boolean;
        limit?: number;
        offset?: number;
    } = {},
) => {
    const search = new URLSearchParams();
    if (params.start_date) search.set("start_date", params.start_date);
    if (params.end_date) search.set("end_date", params.end_date);
    if (params.exclude_transfers !== undefined) search.set("exclude_transfers", String(params.exclude_transfers));
    if (params.exclude_moment_tagged !== undefined)
        search.set("exclude_moment_tagged", String(params.exclude_moment_tagged));
    if (params.include_children !== undefined) search.set("include_children", String(params.include_children));
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    if (params.offset !== undefined) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiFetch<DrilldownTransactionsResponse>(
        `/analytics/category/${encodeURIComponent(categoryRef)}/transactions${query ? `?${query}` : ""}`,
    );
};

export const fetchAnalyticsInternalAccounts = async (
    params: {
        start_date?: string;
        end_date?: string;
        granularity?: AnalyticsGranularity;
        exclude_transfers?: boolean;
        exclude_moment_tagged?: boolean;
        mode?: AnalyticsMode;
        limit?: number;
    } = {},
) => {
    const search = new URLSearchParams();
    if (params.start_date) search.set("start_date", params.start_date);
    if (params.end_date) search.set("end_date", params.end_date);
    if (params.granularity) search.set("granularity", params.granularity);
    if (params.exclude_transfers !== undefined) search.set("exclude_transfers", String(params.exclude_transfers));
    if (params.exclude_moment_tagged !== undefined) {
        search.set("exclude_moment_tagged", String(params.exclude_moment_tagged));
    }
    if (params.mode) search.set("mode", params.mode);
    if (params.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiFetch<AnalyticsGroupedResponse>(`/analytics/internal-accounts${query ? `?${query}` : ""}`);
};

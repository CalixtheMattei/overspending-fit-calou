import { ApiError, apiFetch } from "./api";

export type AccountSummary = {
    id: number;
    account_num: string;
    label: string;
    currency?: string;
};

export type PayeeSummary = {
    id: number;
    name: string;
    kind: string;
};

export type TransactionSummary = {
    id: number;
    posted_at: string;
    operation_at: string;
    amount: string | number;
    currency: string;
    label_raw: string;
    supplier_raw: string | null;
    payee: PayeeSummary | null;
    account: AccountSummary | null;
    type: string;
    comment: string | null;
    splits_sum: string | number;
    splits_count: number;
    is_balanced: boolean;
    is_categorized: boolean;
    remaining_amount: string | number;
    single_category_id: number | null;
    single_category: CategorySummary | null;
    single_internal_account_id: number | null;
};

export type TransactionListResponse = {
    rows: TransactionSummary[];
    limit: number;
    offset: number;
    total: number;
};

export type CategorySummary = {
    id: number;
    name: string;
    parent_id: number | null;
    color: string;
    icon: string;
    is_custom: boolean;
    display_name?: string | null;
};

export type MomentSummary = {
    id: number;
    name: string;
    start_date?: string;
    end_date?: string;
    description?: string | null;
};

export type InternalAccountSummary = {
    id: number;
    name: string;
    type: string | null;
    position: number;
    is_archived: boolean;
};

export type SplitDetail = {
    id: number;
    amount: string | number;
    category_id: number | null;
    category: CategorySummary | null;
    moment_id: number | null;
    moment: MomentSummary | null;
    internal_account_id: number | null;
    internal_account: InternalAccountSummary | null;
    note: string | null;
    position: number;
};

export type CategoryProvenance = {
    source: "uncategorized" | "manual" | "rule" | "import_default" | "mixed";
    last_applied_at: string | null;
    rule: {
        id: number;
        name: string;
    } | null;
};

export type TransactionDetail = {
    transaction: {
        id: number;
        posted_at: string;
        operation_at: string;
        amount: string | number;
        currency: string;
        label_raw: string;
        supplier_raw: string | null;
        type: string;
        comment: string | null;
        payee: PayeeSummary | null;
        account: AccountSummary | null;
    };
    splits: SplitDetail[];
    splits_sum: string | number;
    splits_count: number;
    is_balanced: boolean;
    is_categorized: boolean;
    remaining_amount: string | number;
    category_provenance: CategoryProvenance;
};

export type TransactionsSummary = {
    uncategorized_count: number;
    uncategorized_total_abs: string | number;
    categorized_percent_30d: number;
};

export const fetchTransactions = async (
    params: {
        status?: string;
        type?: string;
        q?: string;
        payee_id?: number | null;
        category_id?: number | null;
        internal_account_id?: number | null;
        bank_account_id?: number | null;
        limit?: number;
        offset?: number;
    } = {},
) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.type) search.set("type", params.type);
    if (params.q) search.set("q", params.q);
    if (params.payee_id) search.set("payee_id", String(params.payee_id));
    if (params.category_id) search.set("category_id", String(params.category_id));
    if (params.internal_account_id) search.set("internal_account_id", String(params.internal_account_id));
    if (params.bank_account_id) search.set("bank_account_id", String(params.bank_account_id));
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiFetch<TransactionListResponse>(`/transactions${query ? `?${query}` : ""}`);
};

export const fetchTransaction = async (transactionId: number) =>
    apiFetch<TransactionDetail>(`/transactions/${transactionId}`);

export const updateTransaction = async (
    transactionId: number,
    payload: { payee_id?: number | null; type?: string; comment?: string | null },
) =>
    apiFetch<TransactionDetail>(`/transactions/${transactionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const replaceTransactionSplits = async (
    transactionId: number,
    payload: {
        splits: {
            id?: number;
            amount: string | number;
            category_id: number | null;
            moment_id?: number | null;
            internal_account_id?: number | null;
            note?: string | null;
        }[];
        confirm_reassign?: boolean;
    },
) =>
    apiFetch<TransactionDetail>(`/transactions/${transactionId}/splits`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

const SPLIT_ERROR_MESSAGES: Record<string, string> = {
    SPLIT_SUM_MISMATCH: "Split total must equal transaction amount.",
    SPLIT_SIGN_MISMATCH: "Split amounts must match transaction sign.",
    SPLIT_AMOUNT_INVALID: "One or more split amounts are invalid.",
    SPLIT_ID_DUPLICATE: "The same split ID appears more than once in the payload.",
    SPLIT_ID_NOT_FOUND: "One or more split IDs do not belong to this transaction.",
    CATEGORY_NOT_FOUND: "One or more selected categories could not be found.",
    CATEGORY_ASSIGNMENT_NOT_ALLOWED: "Category assignment is not allowed for this transaction type.",
    INTERNAL_ACCOUNT_NOT_FOUND: "One or more selected internal accounts could not be found.",
    MOMENT_NOT_FOUND: "One or more selected moments could not be found.",
    MOMENT_REASSIGN_CONFIRM_REQUIRED: "Changing a split from one moment to another requires confirmation.",
};

const resolveSplitErrorCode = (error: unknown): string | null => {
    if (typeof error === "string") {
        return error;
    }
    if (error instanceof ApiError) {
        if (typeof error.detail === "string") {
            return error.detail;
        }
        if (error.detail && typeof error.detail === "object") {
            const code = (error.detail as { code?: unknown }).code;
            if (typeof code === "string") {
                return code;
            }
        }
        return error.message || null;
    }
    if (error instanceof Error) {
        return error.message;
    }
    return null;
};

export const isSplitReassignConflictError = (error: unknown): boolean => {
    if (!(error instanceof ApiError) || error.status !== 409) {
        return false;
    }
    if (!error.detail || typeof error.detail !== "object") {
        return false;
    }
    return (error.detail as { code?: unknown }).code === "MOMENT_REASSIGN_CONFIRM_REQUIRED";
};

export const mapSplitErrorMessage = (error: unknown): string => {
    const code = resolveSplitErrorCode(error);
    if (code && SPLIT_ERROR_MESSAGES[code]) {
        return SPLIT_ERROR_MESSAGES[code];
    }

    if (error instanceof ApiError) {
        if (error.detail && typeof error.detail === "object") {
            const detailMessage = (error.detail as { message?: unknown }).message;
            if (typeof detailMessage === "string" && detailMessage.trim()) {
                return detailMessage;
            }
        }
        return error.message || "Failed to save splits.";
    }

    if (error instanceof Error) {
        return error.message;
    }

    if (typeof error === "string" && error.trim()) {
        return error;
    }

    return "Failed to save splits.";
};

export const fetchTransactionsSummary = async () => apiFetch<TransactionsSummary>("/transactions/summary");

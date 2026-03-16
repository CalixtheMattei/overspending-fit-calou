import { apiFetch } from "./api";

export type Rule = {
    id: number;
    name: string;
    priority: number;
    enabled: boolean;
    source: string | null;
    source_ref: string | null;
    matcher_json: Record<string, unknown>;
    action_json: Record<string, unknown>;
    created_at: string;
    updated_at: string;
};

export type RuleRunBatch = {
    id: number;
    trigger_type: string;
    scope_json: Record<string, unknown>;
    mode: "dry_run" | "apply";
    allow_overwrite: boolean;
    started_at: string;
    finished_at: string | null;
    created_by: string | null;
    summary_json: Record<string, number> | null;
};

export type TransactionRuleHistoryRow = {
    id: number;
    batch_id: number;
    rule_id: number;
    transaction_id: number;
    status: string;
    reason_code: string | null;
    applied_at: string;
    rule?: {
        id: number;
        name: string;
        priority: number;
        enabled: boolean;
    };
};

export type TransactionRuleHistoryResponse = {
    rows: TransactionRuleHistoryRow[];
    limit: number;
    offset: number;
    total: number;
};

export type RulePreviewScope =
    | { type: "all" }
    | { type: "import"; import_id: number }
    | { type: "date_range"; date_from?: string; date_to?: string };

export type RulePreviewRow = {
    transaction_id: number;
    posted_at: string;
    label_raw: string;
    amount: string | number;
    currency: string;
    before: {
        payee_id: number | null;
        type: string | null;
        category_id: number | null;
        has_splits: boolean;
    };
    after: {
        payee_id: number | null;
        type: string | null;
        category_id: number | null;
        has_splits: boolean;
    };
    changed_fields: string[];
};

export type RulePreviewResponse = {
    transactions_scanned: number;
    transactions_matched: number;
    transactions_changed: number;
    match_count: number;
    rows: RulePreviewRow[];
    sample: RulePreviewRow[];
    limit: number;
    offset: number;
    total: number;
};

export const fetchRules = async () => apiFetch<Rule[]>("/rules");

export const createRule = async (payload: {
    name: string;
    priority?: number;
    enabled: boolean;
    matcher_json: Record<string, unknown>;
    action_json: Record<string, unknown>;
    source?: string | null;
    source_ref?: string | null;
}) =>
    apiFetch<Rule>("/rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const updateRule = async (
    ruleId: number,
    payload: {
        name?: string;
        priority?: number;
        enabled?: boolean;
        matcher_json?: Record<string, unknown>;
        action_json?: Record<string, unknown>;
        source?: string | null;
        source_ref?: string | null;
    },
) =>
    apiFetch<Rule>(`/rules/${ruleId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const runRules = async (payload: {
    scope: "import" | "date_range" | "all";
    mode: "dry_run" | "apply";
    allow_overwrite: boolean;
    rule_ids?: number[];
    import_id?: number;
    date_from?: string;
    date_to?: string;
}) =>
    apiFetch<RuleRunBatch>("/rules/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const previewRule = async (payload: {
    scope: RulePreviewScope;
    matcher_json: Record<string, unknown>;
    action_json: Record<string, unknown>;
    mode: "non_destructive" | "destructive";
    limit?: number;
    offset?: number;
}) =>
    apiFetch<RulePreviewResponse>("/rules/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const fetchTransactionRuleHistory = async (
    transactionId: number,
    params: { limit?: number; offset?: number } = {},
) => {
    const search = new URLSearchParams();
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiFetch<TransactionRuleHistoryResponse>(
        `/transactions/${transactionId}/rule-history${query ? `?${query}` : ""}`,
    );
};

export const previewDeleteRule = async (ruleId: number, rollback = true) =>
    apiFetch<{
        total_impacted: number;
        reverted_to_uncategorized: number;
        skipped_conflict: number;
        skipped_not_latest: number;
        deleted: false;
        impacted: { transaction_id: number; effect_id: number; reversible: boolean; reason: string | null }[];
    }>(`/rules/${ruleId}?mode=preview&rollback=${rollback ? "true" : "false"}`, {
        method: "DELETE",
    });

export const confirmDeleteRule = async (ruleId: number, rollback = true) =>
    apiFetch<{
        total_impacted: number;
        reverted_to_uncategorized: number;
        skipped_conflict: number;
        skipped_not_latest: number;
        deleted: true;
    }>(`/rules/${ruleId}?mode=confirm&rollback=${rollback ? "true" : "false"}`, {
        method: "DELETE",
    });

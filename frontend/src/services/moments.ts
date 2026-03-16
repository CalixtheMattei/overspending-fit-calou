import { ApiError, apiFetch } from "./api";

export type MomentTopCategory = {
    category_id: number;
    name: string;
    amount: number;
    percentage: number;
    is_other?: boolean;
};

export type Moment = {
    id: number;
    name: string;
    start_date?: string | null;
    end_date?: string | null;
    description?: string | null;
    cover_image_url?: string | null;
    created_at?: string;
    updated_at?: string;
    tagged_splits_count?: number;
    expenses_total?: number;
    income_total?: number;
    top_categories?: MomentTopCategory[];
};

export type MomentCandidateStatus = "pending" | "accepted" | "rejected";

export type MomentCandidateStatusCounts = {
    pending: number;
    accepted: number;
    rejected: number;
};

export type MomentTaggedSplitRow = {
    split_id: number;
    transaction_id: number;
    operation_at: string;
    posted_at?: string | null;
    label_raw: string;
    supplier_raw?: string | null;
    amount: string | number;
    currency: string;
    category_id?: number | null;
    category_name?: string | null;
    internal_account_id?: number | null;
    account_label?: string | null;
    note?: string | null;
    position?: number;
};

export type MomentCandidateRow = {
    candidate_id: number;
    split_id: number;
    transaction_id: number;
    status: MomentCandidateStatus;
    operation_at: string;
    posted_at?: string | null;
    label_raw: string;
    supplier_raw?: string | null;
    amount: string | number;
    currency: string;
    category_id?: number | null;
    internal_account_id?: number | null;
    note?: string | null;
    position?: number;
    first_seen_at?: string | null;
    last_seen_at?: string | null;
    decided_at?: string | null;
};

export type PagedRowsResponse<T> = {
    rows: T[];
    limit: number;
    offset: number;
    total: number;
};

export type MomentCandidatesPagedResponse = PagedRowsResponse<MomentCandidateRow> & {
    status_counts: MomentCandidateStatusCounts;
};

export type CreateMomentPayload = {
    name: string;
    start_date: string;
    end_date: string;
    description?: string | null;
    cover_image_url?: string | null;
};

export type MomentTaggedMutationResponse = {
    updated_count: number;
};

export type MomentCandidatesRefreshResponse = {
    moment_id: number;
    inserted_count: number;
    touched_count: number;
    status_counts: MomentCandidateStatusCounts;
};

export type DecideMomentCandidatesPayload = {
    split_ids: number[];
    decision: "accepted" | "rejected";
    confirm_reassign?: boolean;
};

export type MomentDecisionResponse = {
    moment_id: number;
    decision: "accepted" | "rejected";
    updated_count: number;
    reassigned_count: number;
    status_counts: MomentCandidateStatusCounts;
};

type BackendMoment = {
    id: number;
    name: string;
    start_date?: string | null;
    end_date?: string | null;
    description?: string | null;
    cover_image_url?: string | null;
    created_at?: string;
    updated_at?: string;
    tagged_splits_count?: number;
    expenses_total?: number;
    income_total?: number;
    top_categories?: MomentTopCategory[];
};

type BackendTaggedRow = {
    split_id: number;
    transaction_id: number;
    operation_at: string;
    posted_at?: string | null;
    amount: string | number;
    currency: string;
    label_raw: string;
    supplier_raw?: string | null;
    category_id?: number | null;
    category_name?: string | null;
    internal_account_id?: number | null;
    internal_account_name?: string | null;
    note?: string | null;
    position?: number;
};

type BackendCandidateRow = {
    id: number;
    moment_id: number;
    split_id: number;
    status: MomentCandidateStatus;
    first_seen_at?: string | null;
    last_seen_at?: string | null;
    decided_at?: string | null;
    split: {
        id: number;
        transaction_id: number;
        amount: string | number;
        category_id?: number | null;
        moment_id?: number | null;
        internal_account_id?: number | null;
        note?: string | null;
        position?: number;
        operation_at: string;
        posted_at?: string | null;
        label_raw: string;
        supplier_raw?: string | null;
        currency: string;
    };
};

type BackendCandidatesRefreshResponse = {
    moment_id: number;
    inserted_count: number;
    touched_count: number;
    status_counts: MomentCandidateStatusCounts;
};

type BackendDecisionResponse = {
    moment_id: number;
    decision: "accepted" | "rejected";
    updated_count: number;
    reassigned_count: number;
    status_counts: MomentCandidateStatusCounts;
};

const mapBackendMoment = (row: BackendMoment): Moment => ({
    id: row.id,
    name: row.name,
    start_date: row.start_date,
    end_date: row.end_date,
    description: row.description ?? null,
    cover_image_url: row.cover_image_url ?? null,
    created_at: row.created_at,
    updated_at: row.updated_at,
    tagged_splits_count: row.tagged_splits_count,
    expenses_total: row.expenses_total ?? 0,
    income_total: row.income_total ?? 0,
    top_categories: row.top_categories ?? [],
});

const mapBackendTaggedRow = (row: BackendTaggedRow): MomentTaggedSplitRow => ({
    split_id: row.split_id,
    transaction_id: row.transaction_id,
    operation_at: row.operation_at,
    posted_at: row.posted_at ?? null,
    label_raw: row.label_raw,
    supplier_raw: row.supplier_raw ?? null,
    amount: row.amount,
    currency: row.currency,
    category_id: row.category_id ?? null,
    category_name: row.category_name ?? null,
    internal_account_id: row.internal_account_id ?? null,
    account_label: row.internal_account_name ?? null,
    note: row.note ?? null,
    position: row.position,
});

const mapBackendCandidateRow = (row: BackendCandidateRow): MomentCandidateRow => ({
    candidate_id: row.id,
    split_id: row.split_id,
    transaction_id: row.split.transaction_id,
    status: row.status,
    operation_at: row.split.operation_at,
    posted_at: row.split.posted_at ?? null,
    label_raw: row.split.label_raw,
    supplier_raw: row.split.supplier_raw ?? null,
    amount: row.split.amount,
    currency: row.split.currency,
    category_id: row.split.category_id ?? null,
    internal_account_id: row.split.internal_account_id ?? null,
    note: row.split.note ?? null,
    position: row.split.position,
    first_seen_at: row.first_seen_at ?? null,
    last_seen_at: row.last_seen_at ?? null,
    decided_at: row.decided_at ?? null,
});

export const fetchMoments = async (params: { q?: string; limit?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    const rows = await apiFetch<BackendMoment[]>(`/moments${query ? `?${query}` : ""}`);
    return rows.map(mapBackendMoment);
};

export const fetchMomentTaggedSplits = async (
    momentId: number,
    params: {
        q?: string;
        limit?: number;
        offset?: number;
    } = {},
): Promise<PagedRowsResponse<MomentTaggedSplitRow>> => {
    const limit = params.limit ?? 20;
    const offset = params.offset ?? 0;
    const search = new URLSearchParams();
    if (params.q && params.q.trim()) search.set("q", params.q.trim());
    search.set("limit", String(limit));
    search.set("offset", String(offset));
    const query = search.toString();
    const response = await apiFetch<PagedRowsResponse<BackendTaggedRow>>(`/moments/${momentId}/tagged${query ? `?${query}` : ""}`);
    return {
        ...response,
        rows: response.rows.map(mapBackendTaggedRow),
    };
};

export const fetchMomentCandidates = async (
    momentId: number,
    params: {
        status?: MomentCandidateStatus;
        limit?: number;
        offset?: number;
    } = {},
): Promise<MomentCandidatesPagedResponse> => {
    const limit = params.limit ?? 20;
    const offset = params.offset ?? 0;
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    search.set("limit", String(limit));
    search.set("offset", String(offset));
    const query = search.toString();
    const response = await apiFetch<PagedRowsResponse<BackendCandidateRow> & { status_counts: MomentCandidateStatusCounts }>(
        `/moments/${momentId}/candidates${query ? `?${query}` : ""}`,
    );
    return {
        ...response,
        rows: response.rows.map(mapBackendCandidateRow),
    };
};

export const createMoment = async (payload: CreateMomentPayload): Promise<Moment> => {
    const normalizedDescription = payload.description?.trim() ?? "";
    const response = await apiFetch<BackendMoment>("/moments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ...payload,
            description: normalizedDescription ? normalizedDescription : null,
        }),
    });
    return mapBackendMoment(response);
};

export const refreshMomentCandidates = async (momentId: number): Promise<MomentCandidatesRefreshResponse> => {
    return apiFetch<BackendCandidatesRefreshResponse>(`/moments/${momentId}/candidates/refresh`, {
        method: "POST",
    });
};

export const removeMomentTaggedSplits = async (
    momentId: number,
    payload: { split_ids: number[] },
): Promise<MomentTaggedMutationResponse> =>
    apiFetch<MomentTaggedMutationResponse>(`/moments/${momentId}/tagged/remove`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const moveMomentTaggedSplits = async (
    momentId: number,
    payload: { split_ids: number[]; target_moment_id: number; confirm_reassign?: boolean },
): Promise<MomentTaggedMutationResponse> =>
    apiFetch<MomentTaggedMutationResponse>(`/moments/${momentId}/tagged/move`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const decideMomentCandidates = async (
    momentId: number,
    payload: DecideMomentCandidatesPayload,
): Promise<MomentDecisionResponse> =>
    apiFetch<BackendDecisionResponse>(`/moments/${momentId}/candidates/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export type UpdateMomentPayload = {
    name?: string;
    start_date?: string;
    end_date?: string;
    description?: string | null;
    cover_image_url?: string | null;
};

export type DeleteMomentResponse = {
    id: number;
    deleted: boolean;
    untagged_splits_count: number;
};

export const updateMoment = async (momentId: number, payload: UpdateMomentPayload): Promise<Moment> => {
    const response = await apiFetch<BackendMoment>(`/moments/${momentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    return mapBackendMoment(response);
};

export const deleteMoment = async (momentId: number): Promise<DeleteMomentResponse> => {
    return apiFetch<DeleteMomentResponse>(`/moments/${momentId}`, {
        method: "DELETE",
    });
};

export const getApiErrorCode = (error: unknown): string | null => {
    if (!(error instanceof ApiError)) return null;
    if (!error.detail || typeof error.detail !== "object") return null;
    const code = (error.detail as { code?: unknown }).code;
    return typeof code === "string" ? code : null;
};

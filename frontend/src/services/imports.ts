import { apiFetch, API_BASE_URL } from "./api";

export type ImportStats = {
    row_count: number;
    created_count: number;
    linked_count: number;
    duplicate_count: number;
    error_count: number;
};

export type AccountSummary = {
    id: number;
    account_num: string;
    label: string;
};

export type ImportSummary = {
    id: number;
    file_name: string;
    file_hash: string;
    imported_at: string;
    account: AccountSummary | null;
    stats: ImportStats;
};

export type ImportRowSummary = {
    id: number;
    status: "created" | "linked" | "error";
    error_code: string | null;
    error_message: string | null;
    date_op: string | null;
    date_val: string | null;
    label_raw: string;
    supplier_raw: string | null;
    amount: string | number | null;
    currency: string;
    category_raw: string | null;
    category_parent_raw: string | null;
    comment_raw: string | null;
    balance_after: string | number | null;
    transaction_id: number | null;
};

export type ImportRowWithImport = ImportRowSummary & {
    import_id: number;
    imported_at: string;
    file_name: string;
    account: AccountSummary | null;
};

export type ImportRowDetail = ImportRowSummary & {
    raw_json: Record<string, string | number | null>;
    normalization_preview?: {
        label_norm: string;
        inferred_type: string | null;
        inferred_payee: string | null;
    };
    transaction?: {
        id: number;
        posted_at: string;
        amount: string | number;
        label_raw: string;
        type: string;
    } | null;
};

export type ImportRowsResponse = {
    rows: ImportRowSummary[];
    limit: number;
    offset: number;
    total: number;
};

export type ImportRowsWithImportResponse = {
    rows: ImportRowWithImport[];
    limit: number;
    offset: number;
    total: number;
};

export const fetchImports = async () => apiFetch<ImportSummary[]>("/imports");

export const fetchImport = async (importId: number) => apiFetch<ImportSummary>(`/imports/${importId}`);

export const fetchImportRows = async (
    importId: number,
    params: { status?: string; limit?: number; offset?: number } = {},
) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiFetch<ImportRowsResponse>(`/imports/${importId}/rows${query ? `?${query}` : ""}`);
};

export const fetchAllImportRows = async (
    params: {
        status?: string;
        q?: string;
        date_from?: string;
        date_to?: string;
        sort?: "date_val" | "amount";
        direction?: "asc" | "desc";
        limit?: number;
        offset?: number;
    } = {},
) => {
    const search = new URLSearchParams();
    if (params.status) search.set("status", params.status);
    if (params.q) search.set("q", params.q);
    if (params.date_from) search.set("date_from", params.date_from);
    if (params.date_to) search.set("date_to", params.date_to);
    if (params.sort) search.set("sort", params.sort);
    if (params.direction) search.set("direction", params.direction);
    if (params.limit) search.set("limit", String(params.limit));
    if (params.offset) search.set("offset", String(params.offset));
    const query = search.toString();
    return apiFetch<ImportRowsWithImportResponse>(`/imports/rows${query ? `?${query}` : ""}`);
};

export const fetchImportRow = async (importId: number, rowId: number) =>
    apiFetch<ImportRowDetail>(`/imports/${importId}/rows/${rowId}`);

const postImport = async (url: string, file: File, fallbackMessage: string) => {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${API_BASE_URL}${url}`, {
        method: "POST",
        body: formData,
    });

    if (!response.ok) {
        let message = fallbackMessage;
        try {
            const data = await response.json();
            if (data && typeof data.detail === "string") {
                message = data.detail;
            }
        } catch (error) {
            const text = await response.text();
            if (text) {
                message = text;
            }
        }
        throw new Error(message);
    }

    return (await response.json()) as { import_id?: number; stats: ImportStats };
};

export const previewImport = async (file: File) =>
    (await postImport("/imports/preview", file, "Failed to preview import")) as { stats: ImportStats };

export const confirmImport = async (file: File) =>
    (await postImport("/imports", file, "Failed to confirm import")) as { import_id: number; stats: ImportStats };

export const uploadImport = confirmImport;

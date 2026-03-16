import { apiFetch } from "./api";

export type Payee = {
    id: number;
    name: string;
    kind: string;
    transaction_count: number;
};

export type AutomaticPayeeSeed = {
    name: string;
    canonical_name: string;
    linked_transaction_count: number;
    is_ignored: boolean;
};

export type ApplyAutomaticPayeePayload = {
    seed_canonical_name: string;
    payee_name: string;
    kind: "unknown" | "person" | "merchant";
    overwrite_existing: boolean;
};

export type ApplyAutomaticPayeeResult = {
    payee: Payee;
    matched_transaction_count: number;
    updated_transaction_count: number;
    skipped_assigned_count: number;
};

export const fetchPayees = async (params: { q?: string; limit?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.limit) search.set("limit", String(params.limit));
    const query = search.toString();
    return apiFetch<Payee[]>(`/payees${query ? `?${query}` : ""}`);
};

export const fetchAutomaticPayees = async (params: { q?: string; limit?: number; include_ignored?: boolean } = {}) => {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (params.limit) search.set("limit", String(params.limit));
    if (params.include_ignored) search.set("include_ignored", "true");
    const query = search.toString();
    return apiFetch<AutomaticPayeeSeed[]>(`/payees/automatic${query ? `?${query}` : ""}`);
};

export const applyAutomaticPayee = async (payload: ApplyAutomaticPayeePayload) =>
    apiFetch<ApplyAutomaticPayeeResult>("/payees/automatic/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const ignoreAutomaticPayee = async (canonical_name: string) =>
    apiFetch<{ canonical_name: string; ignored: boolean }>("/payees/automatic/ignore", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ canonical_name }),
    });

export const restoreAutomaticPayee = async (canonical_name: string) =>
    apiFetch<{ canonical_name: string; ignored: boolean }>(`/payees/automatic/ignore/${encodeURIComponent(canonical_name)}`, {
        method: "DELETE",
    });

export const createPayee = async (payload: { name: string; kind?: string }) =>
    apiFetch<Payee>("/payees", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const updatePayee = async (payeeId: number, payload: { name?: string; kind?: string }) =>
    apiFetch<Payee>(`/payees/${payeeId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const deletePayee = async (payeeId: number) =>
    apiFetch<{ deleted: boolean; transaction_count: number }>(`/payees/${payeeId}`, {
        method: "DELETE",
    });

import { apiFetch } from "./api";

export type InternalAccount = {
    id: number;
    name: string;
    type: string | null;
    position: number;
    is_archived: boolean;
    split_count: number;
};

export const fetchInternalAccounts = async () => apiFetch<InternalAccount[]>("/internal-accounts");

export const createInternalAccount = async (payload: { name: string; type?: string | null; position?: number }) =>
    apiFetch<InternalAccount>("/internal-accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const updateInternalAccount = async (
    accountId: number,
    payload: { name?: string; type?: string | null; position?: number; is_archived?: boolean },
) =>
    apiFetch<InternalAccount>(`/internal-accounts/${accountId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const deleteInternalAccount = async (accountId: number) =>
    apiFetch<{ deleted: boolean; split_count: number }>(`/internal-accounts/${accountId}`, {
        method: "DELETE",
    });

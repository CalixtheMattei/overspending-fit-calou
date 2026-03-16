import { apiFetch } from "./api";

export type BankAccount = {
    id: number;
    account_num: string;
    label: string;
    currency?: string;
};

export const fetchAccounts = async () => apiFetch<BankAccount[]>("/accounts");

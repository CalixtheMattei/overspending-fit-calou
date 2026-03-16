import { useCallback, useMemo, useState } from "react";
import type { SplitDetail } from "@/services/transactions";

export type SplitDraft = {
    id?: number;
    amount: string;
    category_id: number | null;
    moment_id: number | null;
    internal_account_id: number | null;
    note: string;
};

export type SplitTotals = {
    sum: number;
    remaining: number;
    hasInvalid: boolean;
    parsedAmounts: number[];
};

export type SplitValidation = {
    isValid: boolean;
    message: string | null;
};

const cloneDrafts = (drafts: SplitDraft[]) => drafts.map((split) => ({ ...split }));

const normalizeSplitAmount = (value: string) => {
    const parsed = parseSplitAmount(value);
    if (Number.isNaN(parsed)) {
        return value.trim();
    }
    return roundToTwo(parsed).toFixed(2);
};

const normalizeDraft = (split: SplitDraft) => ({
    amount: normalizeSplitAmount(split.amount),
    category_id: split.category_id ?? null,
    moment_id: split.moment_id ?? null,
    internal_account_id: split.internal_account_id ?? null,
    note: split.note ?? "",
});

const areSplitArraysEqual = (left: SplitDraft[], right: SplitDraft[]) => {
    if (left.length !== right.length) {
        return false;
    }

    return left.every((split, index) => {
        const next = right[index];
        if (!next) {
            return false;
        }
        const normalizedLeft = normalizeDraft(split);
        const normalizedRight = normalizeDraft(next);
        return (
            normalizedLeft.amount === normalizedRight.amount &&
            normalizedLeft.category_id === normalizedRight.category_id &&
            normalizedLeft.moment_id === normalizedRight.moment_id &&
            normalizedLeft.internal_account_id === normalizedRight.internal_account_id &&
            normalizedLeft.note === normalizedRight.note
        );
    });
};

export const mapSplitDetailsToDrafts = (splits: SplitDetail[]): SplitDraft[] =>
    splits.map((split) => ({
        id: split.id,
        amount: String(split.amount ?? ""),
        category_id: split.category_id,
        moment_id: split.moment_id,
        internal_account_id: split.internal_account_id,
        note: split.note ?? "",
    }));

export const useSplitDraft = (transactionAmount: number) => {
    const [splitDrafts, setSplitDrafts] = useState<SplitDraft[]>([]);
    const [splitInitialSnapshot, setSplitInitialSnapshot] = useState<SplitDraft[]>([]);
    const [activeSplitIndex, setActiveSplitIndex] = useState<number | null>(null);

    const initializeDrafts = useCallback((drafts: SplitDraft[]) => {
        const nextDrafts = cloneDrafts(drafts);
        setSplitDrafts(nextDrafts);
        setSplitInitialSnapshot(nextDrafts);
        setActiveSplitIndex(null);
    }, []);

    const splitTotals = useMemo<SplitTotals>(() => {
        const parsedAmounts = splitDrafts.map((split) => parseSplitAmount(split.amount));
        const sum = parsedAmounts.reduce((total, value) => total + (Number.isNaN(value) ? 0 : value), 0);
        const roundedSum = roundToTwo(sum);
        const remaining = roundToTwo(transactionAmount - roundedSum);
        return {
            sum: roundedSum,
            remaining,
            hasInvalid: parsedAmounts.some((value) => Number.isNaN(value)),
            parsedAmounts,
        };
    }, [splitDrafts, transactionAmount]);

    const splitValidation = useMemo<SplitValidation>(() => {
        if (splitDrafts.length === 0) {
            return { isValid: true, message: null };
        }

        if (splitTotals.hasInvalid) {
            return { isValid: false, message: "Enter valid split amounts." };
        }

        const signMismatch = splitTotals.parsedAmounts.some((amount) =>
            transactionAmount < 0 ? amount > 0 : transactionAmount > 0 ? amount < 0 : false,
        );
        if (signMismatch) {
            return { isValid: false, message: "Split amounts must match the transaction sign." };
        }

        if (splitTotals.remaining !== 0) {
            return { isValid: false, message: "Split total must equal transaction amount." };
        }

        return { isValid: true, message: null };
    }, [splitDrafts, splitTotals, transactionAmount]);

    const splitDirty = useMemo(
        () => !areSplitArraysEqual(splitDrafts, splitInitialSnapshot),
        [splitDrafts, splitInitialSnapshot],
    );

    const setSplitField = useCallback((index: number, field: keyof SplitDraft, value: string | number | null) => {
        setSplitDrafts((drafts) => {
            if (!drafts[index]) {
                return drafts;
            }
            const next = [...drafts];
            next[index] = {
                ...next[index],
                [field]: value,
            };
            return next;
        });
    }, []);

    const addSplit = useCallback(() => {
        const nextAmount = splitTotals.remaining !== 0 ? splitTotals.remaining : transactionAmount;
        setSplitDrafts((drafts) => [
            ...drafts,
            {
                amount: String(roundToTwo(nextAmount)),
                category_id: null,
                moment_id: null,
                internal_account_id: null,
                note: "",
            },
        ]);
    }, [splitTotals.remaining, transactionAmount]);

    const fillRemaining = useCallback(() => {
        if (activeSplitIndex === null) {
            return;
        }
        setSplitDrafts((drafts) => {
            if (!drafts[activeSplitIndex]) {
                return drafts;
            }
            const next = [...drafts];
            next[activeSplitIndex] = {
                ...next[activeSplitIndex],
                amount: String(roundToTwo(splitTotals.remaining)),
            };
            return next;
        });
    }, [activeSplitIndex, splitTotals.remaining]);

    const makeSingleSplit = useCallback(() => {
        setSplitDrafts([
            {
                amount: String(roundToTwo(transactionAmount)),
                category_id: null,
                moment_id: null,
                internal_account_id: null,
                note: "",
            },
        ]);
        setActiveSplitIndex(0);
    }, [transactionAmount]);

    const deleteSplit = useCallback((index: number) => {
        setSplitDrafts((drafts) => drafts.filter((_, idx) => idx !== index));
        setActiveSplitIndex((prev) => {
            if (prev === null) {
                return prev;
            }
            if (prev === index) {
                return null;
            }
            if (prev > index) {
                return prev - 1;
            }
            return prev;
        });
    }, []);

    return {
        splitDrafts,
        splitTotals,
        splitValidation,
        splitDirty,
        activeSplitIndex,
        setActiveSplitIndex,
        initializeDrafts,
        setSplitField,
        addSplit,
        fillRemaining,
        makeSingleSplit,
        deleteSplit,
    };
};

const parseSplitAmount = (value: string) => {
    if (!value) return Number.NaN;
    const normalized = value.replace(",", ".");
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : Number.NaN;
};

const roundToTwo = (value: number) => Math.round(value * 100) / 100;

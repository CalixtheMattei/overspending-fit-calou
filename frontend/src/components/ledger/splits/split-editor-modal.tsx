import { useEffect, useState } from "react";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { INTERNAL_ACCOUNT_TYPE_OPTIONS } from "@/components/ledger/constants";
import { cx } from "@/utils/cx";
import { amountClass, formatAmount, formatDate } from "@/utils/format";
import { getCategoryDisplayLabel } from "@/components/ledger/categories/category-visuals";
import {
    CategoryCreateForm,
    makeEmptyDraft,
    type CategoryFormDraft,
} from "@/components/ledger/categories/category-create-form";
import type { Category, CategoryPresets } from "@/services/categories";
import type { InternalAccount } from "@/services/internal-accounts";
import type { Moment } from "@/services/moments";
import type { TransactionDetail } from "@/services/transactions";
import { SplitEditor } from "./split-editor";
import { mapSplitDetailsToDrafts, useSplitDraft, type SplitDraft } from "./use-split-draft";

type CreateCategoryModalState = {
    isOpen: boolean;
    targetIndex: number | null;
    draft: CategoryFormDraft;
};

type CreateInternalAccountModalState = {
    isOpen: boolean;
    targetIndex: number | null;
    name: string;
    type: string | null;
    error: string | null;
};

type SplitSaveResult = "saved" | "conflict_required" | "error";

interface SplitEditorModalProps {
    isOpen: boolean;
    loading: boolean;
    saving: boolean;
    error: string | null;
    transactionDetail: TransactionDetail | null;
    categories: Category[];
    categoryPresets: CategoryPresets;
    moments: Moment[];
    internalAccounts: InternalAccount[];
    onOpenChange: (open: boolean) => void;
    onSaveSplits: (splits: SplitDraft[], options?: { confirmReassign?: boolean }) => Promise<SplitSaveResult>;
    onCreateCategory: (payload: {
        name: string;
        parent_id?: number | null;
        color?: string | null;
        icon?: string | null;
    }) => Promise<Category>;
    onCreateInternalAccount: (payload: { name: string; type: string | null }) => Promise<InternalAccount>;
}

const getMomentReassignmentCount = (transactionDetail: TransactionDetail | null, splitDrafts: SplitDraft[]) => {
    if (!transactionDetail) {
        return 0;
    }

    const existingMomentBySplitId = new Map(transactionDetail.splits.map((split) => [split.id, split.moment_id]));
    return splitDrafts.reduce((count, split) => {
        if (typeof split.id !== "number") {
            return count;
        }
        const previousMomentId = existingMomentBySplitId.get(split.id);
        if (typeof previousMomentId !== "number") {
            return count;
        }
        if (split.moment_id === null || split.moment_id === previousMomentId) {
            return count;
        }
        return count + 1;
    }, 0);
};
const normalizeCategoryName = (name: string) =>
    name
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
const isUnknownRootCategory = (category: Category) =>
    category.parent_id === null && normalizeCategoryName(category.name) === "unknown";

export const SplitEditorModal = ({
    isOpen,
    loading,
    saving,
    error,
    transactionDetail,
    categories,
    categoryPresets,
    moments,
    internalAccounts,
    onOpenChange,
    onSaveSplits,
    onCreateCategory,
    onCreateInternalAccount,
}: SplitEditorModalProps) => {
    const transactionAmount = transactionDetail ? Number(transactionDetail.transaction.amount) : 0;
    const presetColors = categoryPresets.colors.length ? categoryPresets.colors : ["#9CA3AF"];
    const presetIcons = categoryPresets.icons.length ? categoryPresets.icons : ["tag"];
    const defaultColor = presetColors.includes(categoryPresets.default_color)
        ? categoryPresets.default_color
        : presetColors[0];
    const defaultIcon = presetIcons.includes(categoryPresets.default_icon)
        ? categoryPresets.default_icon
        : presetIcons[0];
    const parentCategories = categories
        .filter(
            (category) =>
                category.parent_id === null &&
                !category.is_deprecated &&
                !isUnknownRootCategory(category),
        )
        .sort((a, b) => getCategoryDisplayLabel(a).localeCompare(getCategoryDisplayLabel(b)));

    const {
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
    } = useSplitDraft(transactionAmount);

    const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
    const [showSingleSplitConfirm, setShowSingleSplitConfirm] = useState(false);
    const [showReassignConfirm, setShowReassignConfirm] = useState(false);
    const [pendingReassignSplits, setPendingReassignSplits] = useState<SplitDraft[] | null>(null);
    const [pendingReassignCount, setPendingReassignCount] = useState(0);

    const emptyCategoryModalState = (): CreateCategoryModalState => ({
        isOpen: false,
        targetIndex: null,
        draft: makeEmptyDraft({ color: defaultColor, icon: defaultIcon }),
    });

    const [categoryModal, setCategoryModal] = useState<CreateCategoryModalState>(
        emptyCategoryModalState(),
    );
    const [internalAccountModal, setInternalAccountModal] = useState<CreateInternalAccountModalState>({
        isOpen: false,
        targetIndex: null,
        name: "",
        type: null,
        error: null,
    });

    useEffect(() => {
        if (!transactionDetail) {
            initializeDrafts([]);
            return;
        }
        initializeDrafts(mapSplitDetailsToDrafts(transactionDetail.splits));
    }, [transactionDetail, initializeDrafts]);

    useEffect(() => {
        if (!isOpen) {
            setShowDiscardConfirm(false);
            setShowSingleSplitConfirm(false);
            setShowReassignConfirm(false);
            setPendingReassignSplits(null);
            setPendingReassignCount(0);
            setCategoryModal(emptyCategoryModalState());
            setInternalAccountModal({ isOpen: false, targetIndex: null, name: "", type: null, error: null });
        }
    }, [isOpen, defaultColor, defaultIcon]);

    const requestClose = () => {
        if (splitDirty && !saving) {
            setShowDiscardConfirm(true);
            return;
        }
        onOpenChange(false);
    };

    const requestReassignConfirm = (splits: SplitDraft[]) => {
        setPendingReassignSplits(splits.map((split) => ({ ...split })));
        setPendingReassignCount(Math.max(1, getMomentReassignmentCount(transactionDetail, splits)));
        setShowReassignConfirm(true);
    };

    const runSaveSplits = async (splits: SplitDraft[], confirmReassign: boolean) => {
        const result = await onSaveSplits(splits, { confirmReassign });
        if (result === "conflict_required") {
            requestReassignConfirm(splits);
        }
    };

    const handleSave = async () => {
        if (!transactionDetail || !splitValidation.isValid || saving || loading) {
            return;
        }

        const reassignmentCount = getMomentReassignmentCount(transactionDetail, splitDrafts);
        if (reassignmentCount > 0) {
            requestReassignConfirm(splitDrafts);
            return;
        }

        await runSaveSplits(splitDrafts, false);
    };

    return (
        <>
            <ModalOverlay isOpen={isOpen} onOpenChange={(open) => (!open ? requestClose() : null)}>
                <Modal>
                    <Dialog className="max-w-5xl rounded-2xl bg-primary p-0 shadow-xl ring-1 ring-secondary">
                        <div className="flex max-h-[min(92vh,960px)] w-full flex-col">
                            <div className="border-b border-secondary px-6 pt-6 pb-4">
                                <div className="flex items-start justify-between gap-4">
                                    <div className="flex flex-col gap-2">
                                        <h3 className="text-lg font-semibold text-primary">Split editor</h3>
                                        {transactionDetail && (
                                            <div className="flex flex-wrap items-center gap-3 text-sm text-tertiary">
                                                <span>{formatDate(transactionDetail.transaction.posted_at)}</span>
                                                {transactionDetail.transaction.account && (
                                                    <Badge size="sm" color="gray">
                                                        {transactionDetail.transaction.account.label}
                                                    </Badge>
                                                )}
                                                <span
                                                    className={cx(
                                                        "font-semibold",
                                                        amountClass(transactionDetail.transaction.amount),
                                                    )}
                                                >
                                                    {formatAmount(
                                                        transactionDetail.transaction.amount,
                                                        transactionDetail.transaction.currency,
                                                    )}
                                                </span>
                                            </div>
                                        )}
                                    </div>
                                    <Button color="tertiary" isDisabled={saving} onClick={requestClose}>
                                        Cancel
                                    </Button>
                                </div>
                            </div>

                            <div className="overflow-y-auto px-6 py-5">
                                {loading ? (
                                    <div className="flex justify-center py-16">
                                        <LoadingIndicator label="Loading transaction..." />
                                    </div>
                                ) : error && !transactionDetail ? (
                                    <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                                        {error}
                                    </div>
                                ) : transactionDetail ? (
                                    <div className="flex flex-col gap-4">
                                        <div className="rounded-xl bg-secondary p-4">
                                            <div className="text-sm font-medium text-primary">
                                                {transactionDetail.transaction.label_raw || "Untitled transaction"}
                                            </div>
                                            <div className="mt-1 text-xs text-tertiary">
                                                {transactionDetail.transaction.supplier_raw || "No supplier details"}
                                            </div>
                                        </div>
                                        <SplitEditor
                                            transactionAmount={transactionAmount}
                                            currency={transactionDetail.transaction.currency}
                                            splitDrafts={splitDrafts}
                                            splitTotals={splitTotals}
                                            splitValidation={splitValidation}
                                            activeSplitIndex={activeSplitIndex}
                                            categories={categories}
                                            moments={moments}
                                            internalAccounts={internalAccounts}
                                            onActiveSplitIndexChange={setActiveSplitIndex}
                                            onAddSplit={addSplit}
                                            onFillRemaining={fillRemaining}
                                            onSingleSplit={() => {
                                                if (splitDrafts.length > 1) {
                                                    setShowSingleSplitConfirm(true);
                                                    return;
                                                }
                                                makeSingleSplit();
                                            }}
                                            onSplitFieldChange={setSplitField}
                                            onSplitDelete={deleteSplit}
                                            onCreateCategoryRequest={(index) =>
                                                setCategoryModal({
                                                    isOpen: true,
                                                    targetIndex: index,
                                                    draft: makeEmptyDraft({ color: defaultColor, icon: defaultIcon }),
                                                })
                                            }
                                            onCreateInternalAccountRequest={(index) =>
                                                setInternalAccountModal({
                                                    isOpen: true,
                                                    targetIndex: index,
                                                    name: "",
                                                    type: null,
                                                    error: null,
                                                })
                                            }
                                        />
                                    </div>
                                ) : (
                                    <div className="text-sm text-tertiary">Select a transaction to edit splits.</div>
                                )}
                            </div>

                            <div className="border-t border-secondary px-6 py-4">
                                <div className="flex flex-col gap-3">
                                    {error && transactionDetail && (
                                        <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                            {error}
                                        </div>
                                    )}
                                    <div className="flex justify-end gap-2">
                                        <Button color="tertiary" isDisabled={saving} onClick={requestClose}>
                                            Cancel
                                        </Button>
                                        <DemoGuard>
                                            <Button
                                                color="primary"
                                                isDisabled={!transactionDetail || !splitValidation.isValid || saving || loading}
                                                onClick={handleSave}
                                            >
                                                {saving ? "Saving..." : "Save splits"}
                                            </Button>
                                        </DemoGuard>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={showDiscardConfirm} onOpenChange={(open) => !open && setShowDiscardConfirm(false)}>
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Discard split changes?</h4>
                                <p className="text-sm text-tertiary">
                                    You have unsaved split edits. Discard changes or continue editing.
                                </p>
                            </div>
                            <div className="flex justify-end gap-2">
                                <Button color="tertiary" onClick={() => setShowDiscardConfirm(false)}>
                                    Keep editing
                                </Button>
                                <Button
                                    color="secondary-destructive"
                                    onClick={() => {
                                        setShowDiscardConfirm(false);
                                        onOpenChange(false);
                                    }}
                                >
                                    Discard changes
                                </Button>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={showSingleSplitConfirm} onOpenChange={(open) => !open && setShowSingleSplitConfirm(false)}>
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Replace existing splits?</h4>
                                <p className="text-sm text-tertiary">
                                    This will replace all current split rows with one split for the full transaction amount.
                                </p>
                            </div>
                            <div className="flex justify-end gap-2">
                                <Button color="tertiary" onClick={() => setShowSingleSplitConfirm(false)}>
                                    Cancel
                                </Button>
                                <Button
                                    color="secondary-destructive"
                                    onClick={() => {
                                        makeSingleSplit();
                                        setShowSingleSplitConfirm(false);
                                    }}
                                >
                                    Replace with single split
                                </Button>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay
                isOpen={showReassignConfirm}
                onOpenChange={(open) => {
                    if (!open) {
                        setShowReassignConfirm(false);
                        setPendingReassignSplits(null);
                        setPendingReassignCount(0);
                    }
                }}
            >
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Confirm moment reassignment?</h4>
                                <p className="text-sm text-tertiary">
                                    {pendingReassignCount === 1
                                        ? "One split is moving from one moment to another."
                                        : `${pendingReassignCount} splits are moving from one moment to another.`}{" "}
                                    Continue saving changes?
                                </p>
                            </div>
                            <div className="flex justify-end gap-2">
                                <Button
                                    color="tertiary"
                                    isDisabled={saving}
                                    onClick={() => {
                                        setShowReassignConfirm(false);
                                        setPendingReassignSplits(null);
                                        setPendingReassignCount(0);
                                    }}
                                >
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button
                                        color="primary"
                                        isDisabled={saving || !pendingReassignSplits}
                                        onClick={async () => {
                                            if (!pendingReassignSplits) {
                                                return;
                                            }
                                            const splits = pendingReassignSplits;
                                            setShowReassignConfirm(false);
                                            setPendingReassignSplits(null);
                                            setPendingReassignCount(0);
                                            await runSaveSplits(splits, true);
                                        }}
                                    >
                                        {saving ? "Saving..." : "Confirm and save"}
                                    </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay
                isOpen={categoryModal.isOpen}
                onOpenChange={(open) => !open && setCategoryModal(emptyCategoryModalState())}
            >
                <Modal className="flex items-center justify-center">
                    <Dialog className="max-w-lg rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Create category</h4>
                                <p className="text-sm text-tertiary">Add a category with optional parent, color, and icon.</p>
                            </div>
                            <CategoryCreateForm
                                draft={categoryModal.draft}
                                onChange={(patch) =>
                                    setCategoryModal((prev) => ({
                                        ...prev,
                                        draft: { ...prev.draft, ...patch },
                                    }))
                                }
                                parentCategories={parentCategories}
                                colors={presetColors}
                                icons={presetIcons}
                            />
                            {categoryModal.draft.error && (
                                <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                    {categoryModal.draft.error}
                                </div>
                            )}
                            <div className="flex justify-end gap-2">
                                <Button
                                    color="tertiary"
                                    onClick={() => setCategoryModal(emptyCategoryModalState())}
                                >
                                    Cancel
                                </Button>
                                <DemoGuard>
                                <Button
                                    color="primary"
                                    isDisabled={categoryModal.draft.saving}
                                    onClick={async () => {
                                        if (categoryModal.targetIndex === null) return;
                                        const name = categoryModal.draft.name.trim();
                                        if (!name) {
                                            setCategoryModal((prev) => ({
                                                ...prev,
                                                draft: { ...prev.draft, error: "Name is required." },
                                            }));
                                            return;
                                        }
                                        const parentId =
                                            categoryModal.draft.parentId === "none"
                                                ? null
                                                : Number(categoryModal.draft.parentId);
                                        if (parentId !== null) {
                                            const parent = categories.find((category) => category.id === parentId);
                                            if (parent && isUnknownRootCategory(parent)) {
                                                setCategoryModal((prev) => ({
                                                    ...prev,
                                                    draft: {
                                                        ...prev.draft,
                                                        saving: false,
                                                        error: "Unknown category cannot have subcategories.",
                                                    },
                                                }));
                                                return;
                                            }
                                        }
                                        setCategoryModal((prev) => ({
                                            ...prev,
                                            draft: { ...prev.draft, saving: true, error: null },
                                        }));
                                        try {
                                            const created = await onCreateCategory({
                                                name,
                                                parent_id: parentId,
                                                color: categoryModal.draft.color,
                                                icon: categoryModal.draft.icon,
                                            });
                                            setSplitField(categoryModal.targetIndex, "category_id", created.id);
                                            setCategoryModal(emptyCategoryModalState());
                                        } catch (createError) {
                                            setCategoryModal((prev) => ({
                                                ...prev,
                                                draft: {
                                                    ...prev.draft,
                                                    saving: false,
                                                    error:
                                                        createError instanceof Error
                                                            ? createError.message
                                                            : "Failed to create category.",
                                                },
                                            }));
                                        }
                                    }}
                                >
                                    {categoryModal.draft.saving ? "Creating..." : "Create"}
                                </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay
                isOpen={internalAccountModal.isOpen}
                onOpenChange={(open) =>
                    !open && setInternalAccountModal({ isOpen: false, targetIndex: null, name: "", type: null, error: null })
                }
            >
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Create internal account</h4>
                                <p className="text-sm text-tertiary">Name your bucket and choose an optional type.</p>
                            </div>
                            <Input
                                label="Name"
                                placeholder="Savings"
                                value={internalAccountModal.name}
                                onChange={(value) => setInternalAccountModal((prev) => ({ ...prev, name: value }))}
                            />
                            <Select
                                label="Type"
                                items={INTERNAL_ACCOUNT_TYPE_OPTIONS}
                                selectedKey={internalAccountModal.type ?? "none"}
                                onSelectionChange={(key) => {
                                    if (!key || String(key) === "none") {
                                        setInternalAccountModal((prev) => ({ ...prev, type: null }));
                                        return;
                                    }
                                    setInternalAccountModal((prev) => ({ ...prev, type: String(key) }));
                                }}
                            >
                                {(item) => <Select.Item id={item.id} label={item.label} />}
                            </Select>
                            {internalAccountModal.error && (
                                <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                    {internalAccountModal.error}
                                </div>
                            )}
                            <div className="flex justify-end gap-2">
                                <Button
                                    color="tertiary"
                                    onClick={() =>
                                        setInternalAccountModal({ isOpen: false, targetIndex: null, name: "", type: null, error: null })
                                    }
                                >
                                    Cancel
                                </Button>
                                <DemoGuard>
                                <Button
                                    color="primary"
                                    onClick={async () => {
                                        if (internalAccountModal.targetIndex === null) return;
                                        const name = internalAccountModal.name.trim();
                                        if (!name) {
                                            setInternalAccountModal((prev) => ({ ...prev, error: "Name is required." }));
                                            return;
                                        }
                                        try {
                                            const created = await onCreateInternalAccount({
                                                name,
                                                type: internalAccountModal.type,
                                            });
                                            setSplitField(internalAccountModal.targetIndex, "internal_account_id", created.id);
                                            setInternalAccountModal({
                                                isOpen: false,
                                                targetIndex: null,
                                                name: "",
                                                type: null,
                                                error: null,
                                            });
                                        } catch (createError) {
                                            setInternalAccountModal((prev) => ({
                                                ...prev,
                                                error:
                                                    createError instanceof Error
                                                        ? createError.message
                                                        : "Failed to create internal account.",
                                            }));
                                        }
                                    }}
                                >
                                    Create
                                </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </>
    );
};

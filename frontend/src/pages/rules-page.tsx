import { useEffect, useMemo, useState } from "react";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Button } from "@/components/base/buttons/button";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { ImpactPreviewPanel } from "@/components/rules/impact-preview-panel";
import { RuleCreateModal } from "@/components/rules/rule-create-modal";
import { fetchCategories, type Category } from "@/services/categories";
import {
    confirmDeleteRule,
    fetchRules,
    previewDeleteRule,
    previewRule,
    updateRule,
    type Rule,
    type RulePreviewResponse,
} from "@/services/rules";

const getCategoryLabel = (category: Category | undefined) => (category ? category.display_name || category.name : "Unknown");

const getLabelContainsToken = (matcherJson: Record<string, unknown>) => {
    const all = matcherJson.all;
    if (!Array.isArray(all)) return null;
    const condition = all.find((row) => {
        if (!row || typeof row !== "object") return false;
        return (row as { predicate?: unknown }).predicate === "label_contains";
    });
    if (!condition || typeof condition !== "object") return null;
    const value = (condition as { value?: unknown }).value;
    return typeof value === "string" ? value : null;
};

const getSetCategoryId = (actionJson: Record<string, unknown>) => {
    const value = actionJson.set_category;
    if (typeof value !== "number") return null;
    return value;
};

type DeleteModalState = {
    isOpen: boolean;
    rule: Rule | null;
    preview: {
        total_impacted: number;
        reverted_to_uncategorized: number;
        skipped_conflict: number;
    } | null;
    loading: boolean;
    error: string | null;
};

type PreviewModalState = {
    isOpen: boolean;
    rule: Rule | null;
    data: RulePreviewResponse | null;
    loading: boolean;
    error: string | null;
};

export const RulesPage = () => {
    const [rules, setRules] = useState<Rule[]>([]);
    const [categories, setCategories] = useState<Category[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [createOpen, setCreateOpen] = useState(false);

    const [deleteModal, setDeleteModal] = useState<DeleteModalState>({
        isOpen: false,
        rule: null,
        preview: null,
        loading: false,
        error: null,
    });

    const [previewModal, setPreviewModal] = useState<PreviewModalState>({
        isOpen: false,
        rule: null,
        data: null,
        loading: false,
        error: null,
    });

    const orderedRules = useMemo(
        () => [...rules].sort((a, b) => a.priority - b.priority || a.id - b.id),
        [rules],
    );
    const categoryById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);

    const loadData = async () => {
        setLoading(true);
        setError(null);
        try {
            const [ruleRows, categoryRows] = await Promise.all([fetchRules(), fetchCategories({ limit: 200 })]);
            setRules(ruleRows);
            setCategories(categoryRows);
        } catch (fetchError) {
            setError(fetchError instanceof Error ? fetchError.message : "Failed to load rules.");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        void loadData();
    }, []);

    const handleToggleEnabled = async (rule: Rule) => {
        setError(null);
        try {
            const updated = await updateRule(rule.id, { enabled: !rule.enabled });
            setRules((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
        } catch (updateError) {
            setError(updateError instanceof Error ? updateError.message : "Failed to update rule.");
        }
    };

    const handleMoveRule = async (rule: Rule, direction: -1 | 1) => {
        const index = orderedRules.findIndex((row) => row.id === rule.id);
        const targetIndex = index + direction;
        if (index < 0 || targetIndex < 0 || targetIndex >= orderedRules.length) {
            return;
        }

        const target = orderedRules[targetIndex];
        setError(null);
        try {
            await Promise.all([
                updateRule(rule.id, { priority: target.priority }),
                updateRule(target.id, { priority: rule.priority }),
            ]);
            await loadData();
        } catch (moveError) {
            setError(moveError instanceof Error ? moveError.message : "Failed to reorder rules.");
        }
    };

    const handleDeleteClick = async (rule: Rule) => {
        setDeleteModal({ isOpen: true, rule, preview: null, loading: true, error: null });
        try {
            const preview = await previewDeleteRule(rule.id, true);
            setDeleteModal((prev) => ({
                ...prev,
                loading: false,
                preview: {
                    total_impacted: preview.total_impacted,
                    reverted_to_uncategorized: preview.reverted_to_uncategorized,
                    skipped_conflict: preview.skipped_conflict,
                },
            }));
        } catch (previewError) {
            setDeleteModal((prev) => ({
                ...prev,
                loading: false,
                error: previewError instanceof Error ? previewError.message : "Failed to load delete preview.",
            }));
        }
    };

    const handleDeleteConfirm = async () => {
        if (!deleteModal.rule) return;
        setDeleteModal((prev) => ({ ...prev, loading: true, error: null }));
        try {
            await confirmDeleteRule(deleteModal.rule.id, true);
            setDeleteModal({ isOpen: false, rule: null, preview: null, loading: false, error: null });
            await loadData();
        } catch (deleteError) {
            setDeleteModal((prev) => ({
                ...prev,
                loading: false,
                error: deleteError instanceof Error ? deleteError.message : "Failed to delete rule.",
            }));
        }
    };

    const handlePreviewClick = async (rule: Rule) => {
        setPreviewModal({ isOpen: true, rule, data: null, loading: true, error: null });
        try {
            const data = await previewRule({
                scope: { type: "all" },
                matcher_json: rule.matcher_json,
                action_json: rule.action_json,
                mode: "non_destructive",
                limit: 10,
            });
            setPreviewModal((prev) => ({ ...prev, loading: false, data }));
        } catch (previewError) {
            setPreviewModal((prev) => ({
                ...prev,
                loading: false,
                error: previewError instanceof Error ? previewError.message : "Failed to load preview.",
            }));
        }
    };

    return (
        <section className="flex flex-1 flex-col gap-6 p-6">
            <header className="flex flex-wrap items-start justify-between gap-4">
                <div className="space-y-1">
                    <h1 className="text-xl font-semibold text-primary">Rules Engine</h1>
                    <p className="text-sm text-tertiary">Create and apply one safe smart rule at a time with live impact preview.</p>
                </div>
                <Button color="primary" onClick={() => setCreateOpen(true)}>
                    New rule
                </Button>
            </header>

            {error ? (
                <div className="rounded-lg border border-error-secondary bg-error-primary p-3 text-sm text-error-primary">{error}</div>
            ) : null}

            <div className="rounded-2xl border border-secondary bg-primary p-4">
                <h2 className="text-sm font-medium text-secondary">Rules</h2>
                <p className="mb-3 mt-1 text-xs text-tertiary">Rules run top {"->"} bottom. First match wins.</p>

                {loading ? <p className="text-sm text-tertiary">Loading...</p> : null}
                {!loading && orderedRules.length === 0 ? <p className="text-sm text-tertiary">No rules yet.</p> : null}
                {!loading && orderedRules.length > 0 ? (
                    <div className="space-y-2">
                        {orderedRules.map((rule, index) => {
                            const labelToken = getLabelContainsToken(rule.matcher_json);
                            const setCategoryId = getSetCategoryId(rule.action_json);
                            const categoryName = getCategoryLabel(categoryById.get(setCategoryId ?? -1));
                            return (
                                <div
                                    key={rule.id}
                                    className="flex flex-col gap-3 rounded-xl border border-secondary p-3 md:flex-row md:items-center md:justify-between"
                                >
                                    <div className="space-y-1">
                                        <div className="flex items-center gap-2">
                                            <span className="min-w-[1.5rem] text-center text-xs font-semibold tabular-nums text-tertiary">
                                                {index + 1}
                                            </span>
                                            <span className="text-sm font-medium text-primary">{rule.name}</span>
                                            {!rule.enabled && (
                                                <span className="rounded-full bg-secondary px-2 py-0.5 text-xs text-tertiary">
                                                    disabled
                                                </span>
                                            )}
                                        </div>
                                        <div className="pl-8 text-xs text-tertiary">
                                            Match: {labelToken ? `"${labelToken}"` : "Custom matcher"} — Set: {categoryName}
                                        </div>
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <Button color="secondary" size="sm" onClick={() => void handlePreviewClick(rule)}>
                                            Preview
                                        </Button>
                                        <DemoGuard>
                                            <Button color="secondary" size="sm" isDisabled={index === 0} onClick={() => void handleMoveRule(rule, -1)}>
                                                Up
                                            </Button>
                                        </DemoGuard>
                                        <DemoGuard>
                                            <Button
                                                color="secondary"
                                                size="sm"
                                                isDisabled={index === orderedRules.length - 1}
                                                onClick={() => void handleMoveRule(rule, 1)}
                                            >
                                                Down
                                            </Button>
                                        </DemoGuard>
                                        <DemoGuard>
                                            <Button color="tertiary" size="sm" onClick={() => void handleToggleEnabled(rule)}>
                                                {rule.enabled ? "Disable" : "Enable"}
                                            </Button>
                                        </DemoGuard>
                                        <DemoGuard>
                                            <Button color="secondary" size="sm" onClick={() => void handleDeleteClick(rule)}>
                                                Delete
                                            </Button>
                                        </DemoGuard>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ) : null}
            </div>

            <RuleCreateModal isOpen={createOpen} onOpenChange={setCreateOpen} categories={categories} onSaved={loadData} />

            {/* Delete confirmation modal */}
            <ModalOverlay
                isOpen={deleteModal.isOpen}
                onOpenChange={(open) =>
                    !open && !deleteModal.loading && setDeleteModal({ isOpen: false, rule: null, preview: null, loading: false, error: null })
                }
            >
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Delete "{deleteModal.rule?.name}"?</h4>
                                <p className="mt-1 text-sm text-tertiary">
                                    This rule will be permanently removed and cannot be recovered.
                                </p>
                            </div>
                            {deleteModal.loading && !deleteModal.preview ? (
                                <p className="text-sm text-tertiary">Checking impact...</p>
                            ) : deleteModal.preview ? (
                                <div className="rounded-lg bg-secondary px-4 py-3 text-sm">
                                    <div className="flex justify-between text-tertiary">
                                        <span>Transactions affected</span>
                                        <span className="font-medium text-primary">{deleteModal.preview.total_impacted}</span>
                                    </div>
                                    <div className="mt-1 flex justify-between text-tertiary">
                                        <span>Will revert to uncategorized</span>
                                        <span className="font-medium text-primary">{deleteModal.preview.reverted_to_uncategorized}</span>
                                    </div>
                                    {deleteModal.preview.skipped_conflict > 0 && (
                                        <div className="mt-1 flex justify-between text-tertiary">
                                            <span>Skipped (manual override)</span>
                                            <span className="font-medium text-primary">{deleteModal.preview.skipped_conflict}</span>
                                        </div>
                                    )}
                                </div>
                            ) : null}
                            {deleteModal.error ? (
                                <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-sm text-error-primary">
                                    {deleteModal.error}
                                </div>
                            ) : null}
                            <div className="flex justify-end gap-2">
                                <Button
                                    color="tertiary"
                                    isDisabled={deleteModal.loading}
                                    onClick={() => setDeleteModal({ isOpen: false, rule: null, preview: null, loading: false, error: null })}
                                >
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button
                                        color="secondary-destructive"
                                        isDisabled={deleteModal.loading || !deleteModal.preview}
                                        onClick={() => void handleDeleteConfirm()}
                                    >
                                        {deleteModal.loading && deleteModal.preview ? "Deleting..." : "Delete rule"}
                                    </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            {/* Preview modal */}
            <ModalOverlay
                isOpen={previewModal.isOpen}
                onOpenChange={(open) =>
                    !open && setPreviewModal({ isOpen: false, rule: null, data: null, loading: false, error: null })
                }
            >
                <Modal>
                    <Dialog className="max-w-3xl rounded-2xl bg-primary p-0 shadow-xl ring-1 ring-secondary">
                        <div className="flex max-h-[80vh] flex-col">
                            <div className="flex items-start justify-between gap-4 border-b border-secondary px-6 py-4">
                                <div>
                                    <h4 className="text-lg font-semibold text-primary">
                                        Preview: {previewModal.rule?.name}
                                    </h4>
                                    <p className="text-sm text-tertiary">
                                        Transactions this rule would currently affect (non-destructive mode).
                                    </p>
                                </div>
                                <Button
                                    color="tertiary"
                                    size="sm"
                                    onClick={() => setPreviewModal({ isOpen: false, rule: null, data: null, loading: false, error: null })}
                                >
                                    Close
                                </Button>
                            </div>
                            <div className="overflow-y-auto p-6">
                                {previewModal.error ? (
                                    <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                                        {previewModal.error}
                                    </div>
                                ) : (
                                    <ImpactPreviewPanel
                                        previewReady={!previewModal.loading}
                                        previewLoading={previewModal.loading}
                                        previewError={null}
                                        previewData={previewModal.data}
                                        categoryById={categoryById}
                                        onViewAllMatches={() => undefined}
                                    />
                                )}
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </section>
    );
};

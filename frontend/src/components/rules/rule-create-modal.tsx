import { useEffect, useMemo, useState } from "react";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Button } from "@/components/base/buttons/button";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { ActionBuilder } from "@/components/rules/action-builder";
import { ImpactPreviewPanel } from "@/components/rules/impact-preview-panel";
import { MatchBuilder } from "@/components/rules/match-builder";
import type { Category } from "@/services/categories";
import { createRule, previewRule, runRules, type RulePreviewResponse, type RulePreviewRow } from "@/services/rules";
import { formatAmount, formatDate } from "@/utils/format";

type OverwriteMode = "non_destructive" | "destructive";

interface RuleCreateModalProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    categories: Category[];
    onSaved: () => Promise<void> | void;
}

const MATCHES_PAGE_LIMIT = 50;
const PREVIEW_PAGE_LIMIT = 10;
const LARGE_MATCH_THRESHOLD = 5000;

const getCategoryLabel = (category: Category) => category.display_name || category.name;
const getCategoryPreviewLabel = (categoryById: Map<number, Category>, categoryId: number | null) => {
    if (!categoryId) return "Uncategorized";
    const category = categoryById.get(categoryId);
    if (!category) return `#${categoryId}`;
    return category.display_name || category.name;
};

const buildMatcherJson = (labelContains: string) => ({
    all: [{ predicate: "label_contains", value: labelContains }],
});

const buildActionJson = (categoryId: number) => ({
    set_category: categoryId,
});

const mapErrorMessage = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

export const RuleCreateModal = ({ isOpen, onOpenChange, categories, onSaved }: RuleCreateModalProps) => {
    const sortedCategories = useMemo(
        () => [...categories].sort((a, b) => getCategoryLabel(a).localeCompare(getCategoryLabel(b))),
        [categories],
    );
    const categoryById = useMemo(() => new Map(categories.map((category) => [category.id, category])), [categories]);

    const [labelContains, setLabelContains] = useState("");
    const [categoryId, setCategoryId] = useState("");
    const [overwriteMode, setOverwriteMode] = useState<OverwriteMode>("non_destructive");
    const [view, setView] = useState<"form" | "matches">("form");

    const [previewData, setPreviewData] = useState<RulePreviewResponse | null>(null);
    const [previewLoading, setPreviewLoading] = useState(false);
    const [previewError, setPreviewError] = useState<string | null>(null);

    const [matchesOffset, setMatchesOffset] = useState(0);
    const [matchesRows, setMatchesRows] = useState<RulePreviewRow[]>([]);
    const [matchesTotal, setMatchesTotal] = useState(0);
    const [matchesLoading, setMatchesLoading] = useState(false);
    const [matchesError, setMatchesError] = useState<string | null>(null);

    const [confirmLargeImpact, setConfirmLargeImpact] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);

    const trimmedLabel = labelContains.trim();
    const parsedCategoryId = Number(categoryId);
    const previewReady = Boolean(trimmedLabel && Number.isFinite(parsedCategoryId));

    useEffect(() => {
        if (!isOpen) {
            return;
        }
        if (!categoryId && sortedCategories.length > 0) {
            setCategoryId(String(sortedCategories[0].id));
        }
    }, [isOpen, categoryId, sortedCategories]);

    useEffect(() => {
        if (!isOpen) {
            return;
        }
        if (!previewReady) {
            setPreviewLoading(false);
            setPreviewError(null);
            setPreviewData(null);
            return;
        }

        let isActive = true;
        const timeout = window.setTimeout(() => {
            const fetchPreview = async () => {
                setPreviewLoading(true);
                try {
                    const payload = {
                        scope: { type: "all" as const },
                        matcher_json: buildMatcherJson(trimmedLabel),
                        action_json: buildActionJson(parsedCategoryId),
                        mode: overwriteMode,
                        limit: PREVIEW_PAGE_LIMIT,
                        offset: 0,
                    };
                    const response = await previewRule(payload);
                    if (!isActive) return;
                    setPreviewData(response);
                    setPreviewError(null);
                    if (response.match_count <= LARGE_MATCH_THRESHOLD) {
                        setConfirmLargeImpact(false);
                    }
                } catch (error) {
                    if (!isActive) return;
                    setPreviewError(mapErrorMessage(error, "Failed to refresh preview."));
                } finally {
                    if (isActive) {
                        setPreviewLoading(false);
                    }
                }
            };
            void fetchPreview();
        }, 300);

        return () => {
            isActive = false;
            window.clearTimeout(timeout);
        };
    }, [isOpen, overwriteMode, parsedCategoryId, previewReady, trimmedLabel]);

    const loadMatchesPage = async (nextOffset: number) => {
        if (!previewReady) return;
        setMatchesLoading(true);
        setMatchesError(null);
        try {
            const response = await previewRule({
                scope: { type: "all" },
                matcher_json: buildMatcherJson(trimmedLabel),
                action_json: buildActionJson(parsedCategoryId),
                mode: overwriteMode,
                limit: MATCHES_PAGE_LIMIT,
                offset: nextOffset,
            });
            setMatchesRows(response.rows);
            setMatchesOffset(nextOffset);
            setMatchesTotal(response.total);
        } catch (error) {
            setMatchesError(mapErrorMessage(error, "Failed to load preview matches."));
        } finally {
            setMatchesLoading(false);
        }
    };

    const handleOpenMatches = async () => {
        setView("matches");
        await loadMatchesPage(0);
    };

    const resetState = () => {
        setLabelContains("");
        setCategoryId("");
        setOverwriteMode("non_destructive");
        setView("form");
        setPreviewData(null);
        setPreviewLoading(false);
        setPreviewError(null);
        setMatchesOffset(0);
        setMatchesRows([]);
        setMatchesTotal(0);
        setMatchesLoading(false);
        setMatchesError(null);
        setConfirmLargeImpact(false);
        setSaving(false);
        setSaveError(null);
    };

    const handleClose = () => {
        resetState();
        onOpenChange(false);
    };

    const handleSave = async () => {
        if (!previewReady || !previewData) {
            return;
        }

        setSaving(true);
        setSaveError(null);
        try {
            const created = await createRule({
                name: `Label contains "${trimmedLabel}"`,
                enabled: true,
                matcher_json: buildMatcherJson(trimmedLabel),
                action_json: buildActionJson(parsedCategoryId),
            });
            await runRules({
                scope: "all",
                mode: "apply",
                allow_overwrite: overwriteMode === "destructive",
                rule_ids: [created.id],
            });
            await onSaved();
            handleClose();
        } catch (error) {
            setSaveError(mapErrorMessage(error, "Failed to save and apply rule."));
        } finally {
            setSaving(false);
        }
    };

    const requiresLargeImpactConfirmation = (previewData?.match_count ?? 0) > LARGE_MATCH_THRESHOLD;
    const saveDisabled =
        !previewReady ||
        !previewData ||
        previewLoading ||
        saving ||
        (requiresLargeImpactConfirmation && !confirmLargeImpact);
    const matchesStart = matchesTotal === 0 ? 0 : matchesOffset + 1;
    const matchesEnd = Math.min(matchesOffset + MATCHES_PAGE_LIMIT, matchesTotal);

    return (
        <ModalOverlay isOpen={isOpen} onOpenChange={(open) => (!open ? handleClose() : null)}>
            <Modal>
                <Dialog className="max-h-[80vh] max-w-3xl overflow-y-auto rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                    <div className="flex w-full flex-col gap-4">
                        {view === "form" ? (
                            <>
                                <header className="space-y-1">
                                    <h2 className="text-lg font-semibold text-primary">New personalised smart rule</h2>
                                    <p className="text-sm text-tertiary">
                                        Build one rule, preview the impact, then save and apply. Default behavior targets uncategorized transactions only.
                                    </p>
                                </header>

                                <MatchBuilder labelContains={labelContains} onLabelContainsChange={setLabelContains} />
                                <ActionBuilder
                                    categories={sortedCategories}
                                    categoryId={categoryId}
                                    onCategoryIdChange={setCategoryId}
                                    overwriteMode={overwriteMode}
                                    onOverwriteModeChange={setOverwriteMode}
                                />
                                <ImpactPreviewPanel
                                    previewReady={previewReady}
                                    previewLoading={previewLoading}
                                    previewError={previewError}
                                    previewData={previewData}
                                    categoryById={categoryById}
                                    onViewAllMatches={() => void handleOpenMatches()}
                                />

                                {requiresLargeImpactConfirmation ? (
                                    <label className="flex items-start gap-2 rounded-lg border border-warning-secondary bg-warning-primary px-3 py-2 text-sm text-warning-primary">
                                        <input
                                            type="checkbox"
                                            checked={confirmLargeImpact}
                                            onChange={(event) => setConfirmLargeImpact(event.target.checked)}
                                        />
                                        <span>
                                            This rule affects more than {LARGE_MATCH_THRESHOLD} transactions. Confirm to enable save.
                                        </span>
                                    </label>
                                ) : null}

                                {saveError ? (
                                    <p className="rounded-md border border-error-secondary bg-error-primary px-3 py-2 text-sm text-error-primary">{saveError}</p>
                                ) : null}

                                <footer className="flex items-center justify-end gap-2">
                                    <Button color="tertiary" onClick={handleClose}>
                                        Cancel
                                    </Button>
                                    <DemoGuard>
                                        <Button color="primary" isDisabled={saveDisabled} isLoading={saving} onClick={handleSave}>
                                            Save & apply rule
                                        </Button>
                                    </DemoGuard>
                                </footer>
                            </>
                        ) : (
                            <>
                                <header className="flex items-start justify-between gap-3">
                                    <div className="space-y-1">
                                        <h2 className="text-lg font-semibold text-primary">Preview matches</h2>
                                        <p className="text-sm text-tertiary">Showing impacted transactions for this draft rule.</p>
                                    </div>
                                    <Button color="secondary" size="sm" onClick={() => setView("form")}>
                                        Back to rule
                                    </Button>
                                </header>

                                {matchesLoading ? <p className="text-sm text-tertiary">Loading preview rows...</p> : null}
                                {matchesError ? (
                                    <p className="rounded-md border border-error-secondary bg-error-primary px-3 py-2 text-sm text-error-primary">{matchesError}</p>
                                ) : null}
                                {!matchesLoading && matchesRows.length === 0 ? <p className="text-sm text-tertiary">No matches found.</p> : null}
                                {matchesRows.length > 0 ? (
                                    <div className="space-y-2">
                                        {matchesRows.map((row) => (
                                            <div
                                                key={row.transaction_id}
                                                className="grid grid-cols-[84px_1fr_120px_1fr] gap-3 rounded-lg border border-secondary px-3 py-2 text-xs"
                                            >
                                                <span className="text-tertiary">{formatDate(row.posted_at)}</span>
                                                <span className="truncate text-primary">{row.label_raw || "-"}</span>
                                                <span className="text-tertiary">{formatAmount(row.amount, row.currency)}</span>
                                                <span className="truncate text-primary">
                                                    {getCategoryPreviewLabel(categoryById, row.before.category_id)} {"->"}{" "}
                                                    {getCategoryPreviewLabel(categoryById, row.after.category_id)}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                ) : null}

                                <footer className="flex items-center justify-between gap-3 border-t border-secondary pt-3">
                                    <span className="text-xs text-tertiary">
                                        {matchesStart}-{matchesEnd} of {matchesTotal}
                                    </span>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            color="secondary"
                                            size="sm"
                                            isDisabled={matchesOffset === 0 || matchesLoading}
                                            onClick={() => void loadMatchesPage(Math.max(0, matchesOffset - MATCHES_PAGE_LIMIT))}
                                        >
                                            Previous
                                        </Button>
                                        <Button
                                            color="secondary"
                                            size="sm"
                                            isDisabled={matchesOffset + MATCHES_PAGE_LIMIT >= matchesTotal || matchesLoading}
                                            onClick={() => void loadMatchesPage(matchesOffset + MATCHES_PAGE_LIMIT)}
                                        >
                                            Next
                                        </Button>
                                    </div>
                                </footer>
                            </>
                        )}
                    </div>
                </Dialog>
            </Modal>
        </ModalOverlay>
    );
};

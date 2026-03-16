import { Button } from "@/components/base/buttons/button";
import type { Category } from "@/services/categories";
import type { RulePreviewResponse, RulePreviewRow } from "@/services/rules";
import { formatAmount, formatDate } from "@/utils/format";

interface ImpactPreviewPanelProps {
    previewReady: boolean;
    previewLoading: boolean;
    previewError: string | null;
    previewData: RulePreviewResponse | null;
    categoryById: Map<number, Category>;
    onViewAllMatches: () => void;
}

const getCategoryLabel = (categoryById: Map<number, Category>, categoryId: number | null) => {
    if (!categoryId) return "Uncategorized";
    const category = categoryById.get(categoryId);
    if (!category) return `#${categoryId}`;
    return category.display_name || category.name;
};

const PreviewRow = ({ row, categoryById }: { row: RulePreviewRow; categoryById: Map<number, Category> }) => (
    <div className="grid grid-cols-[84px_1fr_120px_1fr] gap-3 rounded-lg border border-secondary px-3 py-2 text-xs">
        <span className="text-tertiary">{formatDate(row.posted_at)}</span>
        <span className="truncate text-primary">{row.label_raw || "-"}</span>
        <span className="text-tertiary">{formatAmount(row.amount, row.currency)}</span>
        <span className="truncate text-primary">
            {getCategoryLabel(categoryById, row.before.category_id)} {"->"} {getCategoryLabel(categoryById, row.after.category_id)}
        </span>
    </div>
);

export const ImpactPreviewPanel = ({
    previewReady,
    previewLoading,
    previewError,
    previewData,
    categoryById,
    onViewAllMatches,
}: ImpactPreviewPanelProps) => {
    return (
        <section className="space-y-3 rounded-xl border border-secondary bg-primary p-4">
            <div className="flex items-center justify-between gap-4">
                <div>
                    <h3 className="text-sm font-semibold text-primary">Impact preview</h3>
                    <p className="text-xs text-tertiary">
                        {previewReady && previewData ? `Will affect: ${previewData.match_count} transaction(s)` : "Add a matcher to see impact"}
                    </p>
                </div>
                {previewData && previewData.match_count > 0 ? (
                    <Button color="secondary" size="sm" onClick={onViewAllMatches}>
                        View all matches
                    </Button>
                ) : null}
            </div>

            {previewLoading ? <p className="text-xs text-tertiary">Updating preview...</p> : null}
            {previewError ? (
                <p className="rounded-md border border-error-secondary bg-error-primary px-3 py-2 text-xs text-error-primary">{previewError}</p>
            ) : null}

            {previewData && previewData.sample.length > 0 ? (
                <div className="space-y-2">
                    {previewData.sample.map((row) => (
                        <PreviewRow key={row.transaction_id} row={row} categoryById={categoryById} />
                    ))}
                </div>
            ) : previewReady && !previewLoading ? (
                <p className="text-xs text-tertiary">No impacted transactions for the current rule.</p>
            ) : null}
        </section>
    );
};

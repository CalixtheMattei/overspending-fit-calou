import { SlideoutMenu } from "@/components/application/slideout-menus/slideout-menu";
import { Button } from "@/components/base/buttons/button";
import type { Category } from "@/services/categories";
import type { RulePreviewRow } from "@/services/rules";
import { formatAmount, formatDate } from "@/utils/format";

interface PreviewMatchesDrawerProps {
    isOpen: boolean;
    onOpenChange: (open: boolean) => void;
    rows: RulePreviewRow[];
    loading: boolean;
    error: string | null;
    offset: number;
    limit: number;
    total: number;
    categoryById: Map<number, Category>;
    onPageChange: (nextOffset: number) => void;
}

const getCategoryLabel = (categoryById: Map<number, Category>, categoryId: number | null) => {
    if (!categoryId) return "Uncategorized";
    const category = categoryById.get(categoryId);
    if (!category) return `#${categoryId}`;
    return category.display_name || category.name;
};

export const PreviewMatchesDrawer = ({
    isOpen,
    onOpenChange,
    rows,
    loading,
    error,
    offset,
    limit,
    total,
    categoryById,
    onPageChange,
}: PreviewMatchesDrawerProps) => {
    const start = total === 0 ? 0 : offset + 1;
    const end = Math.min(offset + limit, total);

    return (
        <SlideoutMenu isOpen={isOpen} onOpenChange={onOpenChange}>
            {({ close }) => (
                <>
                    <SlideoutMenu.Header onClose={close}>
                        <div className="flex flex-col gap-1">
                            <h3 className="text-lg font-semibold text-primary">Preview matches</h3>
                            <p className="text-sm text-tertiary">Showing impacted transactions for this draft rule.</p>
                        </div>
                    </SlideoutMenu.Header>
                    <SlideoutMenu.Content>
                        {loading ? <p className="text-sm text-tertiary">Loading preview rows...</p> : null}
                        {error ? (
                            <p className="rounded-md border border-error-secondary bg-error-primary px-3 py-2 text-sm text-error-primary">{error}</p>
                        ) : null}
                        {!loading && rows.length === 0 ? <p className="text-sm text-tertiary">No matches found.</p> : null}
                        {rows.length > 0 ? (
                            <div className="space-y-2">
                                {rows.map((row) => (
                                    <div key={row.transaction_id} className="grid grid-cols-[84px_1fr_120px_1fr] gap-3 rounded-lg border border-secondary px-3 py-2 text-xs">
                                        <span className="text-tertiary">{formatDate(row.posted_at)}</span>
                                        <span className="truncate text-primary">{row.label_raw || "-"}</span>
                                        <span className="text-tertiary">{formatAmount(row.amount, row.currency)}</span>
                                        <span className="truncate text-primary">
                                            {getCategoryLabel(categoryById, row.before.category_id)} {"->"}{" "}
                                            {getCategoryLabel(categoryById, row.after.category_id)}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        ) : null}
                    </SlideoutMenu.Content>
                    <SlideoutMenu.Footer className="flex items-center justify-between gap-3">
                        <span className="text-xs text-tertiary">
                            {start}-{end} of {total}
                        </span>
                        <div className="flex items-center gap-2">
                            <Button
                                color="secondary"
                                size="sm"
                                isDisabled={offset === 0 || loading}
                                onClick={() => onPageChange(Math.max(0, offset - limit))}
                            >
                                Previous
                            </Button>
                            <Button
                                color="secondary"
                                size="sm"
                                isDisabled={offset + limit >= total || loading}
                                onClick={() => onPageChange(offset + limit)}
                            >
                                Next
                            </Button>
                        </div>
                    </SlideoutMenu.Footer>
                </>
            )}
        </SlideoutMenu>
    );
};

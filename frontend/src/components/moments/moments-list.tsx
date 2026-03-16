import { Calendar } from "@untitledui/icons";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import type { Moment } from "@/services/moments";
import { formatAmount, formatDate } from "@/utils/format";

interface MomentsListProps {
    moments: Moment[];
    loading: boolean;
    error: string | null;
    onRetry: () => void;
    onCreateMoment: () => void;
    onOpenMoment: (momentId: number) => void;
}

const formatMomentRange = (moment: Moment) => {
    const hasStart = Boolean(moment.start_date);
    const hasEnd = Boolean(moment.end_date);
    if (!hasStart && !hasEnd) return "No date range";
    if (hasStart && hasEnd) return `${formatDate(moment.start_date)} - ${formatDate(moment.end_date)}`;
    if (hasStart) return `From ${formatDate(moment.start_date)}`;
    return `Until ${formatDate(moment.end_date)}`;
};

export const MomentsList = ({ moments, loading, error, onRetry, onCreateMoment, onOpenMoment }: MomentsListProps) => {
    return (
        <div className="rounded-2xl border border-secondary bg-primary p-5">
            <div className="mb-4">
                <div>
                    <h2 className="text-lg font-semibold text-primary">Moments Workspace</h2>
                    <p className="text-sm text-tertiary">Create or open a moment to review tagged and candidate transactions.</p>
                </div>
            </div>

            {loading ? (
                <div className="flex justify-center py-12">
                    <LoadingIndicator label="Loading moments..." />
                </div>
            ) : error ? (
                <div className="rounded-lg border border-error-secondary bg-error-primary p-4 text-sm text-error-primary">
                    <p>{error}</p>
                    <div className="mt-3">
                        <Button color="secondary" size="sm" onClick={onRetry}>
                            Retry
                        </Button>
                    </div>
                </div>
            ) : moments.length === 0 ? (
                <EmptyState>
                    <EmptyState.Header>
                        <EmptyState.FeaturedIcon icon={Calendar} color="brand" />
                    </EmptyState.Header>
                    <EmptyState.Content>
                        <EmptyState.Title>No moments found</EmptyState.Title>
                        <EmptyState.Description>Create your first moment to start reviewing candidate and tagged transactions.</EmptyState.Description>
                    </EmptyState.Content>
                    <EmptyState.Footer>
                        <Button color="primary" size="sm" onClick={onCreateMoment}>
                            Create moment
                        </Button>
                    </EmptyState.Footer>
                </EmptyState>
            ) : (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    {moments.map((moment) => {
                        const hasExpenses = (moment.expenses_total ?? 0) > 0;
                        const hasIncome = (moment.income_total ?? 0) > 0;
                        const hasMetrics = hasExpenses || hasIncome;
                        const splitsCount = moment.tagged_splits_count ?? 0;

                        return (
                            <button
                                key={moment.id}
                                type="button"
                                className="overflow-hidden rounded-xl border border-secondary bg-primary text-left transition hover:bg-secondary"
                                onClick={() => onOpenMoment(moment.id)}
                            >
                                {moment.cover_image_url ? (
                                    <div className="relative h-24 w-full">
                                        <img src={moment.cover_image_url} alt="" className="h-full w-full object-cover" />
                                        <div className="absolute inset-0 bg-linear-to-b from-transparent to-black/40" />
                                    </div>
                                ) : null}
                                <div className="p-4">
                                <div className="mb-2 flex items-start justify-between gap-2">
                                    <p className="line-clamp-1 text-sm font-semibold text-primary">{moment.name}</p>
                                    <Badge color="brand" size="sm">
                                        #{moment.id}
                                    </Badge>
                                </div>
                                <p className="text-xs text-tertiary">{formatMomentRange(moment)}</p>

                                {hasMetrics ? (
                                    <div className="mt-3 flex items-baseline gap-3">
                                        {hasExpenses ? (
                                            <span className="text-sm font-medium text-error-primary">
                                                {formatAmount(moment.expenses_total)}
                                            </span>
                                        ) : null}
                                        {hasIncome ? (
                                            <span className="text-sm font-medium text-success-primary">
                                                +{formatAmount(moment.income_total)}
                                            </span>
                                        ) : null}
                                        <span className="text-xs text-quaternary">
                                            {splitsCount} split{splitsCount !== 1 ? "s" : ""}
                                        </span>
                                    </div>
                                ) : (
                                    <p className="mt-2 text-xs text-quaternary">
                                        {splitsCount > 0
                                            ? `${splitsCount} split${splitsCount !== 1 ? "s" : ""} tagged`
                                            : "No tagged splits yet"}
                                    </p>
                                )}

                                {moment.description ? (
                                    <p className="mt-2 line-clamp-2 text-xs text-tertiary">{moment.description}</p>
                                ) : null}
                                </div>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

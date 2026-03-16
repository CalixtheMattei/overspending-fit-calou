import type { ReactNode } from "react";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Tabs } from "@/components/application/tabs/tabs";
import { Button } from "@/components/base/buttons/button";
import { getCategoryDisplayLabel } from "@/components/ledger/categories/category-visuals";
import type { Moment } from "@/services/moments";
import { formatAmount, formatDate, formatPercent } from "@/utils/format";

export type MomentOverlayTab = "tagged" | "candidates";

const OVERLAY_TABS = [
    { id: "tagged", label: "Tagged" },
    { id: "candidates", label: "Candidates" },
] as const;

interface MomentOverlayProps {
    isOpen: boolean;
    moment: Moment | null;
    activeTab: MomentOverlayTab;
    taggedCount: number;
    candidatesCount: number;
    onOpenChange: (open: boolean) => void;
    onTabChange: (tab: MomentOverlayTab) => void;
    onEditMoment?: () => void;
    onAddCoverImage?: () => void;
    onRemoveCoverImage?: () => void;
    onDeleteMoment?: () => void;
    coverImageSaving?: boolean;
    coverImageError?: string | null;
    taggedPanel: ReactNode;
    candidatesPanel: ReactNode;
}

const formatMomentRange = (moment: Moment | null) => {
    if (!moment) return "-";
    if (moment.start_date && moment.end_date) return `${formatDate(moment.start_date)} - ${formatDate(moment.end_date)}`;
    if (moment.start_date) return `From ${formatDate(moment.start_date)}`;
    if (moment.end_date) return `Until ${formatDate(moment.end_date)}`;
    return "No date range";
};

const formatTopCategoryLabel = (name: string): string => {
    const trimmed = name.trim();
    if (!trimmed) return "-";
    return getCategoryDisplayLabel({ name: trimmed });
};

export const MomentOverlay = ({
    isOpen,
    moment,
    activeTab,
    taggedCount,
    candidatesCount,
    onOpenChange,
    onTabChange,
    onEditMoment,
    onAddCoverImage,
    onRemoveCoverImage,
    onDeleteMoment,
    coverImageSaving = false,
    coverImageError = null,
    taggedPanel,
    candidatesPanel,
}: MomentOverlayProps) => {
    const hasCoverImage = Boolean(moment?.cover_image_url);

    return (
        <ModalOverlay isOpen={isOpen} onOpenChange={onOpenChange}>
            <Modal>
                <Dialog className="max-w-[min(1200px,96vw)] rounded-2xl bg-primary p-0 shadow-xl ring-1 ring-secondary">
                    <div className="flex max-h-[min(92vh,960px)] w-full flex-col">
                        <div className="relative overflow-hidden border-b border-secondary">
                            {hasCoverImage && moment?.cover_image_url ? (
                                <>
                                    <img src={moment.cover_image_url} alt="" className="absolute inset-0 h-full w-full object-cover" />
                                    <div className="absolute inset-0 bg-linear-to-b from-black/10 via-black/35 to-black/70" />
                                </>
                            ) : null}

                            <div className={`relative z-10 px-6 py-5 ${hasCoverImage ? "min-h-56" : ""}`}>
                                <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0 space-y-1">
                                        <h2 className={`truncate text-lg font-semibold ${hasCoverImage ? "text-white" : "text-primary"}`}>
                                            {moment?.name || "Moment"}
                                        </h2>
                                        <p className={`text-sm ${hasCoverImage ? "text-white/85" : "text-tertiary"}`}>{formatMomentRange(moment)}</p>
                                        {moment?.description ? (
                                            <p className={`line-clamp-2 text-xs ${hasCoverImage ? "text-white/80" : "text-tertiary"}`}>{moment.description}</p>
                                        ) : null}
                                    </div>
                                    <div className="flex flex-wrap items-center justify-end gap-1.5">
                                        {onAddCoverImage ? (
                                            <Button color="secondary" size="sm" onClick={onAddCoverImage} isLoading={coverImageSaving} isDisabled={coverImageSaving}>
                                                {hasCoverImage ? "Change cover" : "Add cover"}
                                            </Button>
                                        ) : null}
                                        {onRemoveCoverImage && hasCoverImage ? (
                                            <Button
                                                color="tertiary-destructive"
                                                size="sm"
                                                onClick={onRemoveCoverImage}
                                                isDisabled={coverImageSaving}
                                            >
                                                Remove cover
                                            </Button>
                                        ) : null}
                                        {onEditMoment ? (
                                            <Button color="secondary" size="sm" onClick={onEditMoment} isDisabled={coverImageSaving}>
                                                Edit
                                            </Button>
                                        ) : null}
                                        {onDeleteMoment ? (
                                            <Button color="secondary-destructive" size="sm" onClick={onDeleteMoment} isDisabled={coverImageSaving}>
                                                Delete
                                            </Button>
                                        ) : null}
                                        <Button color="tertiary" size="sm" onClick={() => onOpenChange(false)} isDisabled={coverImageSaving}>
                                            Close
                                        </Button>
                                    </div>
                                </div>

                                {coverImageError ? (
                                    <div
                                        className={
                                            hasCoverImage
                                                ? "mt-3 rounded-lg border border-red-300/50 bg-red-900/50 p-3 text-sm text-red-100"
                                                : "mt-3 rounded-lg border border-error-secondary bg-error-primary p-3 text-sm text-error-primary"
                                        }
                                    >
                                        {coverImageError}
                                    </div>
                                ) : null}

                                {moment && ((moment.expenses_total ?? 0) > 0 || (moment.income_total ?? 0) > 0) ? (
                                    <div
                                        className={
                                            hasCoverImage
                                                ? "mt-4 rounded-lg border border-white/15 bg-black/35 p-4 backdrop-blur-sm"
                                                : "mt-4 rounded-lg border border-secondary bg-secondary p-4"
                                        }
                                    >
                                        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
                                            <div>
                                                <p className={`text-xs font-medium ${hasCoverImage ? "text-white/80" : "text-tertiary"}`}>Expenses</p>
                                                <p className={`text-lg font-semibold ${hasCoverImage ? "text-white" : "text-error-primary"}`}>
                                                    {formatAmount(moment.expenses_total)}
                                                </p>
                                            </div>
                                            {(moment.income_total ?? 0) > 0 ? (
                                                <div>
                                                    <p className={`text-xs font-medium ${hasCoverImage ? "text-white/80" : "text-tertiary"}`}>Income</p>
                                                    <p className={`text-lg font-semibold ${hasCoverImage ? "text-white" : "text-success-primary"}`}>
                                                        {formatAmount(moment.income_total)}
                                                    </p>
                                                </div>
                                            ) : null}
                                            <div>
                                                <p className={`text-xs font-medium ${hasCoverImage ? "text-white/80" : "text-tertiary"}`}>Tagged splits</p>
                                                <p className={`text-lg font-semibold ${hasCoverImage ? "text-white" : "text-primary"}`}>
                                                    {moment.tagged_splits_count ?? 0}
                                                </p>
                                            </div>
                                        </div>

                                        {moment.top_categories && moment.top_categories.length > 0 ? (
                                            <div className={`mt-3 border-t pt-3 ${hasCoverImage ? "border-white/15" : "border-secondary"}`}>
                                                <p className={`mb-2 text-xs font-medium ${hasCoverImage ? "text-white/80" : "text-tertiary"}`}>
                                                    Top categories by spend
                                                </p>
                                                <div className="flex flex-wrap gap-x-4 gap-y-1">
                                                    {moment.top_categories.map((cat) => (
                                                        <span
                                                            key={cat.category_id}
                                                            className={`text-xs ${cat.is_other ? (hasCoverImage ? "text-white/50" : "text-quaternary") : hasCoverImage ? "text-white/80" : "text-secondary"}`}
                                                        >
                                                            <span className={`font-medium ${cat.is_other ? (hasCoverImage ? "text-white/60" : "text-tertiary") : hasCoverImage ? "text-white" : "text-primary"}`}>
                                                                {cat.is_other ? cat.name : formatTopCategoryLabel(cat.name)}
                                                            </span>{" "}
                                                            {formatAmount(cat.amount)}{" "}
                                                            <span className={hasCoverImage ? "text-white/70" : "text-quaternary"}>
                                                                ({formatPercent(cat.percentage)})
                                                            </span>
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        ) : null}
                                    </div>
                                ) : null}
                            </div>
                        </div>

                        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                            <Tabs selectedKey={activeTab} onSelectionChange={(key) => key && onTabChange(String(key) as MomentOverlayTab)}>
                                <Tabs.List
                                    aria-label="Moment overlay tabs"
                                    size="sm"
                                    type="button-border"
                                    items={OVERLAY_TABS}
                                    className="mb-4 w-fit"
                                >
                                    {(item) => (
                                        <Tabs.Item
                                            id={item.id}
                                            badge={item.id === "tagged" ? String(taggedCount) : String(candidatesCount)}
                                        >
                                            {item.label}
                                        </Tabs.Item>
                                    )}
                                </Tabs.List>
                                <Tabs.Panel id="tagged" className="outline-hidden">
                                    {taggedPanel}
                                </Tabs.Panel>
                                <Tabs.Panel id="candidates" className="outline-hidden">
                                    {candidatesPanel}
                                </Tabs.Panel>
                            </Tabs>
                        </div>
                    </div>
                </Dialog>
            </Modal>
        </ModalOverlay>
    );
};

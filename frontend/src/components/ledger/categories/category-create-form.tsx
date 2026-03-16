import { type FC, useMemo } from "react";
import { Input } from "@/components/base/input/input";
import { Label } from "@/components/base/input/label";
import { Select, type SelectItemType } from "@/components/base/select/select";
import {
    formatCategoryValue,
    getCategoryDisplayLabel,
    resolveCategoryIcon,
    resolveCategoryIconInfo,
} from "@/components/ledger/categories/category-visuals";
import { cx } from "@/utils/cx";
import type { Category } from "@/services/categories";

type CategoryIconComponent = FC<{ className?: string }>;

export type CategoryFormDraft = {
    name: string;
    parentId: string;
    color: string;
    icon: string;
    error: string | null;
    saving: boolean;
};

export const makeEmptyDraft = (defaults?: {
    color?: string;
    icon?: string;
    parentId?: string;
}): CategoryFormDraft => ({
    name: "",
    parentId: defaults?.parentId ?? "none",
    color: defaults?.color ?? "#9CA3AF",
    icon: defaults?.icon ?? "tag",
    error: null,
    saving: false,
});

export const makeDraftFromCategory = (category: Category): CategoryFormDraft => ({
    name: category.name,
    parentId:
        category.parent_id === null || category.parent_id === undefined
            ? "none"
            : String(category.parent_id),
    color: category.color,
    icon: category.icon,
    error: null,
    saving: false,
});

interface CategoryCreateFormProps {
    draft: CategoryFormDraft;
    onChange: (patch: Partial<CategoryFormDraft>) => void;
    /** Root categories to populate parent selector. */
    parentCategories: Category[];
    colors: string[];
    icons: string[];
    /** When true, parent selector is disabled (e.g. subcategory creation from parent context). */
    parentLocked?: boolean;
    /** Category IDs to exclude from parent selector (e.g. the category being edited). */
    excludeParentIds?: number[];
}

export const CategoryCreateForm = ({
    draft,
    onChange,
    parentCategories,
    colors,
    icons,
    parentLocked = false,
    excludeParentIds,
}: CategoryCreateFormProps) => {
    const selectedIcon = resolveCategoryIconInfo(draft.icon).Icon;

    const parentOptions = useMemo<SelectItemType[]>(() => {
        const excludeSet = excludeParentIds ? new Set(excludeParentIds) : null;
        return [
            { id: "none", label: "No parent" },
            ...parentCategories
                .filter((c) => (excludeSet ? !excludeSet.has(c.id) : true))
                .map((c) => ({
                    id: String(c.id),
                    label: getCategoryDisplayLabel(c),
                })),
        ];
    }, [parentCategories, excludeParentIds]);

    const dedupedIcons = useMemo(() => {
        const seen = new Set<CategoryIconComponent>();
        return icons.filter((key) => {
            const { Icon } = resolveCategoryIconInfo(key);
            if (seen.has(Icon)) return false;
            seen.add(Icon);
            return true;
        });
    }, [icons]);

    return (
        <>
            <Input
                label="Name"
                placeholder="Groceries"
                value={draft.name}
                onChange={(value) => onChange({ name: value })}
            />
            <Select
                label="Parent"
                items={parentOptions}
                selectedKey={draft.parentId}
                isDisabled={parentLocked}
                onSelectionChange={(key) => key && onChange({ parentId: String(key) })}
            >
                {(item) => <Select.Item id={item.id} label={item.label} />}
            </Select>
            <div>
                <Label>Color</Label>
                <div className="mt-1.5 flex flex-wrap gap-2">
                    {colors.map((hex) => {
                        const selected = draft.color.toLowerCase() === hex.toLowerCase();
                        return (
                            <button
                                key={hex}
                                type="button"
                                className={cx(
                                    "size-8 rounded-full transition-transform hover:scale-110",
                                    hex.toUpperCase() === "#FFFFFF" && "ring-1 ring-secondary",
                                    selected && "ring-2 ring-brand-primary ring-offset-2 ring-offset-primary",
                                )}
                                style={{ backgroundColor: hex }}
                                onClick={() => onChange({ color: hex })}
                                aria-label={`Select color ${hex}`}
                                title={hex}
                            />
                        );
                    })}
                </div>
            </div>
            <div>
                <Label>Icon</Label>
                <div className="mt-1.5 grid max-h-48 grid-cols-8 gap-2 overflow-y-auto">
                    {dedupedIcons.map((iconKey) => {
                        const Icon = resolveCategoryIcon(iconKey);
                        const selected = selectedIcon === Icon;
                        return (
                            <button
                                key={iconKey}
                                type="button"
                                title={formatCategoryValue(iconKey)}
                                className={cx(
                                    "flex size-9 items-center justify-center rounded-lg transition-colors",
                                    selected
                                        ? "bg-brand-secondary ring-2 ring-brand-primary"
                                        : "bg-secondary hover:bg-tertiary",
                                )}
                                onClick={() => onChange({ icon: iconKey })}
                                aria-label={`Select icon ${formatCategoryValue(iconKey) || iconKey}`}
                            >
                                <Icon className="size-5" />
                            </button>
                        );
                    })}
                </div>
            </div>
        </>
    );
};

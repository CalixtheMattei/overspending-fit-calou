import { useEffect, useState } from "react";
import type { Category } from "@/services/categories";
import { CategoryTreePicker } from "@/components/ledger/categories/category-tree-picker";

type OverwriteMode = "non_destructive" | "destructive";

interface ActionBuilderProps {
    categories: Category[];
    categoryId: string;
    onCategoryIdChange: (value: string) => void;
    overwriteMode: OverwriteMode;
    onOverwriteModeChange: (value: OverwriteMode) => void;
}

export const ActionBuilder = ({
    categories,
    categoryId,
    onCategoryIdChange,
    overwriteMode,
    onOverwriteModeChange,
}: ActionBuilderProps) => {
    const [showAdvanced, setShowAdvanced] = useState(false);
    useEffect(() => {
        if (overwriteMode === "destructive") {
            setShowAdvanced(true);
        }
    }, [overwriteMode]);

    return (
        <section className="space-y-4 rounded-xl border border-secondary bg-primary p-4">
            <div className="space-y-1">
                <h3 className="text-sm font-semibold text-primary">Then do this...</h3>
                <p className="text-xs text-tertiary">Rules fill missing categories first. Existing categorization stays untouched by default.</p>
            </div>

            <CategoryTreePicker
                categories={categories}
                selectedCategoryId={categoryId ? Number(categoryId) : null}
                onSelect={(id) => onCategoryIdChange(String(id))}
                aria-label="Set rule category"
                placeholder="Set category"
            />

            <fieldset className="space-y-2">
                <legend className="text-xs font-medium text-secondary">Categorization policy</legend>
                <label className="flex items-start gap-2 text-sm text-primary">
                    <input
                        type="radio"
                        name="overwrite_mode"
                        checked={overwriteMode === "non_destructive"}
                        onChange={() => onOverwriteModeChange("non_destructive")}
                    />
                    <span>Only apply to uncategorized transactions (default)</span>
                </label>

                <button
                    type="button"
                    className="text-xs font-medium text-brand-secondary hover:text-brand-secondary_hover"
                    onClick={() => setShowAdvanced((prev) => !prev)}
                >
                    {showAdvanced ? "Hide advanced overwrite option" : "Show advanced overwrite option"}
                </button>

                {showAdvanced ? (
                    <div className="space-y-2 rounded-lg border border-warning-secondary bg-warning-primary px-3 py-2">
                        <label className="flex items-start gap-2 text-sm text-warning-primary">
                            <input
                                type="radio"
                                name="overwrite_mode"
                                checked={overwriteMode === "destructive"}
                                onChange={() => onOverwriteModeChange("destructive")}
                            />
                            <span>Allow overwrite of existing categorization</span>
                        </label>
                        <p className="text-xs text-warning-primary">
                            Use overwrite only when you intentionally want this rule to replace manual or prior rule categorization.
                        </p>
                    </div>
                ) : null}
            </fieldset>
        </section>
    );
};

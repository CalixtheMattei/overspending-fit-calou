import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, Edit01, Plus, Trash01 } from "@untitledui/icons";
import { useSearchParams } from "react-router";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Button } from "@/components/base/buttons/button";
import { ButtonUtility } from "@/components/base/buttons/button-utility";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { Input } from "@/components/base/input/input";
import { getCategoryDisplayLabel, resolveCategoryIcon } from "@/components/ledger/categories/category-visuals";
import {
    CategoryCreateForm,
    makeEmptyDraft,
    makeDraftFromCategory,
    type CategoryFormDraft,
} from "@/components/ledger/categories/category-create-form";
import {
    createCategory,
    deleteCategory,
    fetchCategoryPresets,
    fetchDeletePreview,
    updateCategory,
    type Category,
    type CategoryPresets,
    type DeletePreview,
    type DeleteStrategy,
} from "@/services/categories";
import { CategoryTreePicker } from "@/components/ledger/categories/category-tree-picker";
import { cx } from "@/utils/cx";

type DeleteState = {
    category: Category | null;
    preview: DeletePreview | null;
    loading: boolean;
    error: string | null;
    splitAction: "uncategorize" | "reassign";
    reassignCategoryId: number | null;
    childAction: "promote" | "reparent";
    reparentCategoryId: number | null;
};

type AccordionCard = {
    parent: Category;
    children: Category[];
    visibleChildren: Category[];
    autoExpand: boolean;
    orphan: boolean;
};

const FALLBACK_PRESETS: CategoryPresets = {
    colors: ["#9CA3AF"],
    icons: ["tag"],
    default_color: "#9CA3AF",
    default_icon: "tag",
    categories: [],
    tree: [],
};

const EMPTY_DELETE: DeleteState = {
    category: null,
    preview: null,
    loading: false,
    error: null,
    splitAction: "uncategorize",
    reassignCategoryId: null,
    childAction: "promote",
    reparentCategoryId: null,
};
const sortByName = (a: Category, b: Category) =>
    getCategoryDisplayLabel(a).localeCompare(getCategoryDisplayLabel(b));
const normalizeCategoryName = (name: string) =>
    name
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();
const isUnknownRootCategory = (category: Category) =>
    category.parent_id === null && normalizeCategoryName(category.name) === "unknown";

/**
 * Pick a text color (white or black) for sufficient contrast against the given
 * background color. Uses the W3C relative luminance formula.
 */
const contrastText = (hex: string): string => {
    const raw = hex.replace("#", "");
    const r = parseInt(raw.substring(0, 2), 16) / 255;
    const g = parseInt(raw.substring(2, 4), 16) / 255;
    const b = parseInt(raw.substring(4, 6), 16) / 255;
    const luminance =
        0.2126 * (r <= 0.03928 ? r / 12.92 : ((r + 0.055) / 1.055) ** 2.4) +
        0.7152 * (g <= 0.03928 ? g / 12.92 : ((g + 0.055) / 1.055) ** 2.4) +
        0.0722 * (b <= 0.03928 ? b / 12.92 : ((b + 0.055) / 1.055) ** 2.4);
    return luminance > 0.4 ? "#1B1B1B" : "#FFFFFF";
};

export const CategoriesPage = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const [categories, setCategories] = useState<Category[]>([]);
    const [presets, setPresets] = useState<CategoryPresets>(FALLBACK_PRESETS);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState("");
    const [createOpen, setCreateOpen] = useState(false);
    const [createDraft, setCreateDraft] = useState<CategoryFormDraft>(
        makeEmptyDraft({ color: FALLBACK_PRESETS.default_color, icon: FALLBACK_PRESETS.default_icon }),
    );
    const [createParentLocked, setCreateParentLocked] = useState(false);
    const [editTarget, setEditTarget] = useState<Category | null>(null);
    const [editDraft, setEditDraft] = useState<CategoryFormDraft>(
        makeEmptyDraft({ color: FALLBACK_PRESETS.default_color, icon: FALLBACK_PRESETS.default_icon }),
    );
    const [expanded, setExpanded] = useState<Set<number>>(new Set());
    const [deleteState, setDeleteState] = useState<DeleteState>(EMPTY_DELETE);

    useEffect(() => {
        let active = true;
        const load = async () => {
            setLoading(true);
            setError(null);
            try {
                const presetData = await fetchCategoryPresets();
                if (!active) return;
                setCategories(presetData.categories);
                setPresets(presetData);
                setCreateDraft((prev) => ({ ...prev, color: presetData.default_color, icon: presetData.default_icon }));
            } catch (loadError) {
                if (!active) return;
                setError(loadError instanceof Error ? loadError.message : "Failed to load categories.");
            } finally {
                if (active) setLoading(false);
            }
        };
        load();
        return () => {
            active = false;
        };
    }, []);

    const categoriesById = useMemo(
        () => new Map(categories.map((c) => [c.id, c])),
        [categories],
    );
    const roots = useMemo(
        () => categories.filter((c) => c.parent_id === null).sort(sortByName),
        [categories],
    );
    const allowedParentRoots = useMemo(
        () => roots.filter((c) => !isUnknownRootCategory(c)),
        [roots],
    );

    /* ------------------------------------------------------------------ */
    /*  Search helpers                                                     */
    /* ------------------------------------------------------------------ */

    const normalizedSearch = searchQuery.trim().toLowerCase();
    const hasSearch = normalizedSearch.length > 0;
    const matchesSearch = (category: Category) => {
        if (!hasSearch) return true;
        const raw = category.name.toLowerCase();
        const formatted = getCategoryDisplayLabel(category).toLowerCase();
        return raw.includes(normalizedSearch) || formatted.includes(normalizedSearch);
    };

    /* ------------------------------------------------------------------ */
    /*  Build unified accordion cards (merged personalized + library)     */
    /* ------------------------------------------------------------------ */

    const allCards = useMemo(() => {
        const childrenByParent = new Map<number, Category[]>();
        const rootSet = new Set(categories.filter((c) => c.parent_id === null).map((c) => c.id));

        for (const category of categories) {
            if (category.parent_id === null || !rootSet.has(category.parent_id)) continue;
            const rows = childrenByParent.get(category.parent_id) ?? [];
            rows.push(category);
            childrenByParent.set(category.parent_id, rows);
        }
        childrenByParent.forEach((rows) => rows.sort(sortByName));

        // Include orphan roots as well
        const parentCandidates = categories.filter(
            (c) => c.parent_id === null || !rootSet.has(c.parent_id),
        );

        return parentCandidates
            .sort(sortByName)
            .map((parent) => {
                const children = childrenByParent.get(parent.id) ?? [];
                const parentMatches = matchesSearch(parent);
                const childMatches = hasSearch ? children.filter(matchesSearch) : children;
                return {
                    parent,
                    children,
                    visibleChildren: !hasSearch || parentMatches ? children : childMatches,
                    autoExpand: hasSearch && !parentMatches && childMatches.length > 0,
                    orphan: parent.parent_id !== null && !rootSet.has(parent.parent_id),
                } satisfies AccordionCard;
            })
            .filter((card) => !hasSearch || matchesSearch(card.parent) || card.visibleChildren.length > 0);
    }, [categories, normalizedSearch]);

    /* ------------------------------------------------------------------ */
    /*  Modal open / close helpers                                         */
    /* ------------------------------------------------------------------ */

    const openCreateModal = useCallback(
        (parentId?: number) => {
            const targetParent =
                parentId !== undefined ? categoriesById.get(parentId) ?? null : null;
            const safeParentId =
                targetParent && !isUnknownRootCategory(targetParent)
                    ? String(targetParent.id)
                    : undefined;
            const draft = makeEmptyDraft({
                color: presets.default_color,
                icon: presets.default_icon,
                parentId: safeParentId,
            });
            setCreateDraft(draft);
            setCreateParentLocked(safeParentId !== undefined);
            setCreateOpen(true);
        },
        [categoriesById, presets.default_color, presets.default_icon],
    );

    const closeCreate = () => {
        setCreateOpen(false);
        setCreateDraft(makeEmptyDraft({ color: presets.default_color, icon: presets.default_icon }));
        setCreateParentLocked(false);
    };

    const closeEdit = () => {
        setEditTarget(null);
        setEditDraft(makeEmptyDraft({ color: presets.default_color, icon: presets.default_icon }));
    };

    useEffect(() => {
        if (searchParams.get("create") !== "1") {
            return;
        }
        const parentIdParam = Number(searchParams.get("parent_id"));
        const parentId =
            Number.isFinite(parentIdParam) && parentIdParam > 0 ? parentIdParam : undefined;
        openCreateModal(parentId);
        const nextParams = new URLSearchParams(searchParams);
        nextParams.delete("create");
        nextParams.delete("parent_id");
        setSearchParams(nextParams, { replace: true });
    }, [openCreateModal, searchParams, setSearchParams]);

    const toggleExpanded = (id: number) => {
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    /* ------------------------------------------------------------------ */
    /*  CRUD handlers                                                      */
    /* ------------------------------------------------------------------ */

    const createCategoryFromModal = async () => {
        const name = createDraft.name.trim();
        if (!name) return setCreateDraft((prev) => ({ ...prev, error: "Name is required." }));
        const parentId = createDraft.parentId === "none" ? null : Number(createDraft.parentId);
        if (parentId !== null) {
            const parent = categoriesById.get(parentId);
            if (parent && isUnknownRootCategory(parent)) {
                return setCreateDraft((prev) => ({
                    ...prev,
                    saving: false,
                    error: "Unknown category cannot have subcategories.",
                }));
            }
        }
        setCreateDraft((prev) => ({ ...prev, error: null, saving: true }));
        try {
            const created = await createCategory({
                name,
                parent_id: parentId,
                color: createDraft.color,
                icon: createDraft.icon,
            });
            setCategories((prev) => [...prev, created]);
            closeCreate();
        } catch (createError) {
            setCreateDraft((prev) => ({
                ...prev,
                saving: false,
                error: createError instanceof Error ? createError.message : "Failed to create category.",
            }));
        }
    };

    const updateCategoryFromModal = async () => {
        if (!editTarget || !editTarget.is_custom) return;
        const name = editDraft.name.trim();
        if (!name) return setEditDraft((prev) => ({ ...prev, error: "Name is required." }));
        const parentId = editDraft.parentId === "none" ? null : Number(editDraft.parentId);
        if (parentId !== null) {
            const parent = categoriesById.get(parentId);
            if (parent && isUnknownRootCategory(parent)) {
                return setEditDraft((prev) => ({
                    ...prev,
                    saving: false,
                    error: "Unknown category cannot have subcategories.",
                }));
            }
        }
        setEditDraft((prev) => ({ ...prev, error: null, saving: true }));
        try {
            const updated = await updateCategory(editTarget.id, {
                name,
                parent_id: parentId,
                color: editDraft.color,
                icon: editDraft.icon,
            });
            setCategories((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
            closeEdit();
        } catch (updateError) {
            setEditDraft((prev) => ({
                ...prev,
                saving: false,
                error: updateError instanceof Error ? updateError.message : "Failed to update category.",
            }));
        }
    };

    const openDeleteModal = async (category: Category) => {
        if (!category.is_custom) return;
        setDeleteState({ ...EMPTY_DELETE, category, loading: true });
        try {
            const preview = await fetchDeletePreview(category.id);
            setDeleteState((prev) => ({ ...prev, preview, loading: false }));
        } catch (deleteError) {
            setDeleteState((prev) => ({
                ...prev,
                loading: false,
                error: deleteError instanceof Error ? deleteError.message : "Failed to load category usage.",
            }));
        }
    };

    const confirmDeleteCategory = async () => {
        if (!deleteState.category || deleteState.loading) return;
        const hasImpact =
            (deleteState.preview?.direct_split_count ?? 0) > 0 ||
            (deleteState.preview?.child_count ?? 0) > 0;
        try {
            const deletedId = deleteState.category.id;
            const strategy: DeleteStrategy | undefined = hasImpact
                ? {
                      split_action: deleteState.splitAction,
                      reassign_category_id:
                          deleteState.splitAction === "reassign" ? deleteState.reassignCategoryId : null,
                      child_action: deleteState.childAction,
                      reparent_category_id:
                          deleteState.childAction === "reparent" ? deleteState.reparentCategoryId : null,
                  }
                : undefined;
            await deleteCategory(deletedId, strategy);
            setCategories((prev) =>
                prev
                    .filter((c) => c.id !== deletedId)
                    .map((c) => (c.parent_id === deletedId ? { ...c, parent_id: null } : c)),
            );
            setExpanded((prev) => {
                const next = new Set(prev);
                next.delete(deletedId);
                return next;
            });
            if (editTarget?.id === deletedId) closeEdit();
            setDeleteState(EMPTY_DELETE);
        } catch (deleteError) {
            setDeleteState((prev) => ({
                ...prev,
                error: deleteError instanceof Error ? deleteError.message : "Failed to delete category.",
            }));
        }
    };

    /* ------------------------------------------------------------------ */
    /*  Render helpers                                                     */
    /* ------------------------------------------------------------------ */

    /** Contextual action buttons per category row. */
    const categoryActions = (category: Category, isParent: boolean) => (
        <div className="flex items-center gap-1">
            {/* A3-1: "Add subcategory" action on parent rows */}
            {isParent && !isUnknownRootCategory(category) && (
                <ButtonUtility
                    icon={Plus}
                    tooltip="Add subcategory"
                    onClick={() => openCreateModal(category.id)}
                />
            )}
            {category.is_custom && (
                <>
                    <ButtonUtility
                        icon={Edit01}
                        tooltip="Edit category"
                        onClick={() => {
                            setEditTarget(category);
                            setEditDraft(makeDraftFromCategory(category));
                        }}
                    />
                    <ButtonUtility
                        icon={Trash01}
                        tooltip="Delete category"
                        onClick={() => openDeleteModal(category)}
                    />
                </>
            )}
        </div>
    );

    /** Render a single accordion card (parent colored row + children). */
    const renderCard = (card: AccordionCard) => {
        const ParentIcon = resolveCategoryIcon(card.parent.icon);
        const open = card.children.length > 0 && (card.autoExpand || expanded.has(card.parent.id));
        const linkedParent =
            card.orphan && card.parent.parent_id !== null
                ? categoriesById.get(card.parent.parent_id)
                : null;
        const parentColor = card.parent.color || "#9CA3AF";
        const textColor = contrastText(parentColor);

        return (
            <article
                key={card.parent.id}
                className="overflow-hidden rounded-xl shadow-xs ring-1 ring-secondary"
            >
                {/* Parent: colored row */}
                <div
                    className="flex items-center gap-3 px-4 py-3"
                    style={{ backgroundColor: parentColor }}
                >
                    <button
                        type="button"
                        className={cx(
                            "flex flex-1 items-center gap-3 text-left",
                            card.children.length > 0 ? "cursor-pointer" : "cursor-default",
                        )}
                        onClick={() => card.children.length > 0 && toggleExpanded(card.parent.id)}
                        aria-expanded={card.children.length > 0 ? open : undefined}
                    >
                        <span
                            className="inline-flex size-8 items-center justify-center rounded-lg"
                            style={{ backgroundColor: "rgba(255,255,255,0.2)" }}
                        >
                            <span style={{ color: textColor }}><ParentIcon className="size-4" /></span>
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-2">
                                <span
                                    className="truncate text-sm font-semibold"
                                    style={{ color: textColor }}
                                >
                                    {getCategoryDisplayLabel(card.parent)}
                                </span>
                                {card.children.length > 0 && (
                                    <span
                                        className="text-xs"
                                        style={{ color: textColor, opacity: 0.75 }}
                                    >
                                        {card.children.length} sub
                                    </span>
                                )}
                            </span>
                            {linkedParent && (
                                <span
                                    className="mt-0.5 block text-xs"
                                    style={{ color: textColor, opacity: 0.7 }}
                                >
                                    Part of {getCategoryDisplayLabel(linkedParent)}
                                </span>
                            )}
                        </span>
                        {card.children.length > 0 && (
                            <ChevronDown
                                className={cx(
                                    "size-4 shrink-0 transition-transform",
                                    open && "rotate-180",
                                )}
                                style={{ color: textColor }}
                            />
                        )}
                    </button>
                    {/* Actions overlaid on colored row with pill bg for visibility */}
                    <div
                        className="flex items-center gap-1 rounded-lg px-1 py-0.5"
                        style={{ backgroundColor: "rgba(255,255,255,0.25)" }}
                    >
                        {categoryActions(card.parent, true)}
                    </div>
                </div>

                {/* Children rows */}
                {open && (
                    <div className="flex flex-col gap-px bg-secondary">
                        {card.visibleChildren.map((child) => {
                            const ChildIcon = resolveCategoryIcon(child.icon);
                            return (
                                <div
                                    key={child.id}
                                    className="flex items-center justify-between gap-2 bg-primary px-5 py-2.5"
                                >
                                    <div className="min-w-0 flex items-center gap-2">
                                        <span
                                            className="size-2.5 shrink-0 rounded-full ring-1 ring-secondary"
                                            style={{ backgroundColor: child.color }}
                                        />
                                        <ChildIcon className="size-4 shrink-0 text-fg-quaternary" />
                                        <span className="truncate text-sm text-secondary">
                                            {getCategoryDisplayLabel(child)}
                                        </span>
                                    </div>
                                    {categoryActions(child, false)}
                                </div>
                            );
                        })}
                        {!isUnknownRootCategory(card.parent) && (
                            <button
                                type="button"
                                className="flex items-center gap-2 bg-primary px-5 py-2.5 text-left text-sm font-medium text-brand-primary transition-colors hover:bg-primary_hover"
                                onClick={() => openCreateModal(card.parent.id)}
                            >
                                <Plus className="size-4" />
                                Create category
                            </button>
                        )}
                    </div>
                )}
            </article>
        );
    };

    return (
        <section className="flex flex-1 flex-col gap-6">
            <header className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="flex flex-col gap-2">
                    <h1 className="text-2xl font-semibold text-primary">Categories</h1>
                    <p className="text-sm text-tertiary">
                        Browse category hierarchy, create new categories, and manage your custom ones.
                    </p>
                </div>
                <DemoGuard>
                    <Button
                        color="primary"
                        iconLeading={Plus}
                        onClick={() => openCreateModal()}
                    >
                        Create category
                    </Button>
                </DemoGuard>
            </header>

            <div className="rounded-2xl bg-primary shadow-xs ring-1 ring-secondary">
                <div className="border-b border-secondary px-4 py-4 md:px-6">
                    <Input
                        aria-label="Search categories"
                        placeholder="Search categories"
                        value={searchQuery}
                        onChange={(value) => setSearchQuery(value)}
                        className="w-full md:max-w-xs"
                    />
                </div>
                <div className="flex flex-col gap-3 px-4 py-4 md:px-6 md:py-6">
                    {loading ? (
                        <div className="flex justify-center py-10">
                            <LoadingIndicator label="Loading categories..." />
                        </div>
                    ) : error ? (
                        <div className="rounded-2xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                            {error}
                        </div>
                    ) : allCards.length === 0 ? (
                        <div className="rounded-lg border border-dashed border-secondary p-4 text-sm text-tertiary">
                            {hasSearch
                                ? "No categories match this search."
                                : "No categories available."}
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 gap-3">{allCards.map(renderCard)}</div>
                    )}
                </div>
            </div>

            {/* ---- Create modal (uses shared CategoryCreateForm) ---- */}
            <ModalOverlay isOpen={createOpen} onOpenChange={(open) => !open && closeCreate()}>
                <Modal className="flex items-center justify-center">
                    <Dialog className="max-w-lg rounded-2xl bg-primary p-8 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-6">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">
                                    {createParentLocked ? "Create subcategory" : "Create category"}
                                </h4>
                                <p className="text-sm text-tertiary">
                                    {createParentLocked
                                        ? "Add a subcategory under the selected parent."
                                        : "Add a custom category with optional parent, color, and icon."}
                                </p>
                            </div>
                            <CategoryCreateForm
                                draft={createDraft}
                                onChange={(patch) => setCreateDraft((prev) => ({ ...prev, ...patch }))}
                                parentCategories={allowedParentRoots}
                                colors={presets.colors}
                                icons={presets.icons}
                                parentLocked={createParentLocked}
                            />
                            {createDraft.error && (
                                <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                    {createDraft.error}
                                </div>
                            )}
                            <div className="border-t border-secondary" />
                            <div className="flex justify-end gap-2">
                                <Button color="tertiary" isDisabled={createDraft.saving} onClick={closeCreate}>
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button
                                        color="primary"
                                        isDisabled={createDraft.saving}
                                        onClick={createCategoryFromModal}
                                    >
                                        {createDraft.saving ? "Creating..." : "Create"}
                                    </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            {/* ---- Edit modal (uses shared CategoryCreateForm) ---- */}
            <ModalOverlay isOpen={!!editTarget} onOpenChange={(open) => !open && closeEdit()}>
                <Modal>
                    <Dialog className="max-w-lg rounded-2xl bg-primary p-8 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-6">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Edit category</h4>
                                <p className="text-sm text-tertiary">Update your custom category details.</p>
                            </div>
                            <CategoryCreateForm
                                draft={editDraft}
                                onChange={(patch) => setEditDraft((prev) => ({ ...prev, ...patch }))}
                                parentCategories={allowedParentRoots}
                                colors={presets.colors}
                                icons={presets.icons}
                                excludeParentIds={editTarget ? [editTarget.id] : undefined}
                            />
                            {editDraft.error && (
                                <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                    {editDraft.error}
                                </div>
                            )}
                            <div className="border-t border-secondary" />
                            <div className="flex justify-end gap-2">
                                <Button color="tertiary" isDisabled={editDraft.saving} onClick={closeEdit}>
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button
                                        color="primary"
                                        isDisabled={editDraft.saving}
                                        onClick={updateCategoryFromModal}
                                    >
                                        {editDraft.saving ? "Saving..." : "Update"}
                                    </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            {/* ---- Delete modal (impact-aware strategy) ---- */}
            <ModalOverlay
                isOpen={!!deleteState.category}
                onOpenChange={(open) => !open && setDeleteState(EMPTY_DELETE)}
            >
                <Modal>
                    <Dialog className="max-w-lg rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        {(() => {
                            const preview = deleteState.preview;
                            const hasImpact =
                                (preview?.direct_split_count ?? 0) > 0 || (preview?.child_count ?? 0) > 0;
                            const deleteDisabled =
                                deleteState.loading ||
                                !deleteState.category ||
                                (hasImpact &&
                                    deleteState.splitAction === "reassign" &&
                                    !deleteState.reassignCategoryId) ||
                                (hasImpact &&
                                    deleteState.childAction === "reparent" &&
                                    !deleteState.reparentCategoryId);

                            return (
                                <div className="flex flex-col gap-4">
                                    <div>
                                        <h4 className="text-lg font-semibold text-primary">Delete category</h4>
                                        {deleteState.loading ? (
                                            <p className="text-sm text-tertiary">Checking impact...</p>
                                        ) : !hasImpact ? (
                                            <p className="text-sm text-tertiary">
                                                This category has no usage and no subcategories. It can be deleted
                                                immediately.
                                            </p>
                                        ) : (
                                            <p className="text-sm text-tertiary">
                                                {preview!.direct_split_count > 0 &&
                                                    `${preview!.direct_split_count} split${preview!.direct_split_count !== 1 ? "s" : ""} use this category. `}
                                                {preview!.child_count > 0 &&
                                                    `${preview!.child_count} subcategor${preview!.child_count !== 1 ? "ies" : "y"} belong to it.`}
                                            </p>
                                        )}
                                    </div>

                                    {/* Split handling strategy */}
                                    {!deleteState.loading && hasImpact && (preview?.direct_split_count ?? 0) > 0 && (
                                        <fieldset className="flex flex-col gap-2">
                                            <legend className="text-sm font-medium text-primary">
                                                What should happen to categorized splits?
                                            </legend>
                                            <label className="flex items-center gap-2 text-sm text-secondary">
                                                <input
                                                    type="radio"
                                                    name="splitAction"
                                                    checked={deleteState.splitAction === "uncategorize"}
                                                    onChange={() =>
                                                        setDeleteState((prev) => ({
                                                            ...prev,
                                                            splitAction: "uncategorize",
                                                            reassignCategoryId: null,
                                                        }))
                                                    }
                                                />
                                                Leave uncategorized
                                            </label>
                                            <label className="flex items-center gap-2 text-sm text-secondary">
                                                <input
                                                    type="radio"
                                                    name="splitAction"
                                                    checked={deleteState.splitAction === "reassign"}
                                                    onChange={() =>
                                                        setDeleteState((prev) => ({
                                                            ...prev,
                                                            splitAction: "reassign",
                                                        }))
                                                    }
                                                />
                                                Reassign to another category
                                            </label>
                                            {deleteState.splitAction === "reassign" && (
                                                <div className="ml-6">
                                                    <CategoryTreePicker
                                                        categories={categories.filter(
                                                            (c) => c.id !== deleteState.category?.id,
                                                        )}
                                                        selectedCategoryId={deleteState.reassignCategoryId}
                                                        onSelect={(id) =>
                                                            setDeleteState((prev) => ({
                                                                ...prev,
                                                                reassignCategoryId: id,
                                                            }))
                                                        }
                                                        placeholder="Select target category"
                                                    />
                                                </div>
                                            )}
                                        </fieldset>
                                    )}

                                    {/* Child handling strategy */}
                                    {!deleteState.loading && hasImpact && (preview?.child_count ?? 0) > 0 && (
                                        <fieldset className="flex flex-col gap-2">
                                            <legend className="text-sm font-medium text-primary">
                                                What should happen to subcategories?
                                            </legend>
                                            <label className="flex items-center gap-2 text-sm text-secondary">
                                                <input
                                                    type="radio"
                                                    name="childAction"
                                                    checked={deleteState.childAction === "promote"}
                                                    onChange={() =>
                                                        setDeleteState((prev) => ({
                                                            ...prev,
                                                            childAction: "promote",
                                                            reparentCategoryId: null,
                                                        }))
                                                    }
                                                />
                                                Promote to root categories
                                            </label>
                                            <label className="flex items-center gap-2 text-sm text-secondary">
                                                <input
                                                    type="radio"
                                                    name="childAction"
                                                    checked={deleteState.childAction === "reparent"}
                                                    onChange={() =>
                                                        setDeleteState((prev) => ({
                                                            ...prev,
                                                            childAction: "reparent",
                                                        }))
                                                    }
                                                />
                                                Move under another parent
                                            </label>
                                            {deleteState.childAction === "reparent" && (
                                                <div className="ml-6">
                                                    <CategoryTreePicker
                                                        categories={categories.filter(
                                                            (c) =>
                                                                c.id !== deleteState.category?.id &&
                                                                c.parent_id === null,
                                                        )}
                                                        selectedCategoryId={deleteState.reparentCategoryId}
                                                        onSelect={(id) =>
                                                            setDeleteState((prev) => ({
                                                                ...prev,
                                                                reparentCategoryId: id,
                                                            }))
                                                        }
                                                        placeholder="Select parent category"
                                                    />
                                                </div>
                                            )}
                                        </fieldset>
                                    )}

                                    {deleteState.error && (
                                        <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                            {deleteState.error}
                                        </div>
                                    )}
                                    <div className="flex justify-end gap-2">
                                        <Button color="tertiary" onClick={() => setDeleteState(EMPTY_DELETE)}>
                                            Cancel
                                        </Button>
                                        <DemoGuard>
                                            <Button
                                                color="primary"
                                                isDisabled={deleteDisabled}
                                                onClick={confirmDeleteCategory}
                                            >
                                                Delete
                                            </Button>
                                        </DemoGuard>
                                    </div>
                                </div>
                            );
                        })()}
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </section>
    );
};

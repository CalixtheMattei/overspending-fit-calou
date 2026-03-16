import { useCallback, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ChevronDown, Plus } from "@untitledui/icons";
import { getCategoryDisplayLabel, resolveCategoryIcon } from "@/components/ledger/categories/category-visuals";
import { cx } from "@/utils/cx";
import type { Category } from "@/services/categories";

/* -------------------------------------------------------------------------- */
/*  Types                                                                     */
/* -------------------------------------------------------------------------- */

type TreeNode = {
    category: Category;
    children: TreeNode[];
};

export interface CategoryTreePickerProps {
    categories: Category[];
    /** Currently selected category ID (null = nothing selected). */
    selectedCategoryId: number | null;
    /** Called when a leaf/root category is picked. */
    onSelect: (categoryId: number) => void;
    /** Called when the user clicks "Create category" CTA. */
    onCreateCategory?: () => void;
    /** Called when the user clicks "Create subcategory" under a parent. */
    onCreateSubcategory?: (parentId: number) => void;
    /** Placeholder text shown in the trigger button. */
    placeholder?: string;
    /** Accessible label for the trigger. */
    "aria-label"?: string;
    /** When true the picker is non-interactive. */
    isDisabled?: boolean;
    /** Optional slot shown before the label inside the trigger. */
    triggerIcon?: ReactNode;
    /** Hide deprecated categories unless they are selected. */
    hideDeprecated?: boolean;
    /** Extra category IDs to always show even if deprecated. */
    forceVisibleIds?: Set<number>;
}

/* -------------------------------------------------------------------------- */
/*  Helpers                                                                   */
/* -------------------------------------------------------------------------- */

const buildTree = (
    categories: Category[],
    hideDeprecated: boolean,
    forceVisibleIds: Set<number> | undefined,
    selectedId: number | null,
): TreeNode[] => {
    // Decide which IDs are visible
    const visibleIds = new Set<number>();
    for (const cat of categories) {
        const isSelected = cat.id === selectedId;
        const isForced = forceVisibleIds?.has(cat.id);
        if (!cat.is_deprecated || isSelected || isForced || !hideDeprecated) {
            visibleIds.add(cat.id);
        }
    }
    // Also add parents of visible children
    for (const cat of categories) {
        if (visibleIds.has(cat.id) && cat.parent_id !== null) {
            visibleIds.add(cat.parent_id);
        }
    }

    const visible = categories.filter((c) => visibleIds.has(c.id));
    const childrenByParent = new Map<number, Category[]>();
    const roots: Category[] = [];

    for (const cat of visible) {
        if (cat.parent_id === null || !visibleIds.has(cat.parent_id)) {
            roots.push(cat);
        } else {
            const arr = childrenByParent.get(cat.parent_id) ?? [];
            arr.push(cat);
            childrenByParent.set(cat.parent_id, arr);
        }
    }

    const sortFn = (a: Category, b: Category) =>
        getCategoryDisplayLabel(a).localeCompare(getCategoryDisplayLabel(b));
    roots.sort(sortFn);
    childrenByParent.forEach((arr) => arr.sort(sortFn));

    const toNode = (cat: Category): TreeNode => ({
        category: cat,
        children: (childrenByParent.get(cat.id) ?? []).map(toNode),
    });

    return roots.map(toNode);
};

/* -------------------------------------------------------------------------- */
/*  Component                                                                 */
/* -------------------------------------------------------------------------- */

export const CategoryTreePicker = ({
    categories,
    selectedCategoryId,
    onSelect,
    onCreateCategory,
    onCreateSubcategory,
    placeholder = "Category",
    "aria-label": ariaLabel = "Category",
    isDisabled = false,
    hideDeprecated = true,
    forceVisibleIds,
}: CategoryTreePickerProps) => {
    const [isOpen, setIsOpen] = useState(false);
    const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
    const [focusIndex, setFocusIndex] = useState(-1);
    const containerRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);

    const tree = useMemo(
        () => buildTree(categories, hideDeprecated, forceVisibleIds, selectedCategoryId),
        [categories, hideDeprecated, forceVisibleIds, selectedCategoryId],
    );

    const categoryById = useMemo(
        () => new Map(categories.map((c) => [c.id, c])),
        [categories],
    );

    const selectedCategory = selectedCategoryId ? categoryById.get(selectedCategoryId) ?? null : null;

    // Flatten visible nodes for keyboard nav
    const flatItems = useMemo(() => {
        const items: { id: number | string; node: TreeNode | null; depth: number; type: "category" | "create" | "create-sub" }[] = [];
        const walk = (nodes: TreeNode[], depth: number) => {
            for (const node of nodes) {
                items.push({ id: node.category.id, node, depth, type: "category" });
                if (node.children.length > 0 && expandedIds.has(node.category.id)) {
                    walk(node.children, depth + 1);
                    if (onCreateSubcategory) {
                        items.push({ id: `create-sub-${node.category.id}`, node, depth: depth + 1, type: "create-sub" });
                    }
                }
            }
        };
        if (onCreateCategory) {
            items.push({ id: "create", node: null, depth: 0, type: "create" });
        }
        walk(tree, 0);
        return items;
    }, [tree, expandedIds, onCreateCategory, onCreateSubcategory]);

    const toggleExpanded = useCallback((id: number) => {
        setExpandedIds((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }, []);

    const openPicker = useCallback(() => {
        if (isDisabled) return;
        setIsOpen(true);
        setFocusIndex(-1);
        // Auto-expand parent of selected item
        if (selectedCategoryId) {
            const cat = categoryById.get(selectedCategoryId);
            if (cat?.parent_id) {
                setExpandedIds((prev) => new Set([...prev, cat.parent_id!]));
            }
        }
    }, [isDisabled, selectedCategoryId, categoryById]);

    const closePicker = useCallback(() => {
        setIsOpen(false);
        setFocusIndex(-1);
        triggerRef.current?.focus();
    }, []);

    const handleSelect = useCallback(
        (categoryId: number) => {
            onSelect(categoryId);
            closePicker();
        },
        [onSelect, closePicker],
    );

    const handleKeyDown = useCallback(
        (e: KeyboardEvent) => {
            if (!isOpen) {
                if (e.key === "Enter" || e.key === " " || e.key === "ArrowDown") {
                    e.preventDefault();
                    openPicker();
                }
                return;
            }

            switch (e.key) {
                case "Escape":
                    e.preventDefault();
                    closePicker();
                    break;
                case "ArrowDown":
                    e.preventDefault();
                    setFocusIndex((prev) => Math.min(prev + 1, flatItems.length - 1));
                    break;
                case "ArrowUp":
                    e.preventDefault();
                    setFocusIndex((prev) => Math.max(prev - 1, 0));
                    break;
                case "ArrowRight": {
                    e.preventDefault();
                    const item = flatItems[focusIndex];
                    if (item?.type === "category" && item.node && item.node.children.length > 0) {
                        setExpandedIds((prev) => new Set([...prev, item.node!.category.id]));
                    }
                    break;
                }
                case "ArrowLeft": {
                    e.preventDefault();
                    const item = flatItems[focusIndex];
                    if (item?.type === "category" && item.node && expandedIds.has(item.node.category.id)) {
                        setExpandedIds((prev) => {
                            const next = new Set(prev);
                            next.delete(item.node!.category.id);
                            return next;
                        });
                    }
                    break;
                }
                case "Enter":
                case " ": {
                    e.preventDefault();
                    const item = flatItems[focusIndex];
                    if (!item) break;
                    if (item.type === "create") {
                        onCreateCategory?.();
                        closePicker();
                    } else if (item.type === "create-sub" && item.node) {
                        onCreateSubcategory?.(item.node.category.id);
                        closePicker();
                    } else if (item.type === "category" && item.node) {
                        if (item.node.children.length > 0) {
                            toggleExpanded(item.node.category.id);
                        } else {
                            handleSelect(item.node.category.id);
                        }
                    }
                    break;
                }
            }
        },
        [isOpen, openPicker, closePicker, flatItems, focusIndex, expandedIds, toggleExpanded, handleSelect, onCreateCategory, onCreateSubcategory],
    );

    // Click outside
    const handleBlur = useCallback(() => {
        // Use timeout so inner clicks register first
        setTimeout(() => {
            if (containerRef.current && !containerRef.current.contains(document.activeElement)) {
                setIsOpen(false);
            }
        }, 0);
    }, []);

    const SelectedIcon = selectedCategory ? resolveCategoryIcon(selectedCategory.icon) : null;

    return (
        <div ref={containerRef} className="relative" onBlur={handleBlur}>
            {/* Trigger */}
            <button
                ref={triggerRef}
                type="button"
                role="combobox"
                aria-label={ariaLabel}
                aria-expanded={isOpen}
                aria-haspopup="listbox"
                disabled={isDisabled}
                className={cx(
                    "relative flex w-full cursor-pointer items-center rounded-lg bg-primary shadow-xs ring-1 ring-primary outline-hidden transition duration-100 ease-linear ring-inset",
                    "py-2 px-3",
                    isOpen && "ring-2 ring-brand",
                    isDisabled && "cursor-not-allowed bg-disabled_subtle text-disabled",
                )}
                onClick={() => (isOpen ? closePicker() : openPicker())}
                onKeyDown={handleKeyDown}
            >
                {selectedCategory ? (
                    <span className="flex w-full items-center gap-2 truncate">
                        <span className="inline-flex items-center gap-1.5 shrink-0">
                            <span
                                className="size-2.5 rounded-full ring-1 ring-secondary"
                                style={{ backgroundColor: selectedCategory.color }}
                            />
                            {SelectedIcon && <SelectedIcon className="size-4 text-fg-quaternary" />}
                        </span>
                        <span className="truncate text-md font-medium text-primary">
                            {getCategoryDisplayLabel(selectedCategory)}
                        </span>
                    </span>
                ) : (
                    <span className="text-md text-placeholder">{placeholder}</span>
                )}
                <ChevronDown
                    aria-hidden="true"
                    className={cx(
                        "ml-auto size-4 shrink-0 stroke-[2.5px] text-fg-quaternary transition-transform",
                        isOpen && "rotate-180",
                    )}
                />
            </button>

            {/* Dropdown */}
            {isOpen && (
                <div
                    role="listbox"
                    aria-label={ariaLabel}
                    className="absolute z-50 mt-1 max-h-72 w-full overflow-y-auto rounded-lg bg-primary p-1 shadow-lg ring-1 ring-secondary"
                    onKeyDown={handleKeyDown}
                >
                    {onCreateCategory && (
                        <button
                            type="button"
                            role="option"
                            aria-selected={false}
                            className={cx(
                                "flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm font-medium text-brand-secondary hover:bg-primary_hover",
                                focusIndex === 0 && "bg-primary_hover",
                            )}
                            onClick={() => {
                                onCreateCategory();
                                closePicker();
                            }}
                            onMouseEnter={() => setFocusIndex(0)}
                        >
                            <Plus className="size-4" />
                            Create category
                        </button>
                    )}
                    {tree.map((node) => (
                        <TreeNodeRow
                            key={node.category.id}
                            node={node}
                            depth={0}
                            selectedCategoryId={selectedCategoryId}
                            expandedIds={expandedIds}
                            focusIndex={focusIndex}
                            flatItems={flatItems}
                            onToggle={toggleExpanded}
                            onSelect={handleSelect}
                            onCreateSubcategory={onCreateSubcategory}
                            onFocusIndex={setFocusIndex}
                            closePicker={closePicker}
                        />
                    ))}
                </div>
            )}
        </div>
    );
};

/* -------------------------------------------------------------------------- */
/*  Tree node row                                                             */
/* -------------------------------------------------------------------------- */

interface TreeNodeRowProps {
    node: TreeNode;
    depth: number;
    selectedCategoryId: number | null;
    expandedIds: Set<number>;
    focusIndex: number;
    flatItems: { id: number | string; node: TreeNode | null; depth: number; type: string }[];
    onToggle: (id: number) => void;
    onSelect: (id: number) => void;
    onCreateSubcategory?: (parentId: number) => void;
    onFocusIndex: (index: number) => void;
    closePicker: () => void;
}

const TreeNodeRow = ({
    node,
    depth,
    selectedCategoryId,
    expandedIds,
    focusIndex,
    flatItems,
    onToggle,
    onSelect,
    onCreateSubcategory,
    onFocusIndex,
    closePicker,
}: TreeNodeRowProps) => {
    const { category, children } = node;
    const hasChildren = children.length > 0;
    const isExpanded = expandedIds.has(category.id);
    const isSelected = category.id === selectedCategoryId;
    const Icon = resolveCategoryIcon(category.icon);
    const myIndex = flatItems.findIndex((item) => item.id === category.id);
    const isFocused = focusIndex === myIndex;

    return (
        <>
            <button
                type="button"
                role="option"
                aria-selected={isSelected}
                className={cx(
                    "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors",
                    isSelected && "bg-active",
                    isFocused && "bg-primary_hover",
                    !isSelected && !isFocused && "hover:bg-primary_hover",
                )}
                style={{ paddingLeft: `${depth * 20 + 8}px` }}
                onClick={() => {
                    if (hasChildren) {
                        onToggle(category.id);
                    } else {
                        onSelect(category.id);
                    }
                }}
                onDoubleClick={() => {
                    // Allow selecting parent categories on double click
                    if (hasChildren) {
                        onSelect(category.id);
                    }
                }}
                onMouseEnter={() => onFocusIndex(myIndex)}
            >
                {hasChildren && (
                    <ChevronDown
                        className={cx(
                            "size-3.5 shrink-0 text-fg-quaternary transition-transform",
                            isExpanded && "rotate-180",
                        )}
                    />
                )}
                <span className="inline-flex items-center gap-1.5 shrink-0">
                    <span
                        className="size-2.5 rounded-full ring-1 ring-secondary"
                        style={{ backgroundColor: category.color }}
                    />
                    <Icon className="size-4 text-fg-quaternary" />
                </span>
                <span className="truncate font-medium text-primary">
                    {getCategoryDisplayLabel(category)}
                </span>
                {hasChildren && (
                    <span className="ml-auto text-xs text-tertiary">{children.length}</span>
                )}
            </button>

            {hasChildren && isExpanded && (
                <>
                    {children.map((child) => (
                        <TreeNodeRow
                            key={child.category.id}
                            node={child}
                            depth={depth + 1}
                            selectedCategoryId={selectedCategoryId}
                            expandedIds={expandedIds}
                            focusIndex={focusIndex}
                            flatItems={flatItems}
                            onToggle={onToggle}
                            onSelect={onSelect}
                            onCreateSubcategory={onCreateSubcategory}
                            onFocusIndex={onFocusIndex}
                            closePicker={closePicker}
                        />
                    ))}
                    {onCreateSubcategory && (
                        <button
                            type="button"
                            role="option"
                            aria-selected={false}
                            className={cx(
                                "flex w-full items-center gap-2 rounded-md py-1.5 text-left text-xs font-medium text-brand-secondary hover:bg-primary_hover",
                                focusIndex === flatItems.findIndex((item) => item.id === `create-sub-${category.id}`) && "bg-primary_hover",
                            )}
                            style={{ paddingLeft: `${(depth + 1) * 20 + 8}px` }}
                            onClick={() => {
                                onCreateSubcategory(category.id);
                                closePicker();
                            }}
                            onMouseEnter={() => {
                                const idx = flatItems.findIndex((item) => item.id === `create-sub-${category.id}`);
                                if (idx >= 0) onFocusIndex(idx);
                            }}
                        >
                            <Plus className="size-3.5" />
                            Create category
                        </button>
                    )}
                </>
            )}
        </>
    );
};

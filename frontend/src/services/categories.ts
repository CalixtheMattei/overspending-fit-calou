import { apiFetch } from "./api";

const CATEGORY_QUERY_LIMIT_MAX = 200;

export type Category = {
    id: number;
    name: string;
    parent_id: number | null;
    color: string;
    icon: string;
    is_custom: boolean;
    display_name?: string | null;
    is_deprecated?: boolean;
    canonical_id?: number | null;
    group?: string | null;
};

export type CategoryPresets = {
    colors: string[];
    icons: string[];
    default_color: string;
    default_icon: string;
    categories: Category[];
    tree: Array<Category & { children?: Category[] }>;
};

export const fetchCategories = async (params: { q?: string; limit?: number } = {}) => {
    const search = new URLSearchParams();
    if (params.q) search.set("q", params.q);
    if (typeof params.limit === "number" && Number.isFinite(params.limit)) {
        const boundedLimit = Math.min(CATEGORY_QUERY_LIMIT_MAX, Math.max(1, Math.trunc(params.limit)));
        search.set("limit", String(boundedLimit));
    }
    const query = search.toString();
    return apiFetch<Category[]>(`/categories${query ? `?${query}` : ""}`);
};

export const fetchCategoryPresets = async () => apiFetch<CategoryPresets>("/categories/presets");

export const createCategory = async (payload: {
    name: string;
    parent_id?: number | null;
    color?: string | null;
    icon?: string | null;
}) =>
    apiFetch<Category>("/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export const updateCategory = async (
    categoryId: number,
    payload: { name?: string; parent_id?: number | null; color?: string; icon?: string },
) =>
    apiFetch<Category>(`/categories/${categoryId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });

export type DeletePreview = {
    direct_split_count: number;
    child_count: number;
    children: { id: number; name: string }[];
};

export type DeleteStrategy = {
    split_action: "uncategorize" | "reassign";
    reassign_category_id?: number | null;
    child_action: "promote" | "reparent";
    reparent_category_id?: number | null;
};

export const fetchDeletePreview = async (categoryId: number) =>
    apiFetch<DeletePreview>(`/categories/${categoryId}/delete-preview`);

export const deleteCategory = async (categoryId: number, strategy?: DeleteStrategy) =>
    apiFetch<{ deleted: boolean; splits_reassigned: number; children_moved: number }>(
        `/categories/${categoryId}`,
        {
            method: "DELETE",
            ...(strategy
                ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(strategy) }
                : {}),
        },
    );

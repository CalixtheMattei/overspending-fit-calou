import type { FlowResponse } from "@/services/analytics";

export type SankeyNode = {
    name: string;
    /** Original node ID from the backend (e.g. "expense", "cat_12", "uncategorized") */
    nodeId: string;
    /** Discriminator: "transaction_type" for source nodes, "category_bucket" for category nodes */
    kind: "transaction_type" | "category_bucket";
    /** Present only on category_bucket nodes that have a real category */
    categoryId?: number;
    /** Present only on transaction_type source nodes */
    transactionType?: string;
};

export type SankeyLink = { source: number; target: number; value: number };
export type SankeyData = { nodes: SankeyNode[]; links: SankeyLink[] };

type SankeyFilterOptions = {
    hiddenCategoryIds: Set<string>;
    hiddenTypeIds: Set<string>;
};

export const buildSankeyData = (flow: FlowResponse | null, options: SankeyFilterOptions): SankeyData => {
    if (!flow) {
        return { nodes: [], links: [] };
    }

    const visibleLinks = flow.links.filter(
        (link) => !options.hiddenTypeIds.has(link.source) && !options.hiddenCategoryIds.has(link.target),
    );

    const visibleNodeIds = new Set<string>();
    visibleLinks.forEach((link) => {
        visibleNodeIds.add(link.source);
        visibleNodeIds.add(link.target);
    });

    const nodes = flow.nodes
        .filter((node) => visibleNodeIds.has(node.id))
        .sort((a, b) => {
            if (a.type === b.type) {
                return a.name.localeCompare(b.name);
            }
            return a.type === "source" ? -1 : 1;
        });

    const nodeIndex = new Map<string, number>();
    nodes.forEach((node, index) => {
        nodeIndex.set(node.id, index);
    });

    const links = visibleLinks
        .map((link) => ({
            source: nodeIndex.get(link.source),
            target: nodeIndex.get(link.target),
            value: link.value,
        }))
        .filter((link) => link.source !== undefined && link.target !== undefined)
        .map((link) => ({
            source: link.source as number,
            target: link.target as number,
            value: link.value,
        }));

    return {
        nodes: nodes.map((node) => ({
            name: node.name,
            nodeId: node.id,
            kind: node.kind,
            ...(node.category_id !== undefined ? { categoryId: node.category_id } : {}),
            ...(node.transaction_type !== undefined ? { transactionType: node.transaction_type } : {}),
        })),
        links,
    };
};

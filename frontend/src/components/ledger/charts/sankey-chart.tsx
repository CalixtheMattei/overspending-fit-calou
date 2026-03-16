import { useCallback } from "react";
import { Layer, Rectangle, ResponsiveContainer, Sankey, Tooltip } from "recharts";
import type { SankeyData, SankeyNode } from "./sankey-utils";

export type SankeyNodeClickPayload = {
    nodeId: string;
    kind: "transaction_type" | "category_bucket";
    categoryId?: number;
    transactionType?: string;
};

interface SankeyChartProps {
    data: SankeyData;
    height?: number;
    onNodeClick?: (payload: SankeyNodeClickPayload) => void;
}

/**
 * Custom Sankey node renderer that adds cursor:pointer and hover opacity
 * when an onNodeClick handler is provided.
 */
const ClickableSankeyNode = ({
    x,
    y,
    width,
    height,
    index,
    payload,
    containerWidth,
    onNodeClick,
}: {
    x: number;
    y: number;
    width: number;
    height: number;
    index: number;
    payload: SankeyNode & { value?: number };
    containerWidth: number;
    onNodeClick?: (payload: SankeyNodeClickPayload) => void;
}) => {
    const isClickable = !!onNodeClick && payload.kind === "category_bucket";
    const isOut = x + width + 6 > containerWidth;

    const handleClick = () => {
        if (!onNodeClick) return;
        onNodeClick({
            nodeId: payload.nodeId,
            kind: payload.kind,
            ...(payload.categoryId !== undefined ? { categoryId: payload.categoryId } : {}),
            ...(payload.transactionType !== undefined ? { transactionType: payload.transactionType } : {}),
        });
    };

    return (
        <Layer key={`sankey-node-${index}`}>
            <Rectangle
                x={x}
                y={y}
                width={width}
                height={height}
                fill="#5192ca"
                fillOpacity={0.9}
                onClick={isClickable ? handleClick : undefined}
                style={{ cursor: isClickable ? "pointer" : "default" }}
                className={isClickable ? "transition-opacity hover:opacity-80" : ""}
            />
            <text
                textAnchor={isOut ? "end" : "start"}
                x={isOut ? x - 6 : x + width + 6}
                y={y + height / 2}
                fontSize="12"
                dominantBaseline="central"
                fill="currentColor"
                onClick={isClickable ? handleClick : undefined}
                style={{ cursor: isClickable ? "pointer" : "default" }}
            >
                {payload.name}
            </text>
        </Layer>
    );
};

export const SankeyChart = ({ data, height = 320, onNodeClick }: SankeyChartProps) => {
    const renderNode = useCallback(
        (props: Record<string, unknown>) => (
            <ClickableSankeyNode
                {...(props as Parameters<typeof ClickableSankeyNode>[0])}
                onNodeClick={onNodeClick}
            />
        ),
        [onNodeClick],
    );

    return (
        <div style={{ height }} className="w-full">
            <ResponsiveContainer>
                <Sankey
                    data={data}
                    nodePadding={20}
                    nodeWidth={14}
                    margin={{ top: 8, right: 24, bottom: 8, left: 24 }}
                    link={{ stroke: "rgba(148, 163, 184, 0.5)" }}
                    node={renderNode}
                >
                    <Tooltip />
                </Sankey>
            </ResponsiveContainer>
        </div>
    );
};

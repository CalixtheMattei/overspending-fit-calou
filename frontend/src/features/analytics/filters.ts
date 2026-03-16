import type { AnalyticsGranularity, AnalyticsMode } from "@/services/analytics";

// ---------------------------------------------------------------------------
// Core filter state type
// ---------------------------------------------------------------------------

export type AnalyticsFilterState = {
    startDate: string;
    endDate: string;
    granularity: AnalyticsGranularity;
    mode: AnalyticsMode;
    excludeTransfers: boolean;
    excludeMomentTagged: boolean;
    presetId: RangePresetId | null;
};

// ---------------------------------------------------------------------------
// Range presets
// ---------------------------------------------------------------------------

export const RANGE_PRESET_OPTIONS = [
    { id: "7D", label: "7D" },
    { id: "1M", label: "1M" },
    { id: "3M", label: "3M" },
    { id: "6M", label: "6M" },
    { id: "1Y", label: "1Y" },
    { id: "YTD", label: "YTD" },
] as const;

export type RangePresetId = (typeof RANGE_PRESET_OPTIONS)[number]["id"];

/**
 * Subset of presets used in the ledger Sankey (compact chip bar).
 * Kept in the order the dashboard originally displayed them.
 */
export const SANKEY_PRESET_OPTIONS = [
    { id: "6M", label: "6M" },
    { id: "3M", label: "3M" },
    { id: "1M", label: "1M" },
    { id: "7D", label: "7D" },
] as const satisfies readonly { id: RangePresetId; label: string }[];

// The dashboard also had a "TODAY" chip. We keep it in the ledger-specific
// list so the Sankey UI can continue to show it, but it is not a universal
// analytics preset.
export const SANKEY_PRESET_OPTIONS_WITH_TODAY = [
    ...SANKEY_PRESET_OPTIONS,
    { id: "TODAY" as const, label: "Today" },
] as const;

export type SankeyPresetId = (typeof SANKEY_PRESET_OPTIONS_WITH_TODAY)[number]["id"];

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

/** Format a Date to YYYY-MM-DD in local time. */
export const formatDateLocal = (value: Date): string => {
    const year = value.getFullYear();
    const month = String(value.getMonth() + 1).padStart(2, "0");
    const day = String(value.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
};

/** Compute a {start, end} date range from a preset id. */
export const getPresetDateRange = (
    presetId: RangePresetId | SankeyPresetId,
    now = new Date(),
): { start: string; end: string } => {
    const endDate = new Date(now);
    const startDate = new Date(now);

    switch (presetId) {
        case "7D":
            startDate.setDate(startDate.getDate() - 6);
            break;
        case "1M":
            startDate.setMonth(startDate.getMonth() - 1);
            break;
        case "3M":
            startDate.setMonth(startDate.getMonth() - 3);
            break;
        case "6M":
            startDate.setMonth(startDate.getMonth() - 6);
            break;
        case "1Y":
            startDate.setFullYear(startDate.getFullYear() - 1);
            break;
        case "YTD":
            startDate.setMonth(0);
            startDate.setDate(1);
            break;
        case "TODAY":
            startDate.setTime(endDate.getTime());
            break;
        default: {
            // Exhaustive check — fall back to 3M for safety.
            const _exhaustive: never = presetId;
            void _exhaustive;
            startDate.setMonth(startDate.getMonth() - 3);
        }
    }

    return { start: formatDateLocal(startDate), end: formatDateLocal(endDate) };
};

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

export const DEFAULT_PRESET_ID: RangePresetId = "3M";

export const ANALYTICS_FILTER_DEFAULTS: Readonly<AnalyticsFilterState> = {
    startDate: "",
    endDate: "",
    granularity: "week",
    mode: "user",
    excludeTransfers: true,
    excludeMomentTagged: false,
    presetId: DEFAULT_PRESET_ID,
};

/**
 * Factory that returns a fresh default filter state with dates computed from
 * the default preset. Call at init time so dates are current.
 */
export const createDefaultFilterState = (now = new Date()): AnalyticsFilterState => {
    const range = getPresetDateRange(DEFAULT_PRESET_ID, now);
    return {
        ...ANALYTICS_FILTER_DEFAULTS,
        startDate: range.start,
        endDate: range.end,
    };
};

// ---------------------------------------------------------------------------
// Granularity & mode option lists (shared across surfaces)
// ---------------------------------------------------------------------------

export const GRANULARITY_OPTIONS: { id: AnalyticsGranularity; label: string }[] = [
    { id: "day", label: "Daily" },
    { id: "week", label: "Weekly" },
    { id: "month", label: "Monthly" },
];

export const MODE_OPTIONS: { id: AnalyticsMode; label: string }[] = [
    { id: "user", label: "User view" },
    { id: "counterparty", label: "Counterparty view" },
];

// ---------------------------------------------------------------------------
// URL query-param serialization (preparation for D1-T2)
// ---------------------------------------------------------------------------

const QP_KEYS = {
    startDate: "start",
    endDate: "end",
    granularity: "g",
    mode: "m",
    excludeTransfers: "xt",
    excludeMomentTagged: "xmt",
    presetId: "preset",
} as const;

/** Serialize filter state to a URLSearchParams instance. */
export const serializeFilters = (state: AnalyticsFilterState): URLSearchParams => {
    const params = new URLSearchParams();
    if (state.startDate) params.set(QP_KEYS.startDate, state.startDate);
    if (state.endDate) params.set(QP_KEYS.endDate, state.endDate);
    params.set(QP_KEYS.granularity, state.granularity);
    params.set(QP_KEYS.mode, state.mode);
    params.set(QP_KEYS.excludeTransfers, state.excludeTransfers ? "1" : "0");
    params.set(QP_KEYS.excludeMomentTagged, state.excludeMomentTagged ? "1" : "0");
    if (state.presetId) params.set(QP_KEYS.presetId, state.presetId);
    return params;
};

const VALID_GRANULARITIES = new Set<string>(["day", "week", "month"]);
const VALID_MODES = new Set<string>(["user", "counterparty"]);
const VALID_PRESET_IDS = new Set<string>(RANGE_PRESET_OPTIONS.map((o) => o.id));

/** Deserialize URL search params to a partial filter state. Unknown keys are ignored. */
export const deserializeFilters = (params: URLSearchParams): Partial<AnalyticsFilterState> => {
    const result: Partial<AnalyticsFilterState> = {};

    const start = params.get(QP_KEYS.startDate);
    if (start) result.startDate = start;

    const end = params.get(QP_KEYS.endDate);
    if (end) result.endDate = end;

    const granularity = params.get(QP_KEYS.granularity);
    if (granularity && VALID_GRANULARITIES.has(granularity)) {
        result.granularity = granularity as AnalyticsGranularity;
    }

    const mode = params.get(QP_KEYS.mode);
    if (mode && VALID_MODES.has(mode)) {
        result.mode = mode as AnalyticsMode;
    }

    const xt = params.get(QP_KEYS.excludeTransfers);
    if (xt !== null) result.excludeTransfers = xt === "1";

    const xmt = params.get(QP_KEYS.excludeMomentTagged);
    if (xmt !== null) result.excludeMomentTagged = xmt === "1";

    const preset = params.get(QP_KEYS.presetId);
    if (preset && VALID_PRESET_IDS.has(preset)) {
        result.presetId = preset as RangePresetId;
    }

    return result;
};

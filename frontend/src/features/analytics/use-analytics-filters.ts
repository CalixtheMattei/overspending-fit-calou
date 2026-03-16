import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import type { AnalyticsGranularity, AnalyticsMode } from "@/services/analytics";
import {
    DEFAULT_PRESET_ID,
    type AnalyticsFilterState,
    type RangePresetId,
    createDefaultFilterState,
    deserializeFilters,
    getPresetDateRange,
    serializeFilters,
} from "./filters";

// ---------------------------------------------------------------------------
// Session-storage persistence for excludeMomentTagged (matches prior behavior)
// ---------------------------------------------------------------------------

const EXCLUDE_MOMENT_TAGGED_STORAGE_KEY = "analytics-exclude-moment-tagged";

const readExcludeMomentTagged = (): boolean => {
    if (typeof window === "undefined") return false;
    try {
        return window.sessionStorage.getItem(EXCLUDE_MOMENT_TAGGED_STORAGE_KEY) === "true";
    } catch {
        return false;
    }
};

const writeExcludeMomentTagged = (value: boolean): void => {
    if (typeof window === "undefined") return;
    try {
        window.sessionStorage.setItem(EXCLUDE_MOMENT_TAGGED_STORAGE_KEY, String(value));
    } catch {
        // Ignore storage errors and keep in-memory behavior.
    }
};

// ---------------------------------------------------------------------------
// Capability flags — allow each surface to opt in/out of capabilities
// ---------------------------------------------------------------------------

export type AnalyticsFilterCapabilities = {
    /** Surface shows granularity selector. Default true. */
    supportsGranularity?: boolean;
    /** Surface shows mode selector. Default true. */
    supportsMode?: boolean;
    /** Persist excludeMomentTagged to sessionStorage. Default true. */
    persistExcludeMomentTagged?: boolean;
    /** Sync filter state with URL search params. Default false. */
    syncWithUrl?: boolean;
    /** Override the default date-range preset used on first load. */
    initialPresetId?: RangePresetId;
};

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------

export type UseAnalyticsFiltersReturn = {
    filters: AnalyticsFilterState;
    setStartDate: (value: string) => void;
    setEndDate: (value: string) => void;
    setGranularity: (value: AnalyticsGranularity) => void;
    setMode: (value: AnalyticsMode) => void;
    setExcludeTransfers: (updater: boolean | ((prev: boolean) => boolean)) => void;
    setExcludeMomentTagged: (updater: boolean | ((prev: boolean) => boolean)) => void;
    applyPreset: (presetId: RangePresetId) => void;
    applyCustomRange: (start: string, end: string) => void;
    reset: () => void;
    capabilities: Required<AnalyticsFilterCapabilities>;
};

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

export const useAnalyticsFilters = (
    caps: AnalyticsFilterCapabilities = {},
): UseAnalyticsFiltersReturn => {
    const syncWithUrl = caps.syncWithUrl ?? false;
    const [searchParams, setSearchParams] = useSearchParams();

    const capabilities: Required<AnalyticsFilterCapabilities> = useMemo(
        () => ({
            supportsGranularity: caps.supportsGranularity ?? true,
            supportsMode: caps.supportsMode ?? true,
            persistExcludeMomentTagged: caps.persistExcludeMomentTagged ?? true,
            syncWithUrl,
            initialPresetId: caps.initialPresetId ?? DEFAULT_PRESET_ID,
        }),
        [caps.supportsGranularity, caps.supportsMode, caps.persistExcludeMomentTagged, caps.initialPresetId, syncWithUrl],
    );

    // Capture initial URL params once at mount time for hydration.
    const initialUrlOverrides = useRef<Partial<AnalyticsFilterState> | null>(null);
    if (initialUrlOverrides.current === null) {
        initialUrlOverrides.current = syncWithUrl ? deserializeFilters(searchParams) : {};
    }

    const [filters, setFilters] = useState<AnalyticsFilterState>(() => {
        const presetId = caps.initialPresetId;
        const defaults = presetId
            ? (() => {
                  const base = createDefaultFilterState();
                  const range = getPresetDateRange(presetId);
                  return { ...base, startDate: range.start, endDate: range.end, presetId };
              })()
            : createDefaultFilterState();
        // Hydrate excludeMomentTagged from storage if persistence is on
        if (capabilities.persistExcludeMomentTagged) {
            defaults.excludeMomentTagged = readExcludeMomentTagged();
        }
        // Hydrate from URL search params if sync is enabled (URL takes precedence)
        if (syncWithUrl && initialUrlOverrides.current) {
            return { ...defaults, ...initialUrlOverrides.current };
        }
        return defaults;
    });

    // Track whether this is the initial render to avoid writing URL params on mount
    // when they were already hydrated from the URL.
    const isInitialRender = useRef(true);

    // Push filter state to URL whenever filters change (skip first render to
    // avoid replacing URL params that were just read).
    useEffect(() => {
        if (!syncWithUrl) return;
        if (isInitialRender.current) {
            isInitialRender.current = false;
            // On initial render, write params to URL so the URL always reflects
            // the active state (even when loaded without query params).
            const nextParams = serializeFilters(filters);
            setSearchParams(nextParams, { replace: true });
            return;
        }
        const nextParams = serializeFilters(filters);
        setSearchParams(nextParams, { replace: true });
    }, [filters, syncWithUrl, setSearchParams]);

    // Persist excludeMomentTagged whenever it changes
    useEffect(() => {
        if (capabilities.persistExcludeMomentTagged) {
            writeExcludeMomentTagged(filters.excludeMomentTagged);
        }
    }, [filters.excludeMomentTagged, capabilities.persistExcludeMomentTagged]);

    const setStartDate = useCallback((value: string) => {
        setFilters((prev) => ({ ...prev, startDate: value, presetId: null }));
    }, []);

    const setEndDate = useCallback((value: string) => {
        setFilters((prev) => ({ ...prev, endDate: value, presetId: null }));
    }, []);

    const setGranularity = useCallback((value: AnalyticsGranularity) => {
        setFilters((prev) => ({ ...prev, granularity: value }));
    }, []);

    const setMode = useCallback((value: AnalyticsMode) => {
        setFilters((prev) => ({ ...prev, mode: value }));
    }, []);

    const setExcludeTransfers = useCallback((updater: boolean | ((prev: boolean) => boolean)) => {
        setFilters((prev) => ({
            ...prev,
            excludeTransfers: typeof updater === "function" ? updater(prev.excludeTransfers) : updater,
        }));
    }, []);

    const setExcludeMomentTagged = useCallback((updater: boolean | ((prev: boolean) => boolean)) => {
        setFilters((prev) => ({
            ...prev,
            excludeMomentTagged:
                typeof updater === "function" ? updater(prev.excludeMomentTagged) : updater,
        }));
    }, []);

    const applyPreset = useCallback((presetId: RangePresetId) => {
        const range = getPresetDateRange(presetId);
        setFilters((prev) => ({
            ...prev,
            startDate: range.start,
            endDate: range.end,
            presetId,
        }));
    }, []);

    const applyCustomRange = useCallback((start: string, end: string) => {
        setFilters((prev) => ({
            ...prev,
            startDate: start,
            endDate: end,
            presetId: null,
        }));
    }, []);

    const reset = useCallback(() => {
        const defaults = createDefaultFilterState();
        setFilters(defaults);
    }, []);

    return {
        filters,
        setStartDate,
        setEndDate,
        setGranularity,
        setMode,
        setExcludeTransfers,
        setExcludeMomentTagged,
        applyPreset,
        applyCustomRange,
        reset,
        capabilities,
    };
};

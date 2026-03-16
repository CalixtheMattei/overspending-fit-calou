import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router";
import { ChevronDown, FileCheck02, FilePlus02, SearchLg, UploadCloud02 } from "@untitledui/icons";
import { toCalendarDate } from "@internationalized/date";
import type { SortDescriptor, SortDirection } from "@react-types/shared";
import type { DateValue } from "react-aria-components";
import { DateRangePicker } from "@/components/application/date-picker/date-range-picker";
import { EmptyState } from "@/components/application/empty-state/empty-state";
import { FileUpload } from "@/components/application/file-upload/file-upload-base";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { PaginationCardMinimal } from "@/components/application/pagination/pagination";
import { SlideoutMenu } from "@/components/application/slideout-menus/slideout-menu";
import { Table, TableCard } from "@/components/application/table/table";
import { Tabs } from "@/components/application/tabs/tabs";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { ButtonUtility } from "@/components/base/buttons/button-utility";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";
import { SectionDivider } from "@/components/shared-assets/section-divider";
import { cx } from "@/utils/cx";
import type {
    ImportRowDetail,
    ImportRowSummary,
    ImportRowWithImport,
    ImportStats,
    ImportSummary,
} from "@/services/imports";
import {
    confirmImport,
    fetchAllImportRows,
    fetchImportRow,
    fetchImportRows,
    fetchImports,
    previewImport,
} from "@/services/imports";

type RowsFilter = "all" | "unlinked" | "errors";
type DateRange = { start: DateValue; end: DateValue };
const DEFAULT_ROWS_LIMIT = 25;
const ROWS_PER_PAGE_OPTIONS = [25, 50, 75, 100].map((value) => ({ id: String(value), label: String(value) }));

const IMPORT_ROWS_COLUMNS = [
    { id: "date_val", name: "Date" },
    { id: "label", name: "Label" },
    { id: "supplier", name: "Supplier" },
    { id: "amount", name: "Amount" },
    { id: "category", name: "Raw category" },
    { id: "transaction", name: "Transaction" },
] as const;

type ImportRowsColumn = (typeof IMPORT_ROWS_COLUMNS)[number];
type ImportRowsColumnId = ImportRowsColumn["id"];

const ALL_ROWS_COLUMNS = [
    { id: "import", name: "Import" },
    { id: "imported_at", name: "Imported at" },
    { id: "account", name: "Account" },
    { id: "date_val", name: "Date" },
    { id: "label", name: "Label" },
    { id: "supplier", name: "Supplier" },
    { id: "amount", name: "Amount" },
    { id: "category", name: "Raw category" },
    { id: "transaction", name: "Transaction" },
] as const;

type AllRowsColumn = (typeof ALL_ROWS_COLUMNS)[number];
type AllRowsColumnId = AllRowsColumn["id"];

const IMPORT_TAB_IDS = ["import-history", "all-transactions"] as const;
type ImportTabId = (typeof IMPORT_TAB_IDS)[number];

const IMPORT_TABS: { id: ImportTabId; label: string }[] = [
    { id: "import-history", label: "Import history" },
    { id: "all-transactions", label: "All transactions" },
];

type DrawerContext = { importId: number; rowId: number } | null;

export const ImportsPage = () => {
    const navigate = useNavigate();
    const { importId } = useParams();

    const [imports, setImports] = useState<ImportSummary[]>([]);
    const [importsLoading, setImportsLoading] = useState(true);
    const [importsError, setImportsError] = useState<string | null>(null);

    const [expandedImportId, setExpandedImportId] = useState<number | null>(null);
    const [hasAutoExpanded, setHasAutoExpanded] = useState(false);

    const [rows, setRows] = useState<ImportRowSummary[]>([]);
    const [rowsTotal, setRowsTotal] = useState(0);
    const [rowsLoading, setRowsLoading] = useState(false);
    const [rowsError, setRowsError] = useState<string | null>(null);
    const [rowsPage, setRowsPage] = useState(1);
    const [rowsFilter, setRowsFilter] = useState<RowsFilter>("all");
    const [importRowsLimit, setImportRowsLimit] = useState(DEFAULT_ROWS_LIMIT);

    const [allRows, setAllRows] = useState<ImportRowWithImport[]>([]);
    const [allRowsTotal, setAllRowsTotal] = useState(0);
    const [allRowsLoading, setAllRowsLoading] = useState(false);
    const [allRowsError, setAllRowsError] = useState<string | null>(null);
    const [allRowsPage, setAllRowsPage] = useState(1);
    const [allRowsFilter, setAllRowsFilter] = useState<RowsFilter>("all");
    const [allRowsLimit, setAllRowsLimit] = useState(DEFAULT_ROWS_LIMIT);
    const [allRowsRefreshKey, setAllRowsRefreshKey] = useState(0);
    const [allRowsSearch, setAllRowsSearch] = useState("");
    const [allRowsDateRangeDraft, setAllRowsDateRangeDraft] = useState<DateRange | null>(null);
    const [allRowsDateRangeApplied, setAllRowsDateRangeApplied] = useState<DateRange | null>(null);
    const [allRowsSort, setAllRowsSort] = useState<"date_val" | "amount" | null>(null);
    const [allRowsSortDirection, setAllRowsSortDirection] = useState<SortDirection>("descending");

    const [activeTab, setActiveTab] = useState<ImportTabId>("import-history");

    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [previewStats, setPreviewStats] = useState<ImportStats | null>(null);
    const [previewing, setPreviewing] = useState(false);
    const [previewError, setPreviewError] = useState<string | null>(null);
    const [confirming, setConfirming] = useState(false);
    const [confirmError, setConfirmError] = useState<string | null>(null);
    const [confirmSuccess, setConfirmSuccess] = useState(false);
    const [lastImportId, setLastImportId] = useState<number | null>(null);

    const [drawerContext, setDrawerContext] = useState<DrawerContext>(null);
    const [drawerRow, setDrawerRow] = useState<ImportRowDetail | null>(null);
    const [drawerLoading, setDrawerLoading] = useState(false);
    const [drawerError, setDrawerError] = useState<string | null>(null);

    const importsById = useMemo(() => new Map(imports.map((item) => [item.id, item])), [imports]);
    useEffect(() => {
        const loadImports = async () => {
            setImportsLoading(true);
            setImportsError(null);
            try {
                const data = await fetchImports();
                setImports(data);
            } catch (error) {
                setImportsError(error instanceof Error ? error.message : "Failed to load imports.");
            } finally {
                setImportsLoading(false);
            }
        };

        loadImports();
    }, []);

    useEffect(() => {
        if (!imports.length) {
            setExpandedImportId(null);
            return;
        }

        if (importId) {
            const parsed = Number(importId);
            if (!Number.isNaN(parsed) && imports.some((item) => item.id === parsed)) {
                setExpandedImportId(parsed);
                setHasAutoExpanded(true);
                setActiveTab("import-history");
                return;
            }
        }

        if (!hasAutoExpanded) {
            setExpandedImportId(imports[0].id);
            setHasAutoExpanded(true);
        }
    }, [importId, imports, hasAutoExpanded]);

    useEffect(() => {
        if (!expandedImportId) {
            setRows([]);
            setRowsTotal(0);
            setRowsError(null);
            setRowsLoading(false);
            return;
        }

        let isActive = true;
        const loadRows = async () => {
            setRowsLoading(true);
            setRowsError(null);
            try {
                const status = getStatusParam(rowsFilter);
                const data = await fetchImportRows(expandedImportId, {
                    limit: importRowsLimit,
                    offset: (rowsPage - 1) * importRowsLimit,
                    status,
                });
                if (!isActive) return;
                setRows(data.rows);
                setRowsTotal(data.total);
            } catch (error) {
                if (!isActive) return;
                setRowsError(error instanceof Error ? error.message : "Failed to load import rows.");
            } finally {
                if (isActive) {
                    setRowsLoading(false);
                }
            }
        };

        loadRows();

        return () => {
            isActive = false;
        };
    }, [expandedImportId, rowsFilter, rowsPage, importRowsLimit]);

    useEffect(() => {
        let isActive = true;
        const loadAllRows = async () => {
            setAllRowsLoading(true);
            setAllRowsError(null);
            try {
                const status = getStatusParam(allRowsFilter);
                const trimmedSearch = allRowsSearch.trim();
                const dateFrom = allRowsDateRangeApplied?.start
                    ? toCalendarDate(allRowsDateRangeApplied.start).toString()
                    : undefined;
                const dateTo = allRowsDateRangeApplied?.end
                    ? toCalendarDate(allRowsDateRangeApplied.end).toString()
                    : undefined;
                const sort = allRowsSort ?? undefined;
                const direction = allRowsSort
                    ? allRowsSortDirection === "ascending"
                        ? "asc"
                        : "desc"
                    : undefined;
                const data = await fetchAllImportRows({
                    limit: allRowsLimit,
                    offset: (allRowsPage - 1) * allRowsLimit,
                    status,
                    q: trimmedSearch || undefined,
                    date_from: dateFrom,
                    date_to: dateTo,
                    sort,
                    direction,
                });
                if (!isActive) return;
                setAllRows(data.rows);
                setAllRowsTotal(data.total);
            } catch (error) {
                if (!isActive) return;
                setAllRowsError(error instanceof Error ? error.message : "Failed to load transactions.");
            } finally {
                if (isActive) {
                    setAllRowsLoading(false);
                }
            }
        };

        loadAllRows();

        return () => {
            isActive = false;
        };
    }, [
        allRowsFilter,
        allRowsPage,
        allRowsLimit,
        allRowsRefreshKey,
        allRowsSearch,
        allRowsDateRangeApplied,
        allRowsSort,
        allRowsSortDirection,
    ]);

    useEffect(() => {
        if (!drawerContext) {
            setDrawerRow(null);
            return;
        }

        let isActive = true;
        const loadRow = async () => {
            setDrawerLoading(true);
            setDrawerError(null);
            try {
                const data = await fetchImportRow(drawerContext.importId, drawerContext.rowId);
                if (!isActive) return;
                setDrawerRow(data);
            } catch (error) {
                if (!isActive) return;
                setDrawerError(error instanceof Error ? error.message : "Failed to load row details.");
            } finally {
                if (isActive) {
                    setDrawerLoading(false);
                }
            }
        };

        loadRow();

        return () => {
            isActive = false;
        };
    }, [drawerContext]);

    useEffect(() => {
        if (!selectedFile) {
            setPreviewing(false);
            return;
        }

        let isActive = true;
        const runPreview = async () => {
            setPreviewing(true);
            setPreviewError(null);
            setPreviewStats(null);
            try {
                const result = await previewImport(selectedFile);
                if (!isActive) return;
                setPreviewStats(result.stats);
            } catch (error) {
                if (!isActive) return;
                setPreviewError(error instanceof Error ? error.message : "Failed to preview import.");
            } finally {
                if (isActive) {
                    setPreviewing(false);
                }
            }
        };

        runPreview();

        return () => {
            isActive = false;
        };
    }, [selectedFile]);
    const handleImportToggle = (importItem: ImportSummary) => {
        const isExpanded = expandedImportId === importItem.id;
        if (isExpanded) {
            setExpandedImportId(null);
            setHasAutoExpanded(true);
            navigate("/imports");
            return;
        }

        setExpandedImportId(importItem.id);
        setHasAutoExpanded(true);
        setRowsFilter("all");
        setRowsPage(1);
        navigate(`/imports/${importItem.id}`);
    };

    const handleViewImport = (importIdToOpen: number) => {
        setExpandedImportId(importIdToOpen);
        setHasAutoExpanded(true);
        setRowsFilter("all");
        setRowsPage(1);
        setActiveTab("import-history");
        navigate(`/imports/${importIdToOpen}`);
    };

    const handleFileDrop = (files: FileList) => {
        const file = files.item(0);
        if (file) {
            setSelectedFile(file);
            setPreviewStats(null);
            setPreviewError(null);
            setConfirmError(null);
            setConfirmSuccess(false);
            setLastImportId(null);
        }
    };

    const handleConfirmImport = async () => {
        if (!selectedFile || !previewStats) {
            setConfirmError("Select a CSV file and wait for the preview before confirming.");
            return;
        }

        setConfirming(true);
        setConfirmError(null);
        try {
            const result = await confirmImport(selectedFile);
            setConfirmSuccess(true);
            setLastImportId(result.import_id);

            const updatedImports = await fetchImports();
            setImports(updatedImports);

            setExpandedImportId(result.import_id);
            setHasAutoExpanded(true);
            setRowsFilter("all");
            setRowsPage(1);
            setAllRowsPage(1);
            setAllRowsRefreshKey((prev) => prev + 1);
            setActiveTab("import-history");
            navigate(`/imports/${result.import_id}`);
        } catch (error) {
            setConfirmError(error instanceof Error ? error.message : "Failed to confirm import.");
        } finally {
            setConfirming(false);
        }
    };

    const handleClear = () => {
        setSelectedFile(null);
        setPreviewStats(null);
        setPreviewError(null);
        setPreviewing(false);
        setConfirmError(null);
        setConfirmSuccess(false);
        setLastImportId(null);
    };
    const handleDrawerClose = () => {
        setDrawerContext(null);
        setDrawerRow(null);
    };

    const handleAllRowsSortChange = (descriptor: SortDescriptor) => {
        const column = String(descriptor.column) as AllRowsColumnId;
        if (column !== "date_val" && column !== "amount") {
            return;
        }
        setAllRowsSort(column);
        setAllRowsSortDirection(descriptor.direction);
        setAllRowsPage(1);
    };

    const importRowsTotalPages = Math.max(1, Math.ceil(rowsTotal / importRowsLimit));
    const allRowsTotalPages = Math.max(1, Math.ceil(allRowsTotal / allRowsLimit));
    const canConfirm = Boolean(selectedFile && previewStats && !previewing && !confirming && !confirmSuccess);
    const fileProgress = previewStats ? 100 : 45;
    const allRowsSortDescriptor: SortDescriptor | undefined = allRowsSort
        ? { column: allRowsSort, direction: allRowsSortDirection }
        : undefined;
    const showAllTransactionsNoImportsEmptyState = !importsLoading && !importsError && imports.length === 0;

    return (
        <section className="flex flex-1 flex-col gap-8">
            <header className="flex flex-col gap-2">
                <h1 className="text-2xl font-semibold text-primary">Import</h1>
                <p className="text-sm text-tertiary">
                    Upload CSV exports to store raw rows, dedupe overlapping imports, and create canonical transactions.
                </p>
            </header>

            <FileUpload.DropZone
                className="rounded-2xl bg-primary p-6 shadow-xs ring-1 ring-secondary flex flex-col gap-6 items-stretch"
                accept=".csv,text/csv"
                allowsMultiple={false}
                onDropFiles={handleFileDrop}
                isDisabled={confirming}
            >
                {({ openFileDialog }) => (
                    <>
                        <div className="flex flex-col items-center text-center gap-3">
                            <ButtonUtility
                                icon={<UploadCloud02 className="size-10 text-tertiary" />}
                                color="secondary"
                                tooltip="Upload CSV"
                                onClick={openFileDialog}
                                className="rounded-2xl p-4 ring-1 ring-secondary bg-primary/40 hover:bg-primary/60 transition"
                            />
                            <Button className="px-0" color="link-color" size="lg" onClick={openFileDialog}>
                                Drag & drop your CSV here
                            </Button>                            
                            <p className="text-sm text-tertiary max-w-md">
                                Single account per file. Supports tabs or commas. Follows French decimals.
                            </p>

                            <p className="text-xs text-tertiary max-w-md">
                                CSV files with dateOp, dateVal, label, amount, supplierFound, accountNum.
                            </p>
                        </div>

                        {selectedFile && (
                            <div className="w-full">
                                <FileUpload.List>
                                    <FileUpload.ListItemProgressBar
                                        name={selectedFile.name}
                                        size={selectedFile.size}
                                        progress={fileProgress}
                                        type="csv"
                                        onDelete={handleClear}
                                        completeLabel="File ready"
                                        inProgressLabel="Parsing..."
                                    />
                                </FileUpload.List>
                            </div>
                        )}

                        {previewStats && !confirmSuccess && (
                            <div className="w-full">
                                <PreviewStatsGrid stats={previewStats} />
                            </div>
                        )}

                        <div className="w-full flex flex-col gap-3">
                            <div className="flex flex-wrap items-center gap-3 justify-center">
                                <DemoGuard>
                                <Button
                                    iconLeading={FilePlus02}
                                    size="md"
                                    color="primary"
                                    isLoading={confirming}
                                    isDisabled={!canConfirm}
                                    onClick={handleConfirmImport}
                                >
                                    Confirm import
                                </Button>
                                </DemoGuard>
                                <Button
                                    iconLeading={UploadCloud02}
                                    size="md"
                                    color="secondary"
                                    isDisabled={confirming}
                                    onClick={handleClear}
                                >
                                    Clear
                                </Button>
                            </div>
                            {previewError && <span className="text-sm text-error-primary">{previewError}</span>}
                            {confirmError && <span className="text-sm text-error-primary">{confirmError}</span>}
                            {confirmSuccess && (
                                <div className="flex flex-wrap items-center gap-3 text-sm font-medium text-success-primary">
                                    <FileCheck02 className="size-4 text-success-primary" />
                                    <span>Import confirmed. Review it in the imports history below.</span>
                                    {lastImportId !== null && (
                                        <Button size="sm" color="secondary" onClick={() => handleViewImport(lastImportId)}>
                                            View import
                                        </Button>
                                    )}
                                </div>
                            )}
                        </div>
                    </>
                )}
            </FileUpload.DropZone>
            <SectionDivider />
            <Tabs
                selectedKey={activeTab}
                onSelectionChange={(key) => setActiveTab(key as ImportTabId)}
                className="flex flex-col gap-6"
            >
                <Tabs.List aria-label="Import history tabs" size="sm" type="button-border" items={IMPORT_TABS} className="w-fit">
                    {(item) => <Tabs.Item id={item.id}>{item.label}</Tabs.Item>}
                </Tabs.List>
                <Tabs.Panel id="import-history">
                    <section className="flex flex-col gap-4">
                    {importsLoading ? (
                        <div className="flex justify-center py-10">
                            <LoadingIndicator label="Loading imports..." />
                        </div>
                    ) : importsError ? (
                        <div className="rounded-xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                            {importsError}
                        </div>
                    ) : imports.length === 0 ? (
                        <EmptyState>
                            <EmptyState.Header>
                                <EmptyState.FeaturedIcon icon={UploadCloud02} color="brand" />
                            </EmptyState.Header>
                            <EmptyState.Content>
                                <EmptyState.Title>No imports yet</EmptyState.Title>
                                <EmptyState.Description>
                                    Upload a CSV file with the expected BoursoBank-like columns to populate your history.
                                </EmptyState.Description>
                            </EmptyState.Content>
                        </EmptyState>
                    ) : (
                        <TableCard.Root>
                            <TableCard.Header title="Imports history" description="Click an import to review results." />
                                <div className="hidden grid-cols-[minmax(0,0.8fr)_minmax(0,1.4fr)_minmax(0,1.1fr)_minmax(0,1fr)_auto] gap-4 border-b border-secondary px-6 py-3 text-xs font-semibold text-quaternary lg:grid">
                                    <span>Imported at</span>
                                    <span>File name</span>
                                    <span>Account</span>
                                    <span>Stats</span>
                                    <span aria-hidden="true" />
                                </div>
                            <div className="divide-y divide-secondary">
                                {imports.map((item) => {
                                    const isExpanded = expandedImportId === item.id;
                                    const panelId = `import-${item.id}-panel`;
                                    return (
                                        <div key={item.id} className="px-6 py-4">
                                            <button
                                                type="button"
                                                className={cx(
                                                    "outline-focus-ring w-full rounded-xl px-2 py-2 text-left transition-colors hover:bg-secondary",
                                                    isExpanded && "bg-secondary",
                                                )}
                                                onClick={() => handleImportToggle(item)}
                                                aria-expanded={isExpanded}
                                                aria-controls={panelId}
                                            >
                                                <div className="flex items-center gap-4">
                                                    <div className="grid flex-1 gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.4fr)_minmax(0,1.1fr)_minmax(0,1fr)]">
                                                        <div className="text-sm text-secondary">
                                                            {formatDateTime(item.imported_at)}
                                                        </div>
                                                        <div className="flex flex-col">
                                                            <span className="text-sm font-medium text-secondary">{item.file_name}</span>
                                                            <span className="text-xs text-tertiary">
                                                                Hash {truncateHash(item.file_hash)}
                                                            </span>
                                                        </div>
                                                        <div className="flex flex-col">
                                                            <span className="text-sm font-medium text-secondary">
                                                                {item.account?.label ?? "Unknown"}
                                                            </span>
                                                            <span className="text-xs text-tertiary">
                                                                {item.account?.account_num ?? "-"}
                                                            </span>
                                                        </div>
                                                        <StatsInline stats={item.stats} />
                                                    </div>
                                                    <ChevronDown
                                                        className={cx(
                                                            "size-4 text-tertiary transition-transform",
                                                            isExpanded && "rotate-180",
                                                        )}
                                                    />
                                                </div>
                                            </button>

                                            {isExpanded && (
                                                <div id={panelId} className="mt-4 flex flex-col gap-6">
                                                    <div className="flex flex-wrap items-center gap-2">
                                                        <FilterButton
                                                            active={rowsFilter === "all"}
                                                            label="All rows"
                                                            onClick={() => {
                                                                setRowsFilter("all");
                                                                setRowsPage(1);
                                                            }}
                                                        />
                                                        <FilterButton
                                                            active={rowsFilter === "unlinked"}
                                                            label="Unlinked"
                                                            onClick={() => {
                                                                setRowsFilter("unlinked");
                                                                setRowsPage(1);
                                                            }}
                                                        />
                                                        <FilterButton
                                                            active={rowsFilter === "errors"}
                                                            label="Errors"
                                                            onClick={() => {
                                                                setRowsFilter("errors");
                                                                setRowsPage(1);
                                                            }}
                                                        />
                                                    </div>

                                                    <TableCard.Root>
                                                        <TableCard.Header
                                                            title="Import rows"
                                                            description="Rows created, linked, or failed during import."
                                                            contentTrailing={
                                                                <RowsPerPageSelect
                                                                    value={importRowsLimit}
                                                                    onChange={(value) => {
                                                                        setImportRowsLimit(value);
                                                                        setRowsPage(1);
                                                                    }}
                                                                />
                                                            }
                                                        />
                                                        {rowsLoading ? (
                                                            <div className="flex justify-center py-10">
                                                                <LoadingIndicator label="Loading rows..." />
                                                            </div>
                                                        ) : rowsError ? (
                                                            <div className="rounded-xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                                                                {rowsError}
                                                            </div>
                                                        ) : (
                                                            <>
                                                                <Table aria-label={`Import rows for ${item.file_name}`}>
                                                                    <Table.Header columns={IMPORT_ROWS_COLUMNS}>
                                                                        {(column) => (
                                                                            <Table.Head>
                                                                                <span className="text-xs font-semibold text-secondary">
                                                                                    {column.name}
                                                                                </span>
                                                                            </Table.Head>
                                                                        )}
                                                                    </Table.Header>
                                                                    <Table.Body items={rows}>
                                                                        {(row) => (
                                                                            <Table.Row
                                                                                id={row.id}
                                                                                columns={IMPORT_ROWS_COLUMNS}
                                                                                className="cursor-pointer"
                                                                                onAction={() =>
                                                                                    setDrawerContext({
                                                                                        importId: item.id,
                                                                                        rowId: row.id,
                                                                                    })
                                                                                }
                                                                            >
                                                                                {(column) => {
                                                                                    const columnId = column.id as ImportRowsColumnId;
                                                                                    return (
                                                                                        <Table.Cell>
                                                                                            {columnId === "date_val" && (
                                                                                                <span className="text-sm text-primary">
                                                                                                    {formatDate(row.date_val)}
                                                                                                </span>
                                                                                            )}
                                                                                            {columnId === "label" && (
                                                                                                <div className="flex flex-col gap-1">
                                                                                                    <span className="text-sm font-medium text-primary">
                                                                                                        {row.label_raw || "Untitled"}
                                                                                                    </span>
                                                                                                    <RowStatusBadge status={row.status} />
                                                                                                </div>
                                                                                            )}
                                                                                            {columnId === "supplier" && (
                                                                                                <span className="text-sm text-primary">
                                                                                                    {row.supplier_raw || "-"}
                                                                                                </span>
                                                                                            )}
                                                                                            {columnId === "amount" && (
                                                                                                <span
                                                                                                    className={cx(
                                                                                                        "text-sm font-semibold",
                                                                                                        amountClass(row.amount),
                                                                                                    )}
                                                                                                >
                                                                                                    {formatAmount(row.amount)}
                                                                                                </span>
                                                                                            )}
                                                                                            {columnId === "category" && (
                                                                                                <span className="text-sm text-primary">
                                                                                                    {row.category_raw || "-"}
                                                                                                </span>
                                                                                            )}
                                                                                            {columnId === "transaction" && (
                                                                                                <span className="text-sm text-primary">
                                                                                                    {row.transaction_id ? `#${row.transaction_id}` : "-"}
                                                                                                </span>
                                                                                            )}
                                                                                        </Table.Cell>
                                                                                    );
                                                                                }}
                                                                            </Table.Row>
                                                                        )}
                                                                    </Table.Body>
                                                                </Table>
                                                                {rows.length === 0 ? (
                                                                    <div className="px-6 py-10 text-sm text-tertiary">
                                                                        No rows found for this import.
                                                                    </div>
                                                                ) : (
                                                                    <PaginationCardMinimal
                                                                        page={rowsPage}
                                                                        total={importRowsTotalPages}
                                                                        onPageChange={(page) => setRowsPage(Math.max(1, page))}
                                                                    />
                                                                )}
                                                            </>
                                                        )}
                                                    </TableCard.Root>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        </TableCard.Root>
                    )}
                </section>
                </Tabs.Panel>

                <Tabs.Panel id="all-transactions">
                    <section className="flex flex-col gap-4">
                        {showAllTransactionsNoImportsEmptyState ? (
                            <EmptyState>
                                <EmptyState.Header>
                                    <EmptyState.FeaturedIcon icon={UploadCloud02} color="brand" />
                                </EmptyState.Header>
                                <EmptyState.Content>
                                    <EmptyState.Title>No transactions yet</EmptyState.Title>
                                    <EmptyState.Description>
                                        Import a CSV file to populate transactions across all imports.
                                    </EmptyState.Description>
                                </EmptyState.Content>
                            </EmptyState>
                        ) : (
                            <TableCard.Root>
                                <TableCard.Header
                                    title="All transactions"
                                    description="Browse rows across every import."
                                    contentTrailing={
                                        <RowsPerPageSelect
                                            value={allRowsLimit}
                                            onChange={(value) => {
                                                setAllRowsLimit(value);
                                                setAllRowsPage(1);
                                            }}
                                        />
                                    }
                                />
                                <div className="flex flex-col gap-4 border-b border-secondary px-6 py-4">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <FilterButton
                                            active={allRowsFilter === "all"}
                                            label="All rows"
                                            onClick={() => {
                                                setAllRowsFilter("all");
                                                setAllRowsPage(1);
                                            }}
                                        />
                                        <FilterButton
                                            active={allRowsFilter === "unlinked"}
                                            label="Unlinked"
                                            onClick={() => {
                                                setAllRowsFilter("unlinked");
                                                setAllRowsPage(1);
                                            }}
                                        />
                                        <FilterButton
                                            active={allRowsFilter === "errors"}
                                            label="Errors"
                                            onClick={() => {
                                                setAllRowsFilter("errors");
                                                setAllRowsPage(1);
                                            }}
                                        />
                                    </div>
                                    <div className="flex flex-wrap items-center gap-3">
                                        <Input
                                            size="md"
                                            placeholder="Search label or supplier"
                                            icon={SearchLg}
                                            value={allRowsSearch}
                                            onChange={(value) => {
                                                setAllRowsSearch(value);
                                                setAllRowsPage(1);
                                            }}
                                            className="w-full md:max-w-xs"
                                        />
                                        <DateRangePicker
                                            value={allRowsDateRangeDraft}
                                            onChange={setAllRowsDateRangeDraft}
                                            onApply={() => {
                                                setAllRowsDateRangeApplied(allRowsDateRangeDraft);
                                                setAllRowsPage(1);
                                            }}
                                            onCancel={() => {
                                                setAllRowsDateRangeDraft(allRowsDateRangeApplied);
                                            }}
                                        />
                                    </div>
                                </div>
                                {allRowsLoading ? (
                                    <div className="flex justify-center py-10">
                                        <LoadingIndicator label="Loading transactions..." />
                                    </div>
                                ) : allRowsError ? (
                                    <div className="rounded-xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                                        {allRowsError}
                                    </div>
                                ) : (
                                    <>
                                        <Table
                                            aria-label="All transactions"
                                            sortDescriptor={allRowsSortDescriptor}
                                            onSortChange={handleAllRowsSortChange}
                                        >
                                            <Table.Header columns={ALL_ROWS_COLUMNS}>
                                                {(column) => {
                                                    const columnId = column.id as AllRowsColumnId;
                                                    const allowsSorting = columnId === "date_val" || columnId === "amount";
                                                    return (
                                                        <Table.Head allowsSorting={allowsSorting}>
                                                            <span className="text-xs font-semibold text-secondary">{column.name}</span>
                                                        </Table.Head>
                                                    );
                                                }}
                                            </Table.Header>
                                            <Table.Body items={allRows}>
                                                {(row) => (
                                                    <Table.Row
                                                        id={`${row.import_id}-${row.id}`}
                                                        columns={ALL_ROWS_COLUMNS}
                                                        className="cursor-pointer"
                                                        onAction={() =>
                                                            setDrawerContext({
                                                                importId: row.import_id,
                                                                rowId: row.id,
                                                            })
                                                        }
                                                    >
                                                        {(column) => {
                                                            const columnId = column.id as AllRowsColumnId;
                                                            const importHash = importsById.get(row.import_id)?.file_hash;
                                                            return (
                                                                <Table.Cell>
                                                                    {columnId === "import" && (
                                                                        <div className="flex flex-col">
                                                                            <span className="text-sm font-medium text-secondary">
                                                                                {row.file_name}
                                                                            </span>
                                                                            <span className="text-xs text-tertiary">
                                                                                Hash {importHash ? truncateHash(importHash) : "-"}
                                                                            </span>
                                                                        </div>
                                                                    )}
                                                                    {columnId === "imported_at" && (
                                                                        <span className="text-sm text-primary">
                                                                            {formatDateTime(row.imported_at)}
                                                                        </span>
                                                                    )}
                                                                    {columnId === "account" && (
                                                                        <div className="flex flex-col">
                                                                            <span className="text-sm font-medium text-secondary">
                                                                                {row.account?.label ?? "Unknown"}
                                                                            </span>
                                                                            <span className="text-xs text-tertiary">
                                                                                {row.account?.account_num ?? "-"}
                                                                            </span>
                                                                        </div>
                                                                    )}
                                                                    {columnId === "date_val" && (
                                                                        <span className="text-sm text-primary">{formatDate(row.date_val)}</span>
                                                                    )}
                                                                    {columnId === "label" && (
                                                                        <div className="flex flex-col gap-1">
                                                                            <span className="text-sm font-medium text-primary">
                                                                                {row.label_raw || "Untitled"}
                                                                            </span>
                                                                            <RowStatusBadge status={row.status} />
                                                                        </div>
                                                                    )}
                                                                    {columnId === "supplier" && (
                                                                        <span className="text-sm text-primary">{row.supplier_raw || "-"}</span>
                                                                    )}
                                                                    {columnId === "amount" && (
                                                                        <span className={cx("text-sm font-semibold", amountClass(row.amount))}>
                                                                            {formatAmount(row.amount)}
                                                                        </span>
                                                                    )}
                                                                    {columnId === "category" && (
                                                                        <span className="text-sm text-primary">{row.category_raw || "-"}</span>
                                                                    )}
                                                                    {columnId === "transaction" && (
                                                                        <span className="text-sm text-primary">
                                                                            {row.transaction_id ? `#${row.transaction_id}` : "-"}
                                                                        </span>
                                                                    )}
                                                                </Table.Cell>
                                                            );
                                                        }}
                                                    </Table.Row>
                                                )}
                                            </Table.Body>
                                        </Table>
                                        {allRows.length === 0 ? (
                                            <div className="px-6 py-10 text-sm text-tertiary">No transactions found.</div>
                                        ) : (
                                            <PaginationCardMinimal
                                                page={allRowsPage}
                                                total={allRowsTotalPages}
                                                onPageChange={(page) => setAllRowsPage(Math.max(1, page))}
                                            />
                                        )}
                                    </>
                                )}
                            </TableCard.Root>
                        )}
                    </section>
                </Tabs.Panel>
            </Tabs>

            <SlideoutMenu isOpen={drawerContext !== null} onOpenChange={(open) => (!open ? handleDrawerClose() : null)}>
                {({ close }) => (
                    <>
                        <SlideoutMenu.Header onClose={close}>
                            <div className="flex flex-col gap-2">
                                <h3 className="text-lg font-semibold text-primary">Row detail</h3>
                                <p className="text-sm text-tertiary">Inspect raw data and normalization results.</p>
                            </div>
                        </SlideoutMenu.Header>
                        <SlideoutMenu.Content>
                            {drawerLoading ? (
                                <div className="flex justify-center py-10">
                                    <LoadingIndicator label="Loading row..." />
                                </div>
                            ) : drawerError ? (
                                <div className="rounded-xl border border-error-subtle bg-error-primary/10 p-4 text-sm text-error-primary">
                                    {drawerError}
                                </div>
                            ) : drawerRow ? (
                                <div className="flex flex-col gap-6">
                                    <div className="rounded-xl bg-secondary p-4">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-sm font-medium text-secondary">
                                                {drawerRow.label_raw || "Untitled"}
                                            </span>
                                            <RowStatusBadge status={drawerRow.status} />
                                            {drawerRow.error_message && (
                                                <span className="text-sm text-error-primary">{drawerRow.error_message}</span>
                                            )}
                                        </div>
                                    </div>

                                    <SectionCard title="Normalization preview">
                                        <div className="grid gap-3 text-sm text-tertiary">
                                            <div>
                                                <span className="text-xs text-quaternary">Label normalized</span>
                                                <div className="text-sm font-medium text-secondary">
                                                    {drawerRow.normalization_preview?.label_norm || "-"}
                                                </div>
                                            </div>
                                            <div>
                                                <span className="text-xs text-quaternary">Inferred type</span>
                                                <div className="text-sm font-medium text-secondary">
                                                    {drawerRow.normalization_preview?.inferred_type || "-"}
                                                </div>
                                            </div>
                                            <div>
                                                <span className="text-xs text-quaternary">Inferred payee</span>
                                                <div className="text-sm font-medium text-secondary">
                                                    {drawerRow.normalization_preview?.inferred_payee || "-"}
                                                </div>
                                            </div>
                                        </div>
                                    </SectionCard>

                                    <SectionCard title="Linked transaction">
                                        {drawerRow.transaction ? (
                                            <div className="flex flex-col gap-2 text-sm text-tertiary">
                                                <div className="flex items-center justify-between">
                                                    <span className="text-sm font-medium text-secondary">
                                                        #{drawerRow.transaction.id} - {drawerRow.transaction.label_raw}
                                                    </span>
                                                    <Badge size="sm" color="gray">
                                                        {drawerRow.transaction.type}
                                                    </Badge>
                                                </div>
                                                <div className="flex items-center justify-between">
                                                    <span>{formatDate(drawerRow.transaction.posted_at)}</span>
                                                    <span className={cx("font-semibold", amountClass(drawerRow.transaction.amount))}>
                                                        {formatAmount(drawerRow.transaction.amount)}
                                                    </span>
                                                </div>
                                            </div>
                                        ) : (
                                            <span className="text-sm text-tertiary">No transaction linked.</span>
                                        )}
                                    </SectionCard>

                                    <SectionCard title="Raw JSON">
                                        <pre className="max-h-72 overflow-auto rounded-lg bg-primary p-3 text-xs text-tertiary ring-1 ring-secondary">
                                            {JSON.stringify(drawerRow.raw_json, null, 2)}
                                        </pre>
                                    </SectionCard>
                                </div>
                            ) : (
                                <span className="text-sm text-tertiary">Select a row to see details.</span>
                            )}
                        </SlideoutMenu.Content>
                    </>
                )}
            </SlideoutMenu>
        </section>
    );
};

const RowsPerPageSelect = ({ value, onChange }: { value: number; onChange: (value: number) => void }) => {
    return (
        <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-tertiary">Rows per page</span>
            <Select
                aria-label="Rows per page"
                size="sm"
                items={ROWS_PER_PAGE_OPTIONS}
                selectedKey={String(value)}
                onSelectionChange={(key) => {
                    if (!key) return;
                    const next = Number(key);
                    if (!Number.isNaN(next)) {
                        onChange(next);
                    }
                }}
                className="min-w-[100px]"
            >
                {(item) => <Select.Item id={item.id} label={item.label} />}
            </Select>
        </div>
    );
};

const StatsInline = ({ stats }: { stats: ImportStats }) => {
    return (
        <div className="flex flex-wrap gap-2 text-xs text-tertiary">
            <span>Created {stats.created_count}</span>
            <span>Linked {stats.linked_count}</span>
            <span>Dupes {stats.duplicate_count}</span>
            <span>Errors {stats.error_count}</span>
        </div>
    );
};

const PreviewStatsGrid = ({ stats }: { stats: ImportStats }) => {
    const items = [
        { label: "Rows", value: stats.row_count },
        { label: "Created", value: stats.created_count },
        { label: "Linked", value: stats.linked_count },
        { label: "Duplicates", value: stats.duplicate_count },
        { label: "Errors", value: stats.error_count },
    ];

    return (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {items.map((item) => (
                <div key={item.label} className="rounded-xl bg-primary p-4 ring-1 ring-secondary">
                    <span className="text-xs text-tertiary">{item.label}</span>
                    <div className="text-lg font-semibold text-primary">{item.value}</div>
                </div>
            ))}
        </div>
    );
};

const RowStatusBadge = ({ status }: { status: ImportRowSummary["status"] }) => {
    const color = status === "error" ? "error" : status === "linked" ? "blue" : "success";
    const label = status === "error" ? "Error" : status === "linked" ? "Linked" : "Created";
    return (
        <Badge size="sm" color={color}>
            {label}
        </Badge>
    );
};

const FilterButton = ({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) => {
    return (
        <Button size="sm" color={active ? "secondary" : "tertiary"} onClick={onClick}>
            {label}
        </Button>
    );
};

const SectionCard = ({ title, children }: { title: string; children: ReactNode }) => {
    return (
        <div className="rounded-xl bg-primary p-4 ring-1 ring-secondary">
            <h4 className="text-sm font-semibold text-secondary">{title}</h4>
            <div className="mt-3">{children}</div>
        </div>
    );
};

const formatDate = (value?: string | null) => {
    if (!value) return "-";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString("fr-FR");
};

const formatDateTime = (value?: string | null) => {
    if (!value) return "-";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
};

const formatAmount = (value?: string | number | null) => {
    if (value === null || value === undefined || value === "") return "-";
    const numberValue = typeof value === "number" ? value : Number(value);
    if (Number.isNaN(numberValue)) return String(value);
    return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(numberValue);
};

const amountClass = (value?: string | number | null) => {
    const numberValue = typeof value === "number" ? value : Number(value);
    if (Number.isNaN(numberValue) || numberValue === 0) return "text-tertiary";
    return numberValue < 0 ? "text-error-primary" : "text-success-primary";
};

const truncateHash = (hash?: string | null) => {
    if (!hash) return "-";
    return `${hash.slice(0, 8)}...`;
};

const getStatusParam = (filter: RowsFilter) => {
    if (filter === "unlinked") return "created";
    if (filter === "errors") return "error";
    return undefined;
};

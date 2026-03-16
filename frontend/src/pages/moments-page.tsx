import { type ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { parseDate } from "@internationalized/date";
import { DatePicker } from "@/components/application/date-picker/date-picker";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Button } from "@/components/base/buttons/button";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";
import { TextArea } from "@/components/base/textarea/textarea";
import { MomentCandidatesTable, MomentOverlay, MomentsBulkActionBar, MomentsList, MomentTaggedTable, type MomentOverlayTab } from "@/components/moments";
import { ApiError } from "@/services/api";
import { getDefaultMomentCoverDataUri } from "@/utils/moment-cover-defaults";
import { formatAmount } from "@/utils/format";
import {
    createMoment,
    decideMomentCandidates,
    deleteMoment,
    fetchMomentCandidates,
    fetchMoments,
    fetchMomentTaggedSplits,
    getApiErrorCode,
    moveMomentTaggedSplits,
    refreshMomentCandidates,
    removeMomentTaggedSplits,
    updateMoment,
    type Moment,
    type MomentCandidateRow,
    type MomentCandidateStatus,
    type MomentTaggedSplitRow,
} from "@/services/moments";

const PAGE_SIZE = 20;
const REASSIGN_CONFIRM_TEXT = "One or more splits are already assigned to another moment. Confirm reassignment?";
const MOMENT_COVER_UPLOAD_ACCEPT = "image/png,image/jpeg,image/jpg,image/webp";
const MOMENT_COVER_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024;
const MOMENT_COVER_ALLOWED_FILE_TYPES = new Set(["image/png", "image/jpeg", "image/jpg", "image/webp"]);

type CandidateStatusFilter = "all" | MomentCandidateStatus;
type CandidateDecision = "accepted" | "rejected";

type CreateMomentDraft = {
    name: string;
    startDate: string;
    endDate: string;
    description: string;
};

type ReassignConfirmState =
    | {
          kind: "tagged-move";
          splitIds: number[];
          targetMomentId: number;
      }
    | {
          kind: "candidates-accept";
          splitIds: number[];
      }
    | null;

const DEFAULT_CREATE_DRAFT: CreateMomentDraft = {
    name: "",
    startDate: "",
    endDate: "",
    description: "",
};

const CANDIDATE_STATUS_OPTIONS: { id: CandidateStatusFilter; label: string }[] = [
    { id: "all", label: "All statuses" },
    { id: "pending", label: "Pending" },
    { id: "accepted", label: "Accepted" },
    { id: "rejected", label: "Rejected" },
];

const getErrorMessage = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

const toISODate = (d: Date) => d.toISOString().slice(0, 10);

const DATE_SHORTCUTS = [
    {
        label: "Last 7 days",
        get: () => {
            const end = new Date();
            const start = new Date();
            start.setDate(end.getDate() - 6);
            return { startDate: toISODate(start), endDate: toISODate(end) };
        },
    },
    {
        label: "Last 30 days",
        get: () => {
            const end = new Date();
            const start = new Date();
            start.setDate(end.getDate() - 29);
            return { startDate: toISODate(start), endDate: toISODate(end) };
        },
    },
    {
        label: "This month",
        get: () => {
            const now = new Date();
            const start = new Date(now.getFullYear(), now.getMonth(), 1);
            return { startDate: toISODate(start), endDate: toISODate(now) };
        },
    },
];

const toIds = (keys: Set<string>) =>
    Array.from(keys)
        .map((value) => Number(value))
        .filter((value) => Number.isFinite(value));

const toTotalPages = (total: number) => Math.max(1, Math.ceil(total / PAGE_SIZE));

const toDateValue = (value: string) => {
    if (!value) return null;
    try {
        return parseDate(value);
    } catch {
        return null;
    }
};

const getCreateValidationError = (draft: CreateMomentDraft): string | null => {
    if (!draft.name.trim()) return "Name is required.";
    if (!draft.startDate || !draft.endDate) return "Start and end dates are required.";
    if (draft.startDate > draft.endDate) return "Start date must be on or before end date.";
    return null;
};

const mapCreateError = (error: unknown): string => {
    const code = getApiErrorCode(error);
    if (code === "MOMENT_NAME_REQUIRED") return "Name is required.";
    if (code === "MOMENT_INVALID_DATE_RANGE") return "Start date must be on or before end date.";
    if (error instanceof ApiError && error.status === 422) {
        return error.message || "Failed to create moment.";
    }
    return getErrorMessage(error, "Failed to create moment.");
};

const getMomentCoverFileValidationError = (file: File): string | null => {
    const fileType = file.type.toLowerCase();
    if (!MOMENT_COVER_ALLOWED_FILE_TYPES.has(fileType)) {
        return "Unsupported image format. Use PNG, JPG, JPEG, or WebP.";
    }
    if (file.size > MOMENT_COVER_MAX_FILE_SIZE_BYTES) {
        return "Image must be 5MB or smaller.";
    }
    return null;
};

export const MomentsPage = () => {
    const navigate = useNavigate();
    const coverFileInputRef = useRef<HTMLInputElement>(null);

    const [moments, setMoments] = useState<Moment[]>([]);
    const [momentsLoading, setMomentsLoading] = useState(true);
    const [momentsError, setMomentsError] = useState<string | null>(null);

    const [overlayOpen, setOverlayOpen] = useState(false);
    const [selectedMomentId, setSelectedMomentId] = useState<number | null>(null);
    const [activeTab, setActiveTab] = useState<MomentOverlayTab>("tagged");

    const [createOpen, setCreateOpen] = useState(false);
    const [createDraft, setCreateDraft] = useState<CreateMomentDraft>(DEFAULT_CREATE_DRAFT);
    const [createError, setCreateError] = useState<string | null>(null);
    const [createSaving, setCreateSaving] = useState(false);

    const [taggedRows, setTaggedRows] = useState<MomentTaggedSplitRow[]>([]);
    const [taggedTotal, setTaggedTotal] = useState(0);
    const [taggedPage, setTaggedPage] = useState(1);
    const [taggedQuery, setTaggedQuery] = useState("");
    const [taggedLoading, setTaggedLoading] = useState(false);
    const [taggedError, setTaggedError] = useState<string | null>(null);
    const [taggedSelection, setTaggedSelection] = useState<Set<string>>(new Set());
    const [taggedMoveTargetMomentId, setTaggedMoveTargetMomentId] = useState("none");

    const [candidateRows, setCandidateRows] = useState<MomentCandidateRow[]>([]);
    const [candidatesTotal, setCandidatesTotal] = useState(0);
    const [candidatesPage, setCandidatesPage] = useState(1);
    const [candidateStatusFilter, setCandidateStatusFilter] = useState<CandidateStatusFilter>("pending");
    const [candidatesLoading, setCandidatesLoading] = useState(false);
    const [candidatesError, setCandidatesError] = useState<string | null>(null);
    const [candidatesSelection, setCandidatesSelection] = useState<Set<string>>(new Set());
    const [candidatesRefreshing, setCandidatesRefreshing] = useState(false);

    const [pendingBulkAction, setPendingBulkAction] = useState<string | null>(null);
    const [bulkError, setBulkError] = useState<string | null>(null);
    const [bulkNotice, setBulkNotice] = useState<string | null>(null);
    const [reassignConfirmState, setReassignConfirmState] = useState<ReassignConfirmState>(null);

    const [editOpen, setEditOpen] = useState(false);
    const [editDraft, setEditDraft] = useState<CreateMomentDraft>(DEFAULT_CREATE_DRAFT);
    const [editError, setEditError] = useState<string | null>(null);
    const [editSaving, setEditSaving] = useState(false);

    const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);
    const [deleteDeleting, setDeleteDeleting] = useState(false);
    const [coverImageSaving, setCoverImageSaving] = useState(false);
    const [coverImageError, setCoverImageError] = useState<string | null>(null);

    const createValidationError = useMemo(() => getCreateValidationError(createDraft), [createDraft]);

    const selectedMoment = useMemo(
        () => moments.find((moment) => moment.id === selectedMomentId) ?? null,
        [moments, selectedMomentId],
    );
    const replaceMomentInState = useCallback((updated: Moment) => {
        setMoments((previous) => previous.map((moment) => (moment.id === updated.id ? updated : moment)));
    }, []);
    const isTrueEmptyState = !momentsLoading && !momentsError && moments.length === 0;

    const moveTargetOptions = useMemo(
        () => [
            { id: "none", label: "Select target moment" },
            ...moments.filter((moment) => moment.id !== selectedMomentId).map((moment) => ({ id: String(moment.id), label: moment.name })),
        ],
        [moments, selectedMomentId],
    );

    const createStartDateValue = useMemo(() => toDateValue(createDraft.startDate), [createDraft.startDate]);
    const createEndDateValue = useMemo(() => toDateValue(createDraft.endDate), [createDraft.endDate]);

    const reassignSplitDetails = useMemo(() => {
        if (!reassignConfirmState) return [];
        const ids = new Set(reassignConfirmState.splitIds);
        const source = reassignConfirmState.kind === "candidates-accept" ? candidateRows : taggedRows;
        return source
            .filter((row) => ids.has(row.split_id))
            .map((row) => ({ label: row.label_raw, amount: row.amount, currency: row.currency }));
    }, [reassignConfirmState, candidateRows, taggedRows]);

    const editValidationError = useMemo(() => getCreateValidationError(editDraft), [editDraft]);
    const editStartDateValue = useMemo(() => toDateValue(editDraft.startDate), [editDraft.startDate]);
    const editEndDateValue = useMemo(() => toDateValue(editDraft.endDate), [editDraft.endDate]);

    const taggedSelectedAmount = useMemo(
        () => taggedRows.filter((row) => taggedSelection.has(String(row.split_id))).reduce((sum, row) => sum + Number(row.amount), 0),
        [taggedRows, taggedSelection],
    );

    const candidatesSelectedAmount = useMemo(
        () => candidateRows.filter((row) => candidatesSelection.has(String(row.split_id))).reduce((sum, row) => sum + Number(row.amount), 0),
        [candidateRows, candidatesSelection],
    );

    const loadMoments = useCallback(async () => {
        setMomentsLoading(true);
        setMomentsError(null);
        try {
            const rows = await fetchMoments({ limit: 200 });
            setMoments(rows);
        } catch (error) {
            setMomentsError(getErrorMessage(error, "Failed to load moments."));
        } finally {
            setMomentsLoading(false);
        }
    }, []);

    const loadTaggedRows = useCallback(
        async (options?: { momentId?: number; page?: number; query?: string }) => {
            const momentId = options?.momentId ?? selectedMomentId;
            if (!momentId) return;

            const page = options?.page ?? taggedPage;
            const query = options?.query ?? taggedQuery;

            setTaggedLoading(true);
            setTaggedError(null);
            try {
                const response = await fetchMomentTaggedSplits(momentId, {
                    q: query.trim() || undefined,
                    limit: PAGE_SIZE,
                    offset: (page - 1) * PAGE_SIZE,
                });
                setTaggedRows(response.rows);
                setTaggedTotal(response.total);
            } catch (error) {
                setTaggedRows([]);
                setTaggedTotal(0);
                setTaggedError(getErrorMessage(error, "Failed to load tagged rows."));
            } finally {
                setTaggedLoading(false);
            }
        },
        [selectedMomentId, taggedPage, taggedQuery],
    );

    const loadCandidateRows = useCallback(
        async (options?: { momentId?: number; page?: number; statusFilter?: CandidateStatusFilter }) => {
            const momentId = options?.momentId ?? selectedMomentId;
            if (!momentId) return;

            const page = options?.page ?? candidatesPage;
            const statusFilter = options?.statusFilter ?? candidateStatusFilter;

            setCandidatesLoading(true);
            setCandidatesError(null);
            try {
                const response = await fetchMomentCandidates(momentId, {
                    status: statusFilter === "all" ? undefined : statusFilter,
                    limit: PAGE_SIZE,
                    offset: (page - 1) * PAGE_SIZE,
                });
                setCandidateRows(response.rows);
                setCandidatesTotal(response.total);
            } catch (error) {
                setCandidateRows([]);
                setCandidatesTotal(0);
                setCandidatesError(getErrorMessage(error, "Failed to load candidate rows."));
            } finally {
                setCandidatesLoading(false);
            }
        },
        [selectedMomentId, candidatesPage, candidateStatusFilter],
    );

    useEffect(() => {
        void loadMoments();
    }, [loadMoments]);

    useEffect(() => {
        if (!overlayOpen || !selectedMomentId) return;
        if (activeTab === "tagged") {
            void loadTaggedRows();
            return;
        }
        void loadCandidateRows();
    }, [overlayOpen, selectedMomentId, activeTab, loadTaggedRows, loadCandidateRows]);

    useEffect(() => {
        setTaggedSelection(new Set());
    }, [selectedMomentId, activeTab, taggedPage, taggedQuery]);

    useEffect(() => {
        setCandidatesSelection(new Set());
    }, [selectedMomentId, activeTab, candidateStatusFilter, candidatesPage]);

    useEffect(() => {
        setTaggedMoveTargetMomentId("none");
    }, [selectedMomentId]);

    useEffect(() => {
        setCoverImageError(null);
    }, [selectedMomentId]);

    const resetCreateState = () => {
        setCreateOpen(false);
        setCreateDraft(DEFAULT_CREATE_DRAFT);
        setCreateError(null);
    };

    const handleOverlayOpenChange = (open: boolean) => {
        setOverlayOpen(open);
        if (!open) {
            setSelectedMomentId(null);
            setActiveTab("tagged");
            setBulkError(null);
            setBulkNotice(null);
            setReassignConfirmState(null);
            setCoverImageError(null);
        }
    };

    const handleOpenMoment = (momentId: number) => {
        setSelectedMomentId(momentId);
        setOverlayOpen(true);
        setActiveTab("tagged");
        setBulkError(null);
        setBulkNotice(null);
        setCoverImageError(null);
    };

    const openEditModal = () => {
        if (!selectedMoment) return;
        setEditDraft({
            name: selectedMoment.name,
            startDate: selectedMoment.start_date ?? "",
            endDate: selectedMoment.end_date ?? "",
            description: selectedMoment.description ?? "",
        });
        setEditError(null);
        setEditOpen(true);
    };

    const resetEditState = () => {
        setEditOpen(false);
        setEditDraft(DEFAULT_CREATE_DRAFT);
        setEditError(null);
    };

    const updateEditDraft = (patch: Partial<CreateMomentDraft>) => {
        setEditDraft((prev) => ({ ...prev, ...patch }));
        setEditError(null);
    };

    const handleEditMoment = async () => {
        if (editSaving || !selectedMomentId) return;

        const validationError = getCreateValidationError(editDraft);
        if (validationError) {
            setEditError(validationError);
            return;
        }

        const datesChanged =
            editDraft.startDate !== (selectedMoment?.start_date ?? "") ||
            editDraft.endDate !== (selectedMoment?.end_date ?? "");

        setEditSaving(true);
        setEditError(null);

        try {
            await updateMoment(selectedMomentId, {
                name: editDraft.name.trim(),
                start_date: editDraft.startDate,
                end_date: editDraft.endDate,
                description: editDraft.description.trim() || null,
            });
        } catch (error) {
            setEditSaving(false);
            setEditError(mapCreateError(error));
            return;
        }

        resetEditState();
        setEditSaving(false);
        await loadMoments();

        if (datesChanged) {
            try {
                const refreshResponse = await refreshMomentCandidates(selectedMomentId);
                await loadCandidateRows({ momentId: selectedMomentId });
                setBulkNotice(`Date range updated — candidates refreshed: ${refreshResponse.inserted_count} new, ${refreshResponse.touched_count} touched`);
            } catch {
                setBulkNotice("Date range updated. Refresh candidates to update results.");
            }
        }
    };

    const openCoverImagePicker = () => {
        if (!selectedMomentId || coverImageSaving) return;
        coverFileInputRef.current?.click();
    };

    const handleCoverImageUpload = (event: ChangeEvent<HTMLInputElement>) => {
        const inputElement = event.currentTarget;
        const file = inputElement.files?.[0];
        if (!file) return;

        const validationError = getMomentCoverFileValidationError(file);
        if (validationError) {
            setCoverImageError(validationError);
            inputElement.value = "";
            return;
        }

        if (!selectedMomentId) {
            inputElement.value = "";
            return;
        }

        const fileReader = new FileReader();
        fileReader.onload = () => {
            const imageDataUrl = fileReader.result;
            if (typeof imageDataUrl !== "string") {
                setCoverImageError("Could not read image file. Please try a different file.");
                return;
            }

            setCoverImageSaving(true);
            setCoverImageError(null);
            void updateMoment(selectedMomentId, {
                cover_image_url: imageDataUrl,
            })
                .then((updatedMoment) => {
                    replaceMomentInState(updatedMoment);
                    setCoverImageError(null);
                })
                .catch((error: unknown) => {
                    setCoverImageError(getErrorMessage(error, "Failed to update cover image."));
                })
                .finally(() => {
                    setCoverImageSaving(false);
                });
        };
        fileReader.onerror = () => {
            setCoverImageError("Could not read image file. Please try a different file.");
        };

        fileReader.readAsDataURL(file);
        inputElement.value = "";
    };

    const handleRemoveCoverImage = async () => {
        if (!selectedMomentId || !selectedMoment?.cover_image_url || coverImageSaving) return;

        setCoverImageSaving(true);
        setCoverImageError(null);
        try {
            const updatedMoment = await updateMoment(selectedMomentId, { cover_image_url: null });
            replaceMomentInState(updatedMoment);
        } catch (error) {
            setCoverImageError(getErrorMessage(error, "Failed to remove cover image."));
        } finally {
            setCoverImageSaving(false);
        }
    };

    const openDeleteConfirm = () => {
        setDeleteError(null);
        setDeleteConfirmOpen(true);
    };

    const handleDeleteMoment = async () => {
        if (deleteDeleting || !selectedMomentId) return;

        setDeleteDeleting(true);
        setDeleteError(null);

        try {
            await deleteMoment(selectedMomentId);
        } catch (error) {
            setDeleteDeleting(false);
            setDeleteError(getErrorMessage(error, "Failed to delete moment."));
            return;
        }

        setDeleteDeleting(false);
        setDeleteConfirmOpen(false);
        handleOverlayOpenChange(false);
        await loadMoments();
    };

    const handleOpenTransaction = (transactionId: number) => {
        void navigate(`/ledger?tx=${transactionId}`);
    };

    const handleOpenTransactionSplit = (transactionId: number) => {
        void navigate(`/ledger?tx=${transactionId}&action=split`);
    };

    const openCreateMomentModal = () => {
        setCreateOpen(true);
        setCreateError(null);
    };

    const updateCreateDraft = (patch: Partial<CreateMomentDraft>) => {
        setCreateDraft((prev) => ({ ...prev, ...patch }));
        setCreateError(null);
    };

    const handleCreateMoment = async () => {
        if (createSaving) return;

        const validationError = getCreateValidationError(createDraft);
        if (validationError) {
            setCreateError(validationError);
            return;
        }

        setCreateSaving(true);
        setCreateError(null);

        let created: Moment;
        try {
            created = await createMoment({
                name: createDraft.name.trim(),
                start_date: createDraft.startDate,
                end_date: createDraft.endDate,
                description: createDraft.description,
                cover_image_url: getDefaultMomentCoverDataUri(createDraft.name.trim(), createDraft.startDate),
            });
        } catch (error) {
            setCreateSaving(false);
            setCreateError(mapCreateError(error));
            return;
        }

        resetCreateState();

        setSelectedMomentId(created.id);
        setOverlayOpen(true);
        setActiveTab("candidates");
        setCandidateStatusFilter("pending");
        setCandidatesPage(1);
        setCandidatesSelection(new Set());
        setBulkError(null);
        setBulkNotice(null);

        try {
            await loadMoments();
            const refreshResponse = await refreshMomentCandidates(created.id);
            await loadCandidateRows({ momentId: created.id, page: 1, statusFilter: "pending" });
            setBulkNotice(`Candidates refreshed: ${refreshResponse.inserted_count} inserted, ${refreshResponse.touched_count} touched`);
        } catch (error) {
            setBulkError(getErrorMessage(error, "Moment created, but candidate refresh failed."));
        } finally {
            setCreateSaving(false);
        }
    };

    const handleRefreshCandidates = async () => {
        if (!selectedMomentId || candidatesRefreshing) return;
        setCandidatesRefreshing(true);
        setBulkError(null);
        try {
            const response = await refreshMomentCandidates(selectedMomentId);
            setBulkNotice(`Candidates refreshed: ${response.inserted_count} inserted, ${response.touched_count} touched`);
            await loadCandidateRows();
        } catch (error) {
            setBulkError(getErrorMessage(error, "Failed to refresh candidates."));
        } finally {
            setCandidatesRefreshing(false);
        }
    };

    const runTaggedRemove = async (splitIds: number[]) => {
        if (!selectedMomentId || splitIds.length === 0) return;

        setPendingBulkAction("tagged-remove");
        setBulkError(null);
        try {
            const response = await removeMomentTaggedSplits(selectedMomentId, { split_ids: splitIds });
            setBulkNotice(`${response.updated_count} tagged rows removed.`);
            setTaggedSelection(new Set());
            await Promise.all([loadTaggedRows(), loadMoments()]);
        } catch (error) {
            setBulkError(getErrorMessage(error, "Failed to remove tagged rows."));
        } finally {
            setPendingBulkAction(null);
        }
    };

    const runTaggedMove = async (splitIds: number[], targetMomentId: number, confirmReassign = false) => {
        if (!selectedMomentId || splitIds.length === 0) return;

        setPendingBulkAction("tagged-move");
        setBulkError(null);
        try {
            const response = await moveMomentTaggedSplits(selectedMomentId, {
                split_ids: splitIds,
                target_moment_id: targetMomentId,
                confirm_reassign: confirmReassign,
            });
            setBulkNotice(`${response.updated_count} tagged rows moved.`);
            setTaggedSelection(new Set());
            setTaggedMoveTargetMomentId("none");
            await Promise.all([loadTaggedRows(), loadMoments()]);
        } catch (error) {
            const requiresConfirm = error instanceof ApiError && error.status === 409 && getApiErrorCode(error) === "MOMENT_REASSIGN_CONFIRM_REQUIRED";
            if (requiresConfirm && !confirmReassign) {
                setReassignConfirmState({
                    kind: "tagged-move",
                    splitIds,
                    targetMomentId,
                });
                return;
            }
            setBulkError(getErrorMessage(error, "Failed to move tagged rows."));
        } finally {
            setPendingBulkAction(null);
        }
    };

    const runCandidatesDecision = async (decision: CandidateDecision, splitIds: number[], confirmReassign = false) => {
        if (!selectedMomentId || splitIds.length === 0) return;

        setPendingBulkAction(`candidates-${decision}`);
        setBulkError(null);
        try {
            const response = await decideMomentCandidates(selectedMomentId, {
                split_ids: splitIds,
                decision,
                confirm_reassign: confirmReassign,
            });
            setBulkNotice(`${response.updated_count} candidates marked ${decision}.`);
            setCandidatesSelection(new Set());
            await loadCandidateRows();
        } catch (error) {
            const requiresConfirm =
                decision === "accepted" &&
                error instanceof ApiError &&
                error.status === 409 &&
                getApiErrorCode(error) === "MOMENT_REASSIGN_CONFIRM_REQUIRED";

            if (requiresConfirm && !confirmReassign) {
                setReassignConfirmState({
                    kind: "candidates-accept",
                    splitIds,
                });
                return;
            }
            setBulkError(getErrorMessage(error, "Failed to apply candidate decision."));
        } finally {
            setPendingBulkAction(null);
        }
    };

    const runTaggedBulkAction = async (mode: "remove" | "move") => {
        if (!selectedMomentId) return;
        const splitIds = toIds(taggedSelection);
        if (splitIds.length === 0) return;

        if (mode === "remove") {
            await runTaggedRemove(splitIds);
            return;
        }

        const targetMomentId = Number(taggedMoveTargetMomentId);
        if (!Number.isFinite(targetMomentId) || targetMomentId === selectedMomentId) {
            return;
        }

        await runTaggedMove(splitIds, targetMomentId, false);
    };

    const handleConfirmReassign = async () => {
        const current = reassignConfirmState;
        if (!current) return;

        setReassignConfirmState(null);
        if (current.kind === "tagged-move") {
            await runTaggedMove(current.splitIds, current.targetMomentId, true);
            return;
        }

        await runCandidatesDecision("accepted", current.splitIds, true);
    };

    const taggedPanel = (
        <div className="space-y-4">
            {bulkError ? <div className="rounded-lg border border-error-secondary bg-error-primary p-3 text-sm text-error-primary">{bulkError}</div> : null}
            {bulkNotice ? <div className="rounded-lg border border-success-secondary bg-success-primary p-3 text-sm text-success-primary">{bulkNotice}</div> : null}

            <div className="flex flex-wrap items-end gap-3">
                <div className="w-full max-w-sm">
                    <Input
                        label="Search tagged rows"
                        placeholder="Label or supplier"
                        value={taggedQuery}
                        onChange={(value) => {
                            setTaggedQuery(value);
                            setTaggedPage(1);
                        }}
                    />
                </div>
                <div className="w-full max-w-xs">
                    <Select
                        label="Move target"
                        items={moveTargetOptions}
                        selectedKey={taggedMoveTargetMomentId}
                        onSelectionChange={(key) => key && setTaggedMoveTargetMomentId(String(key))}
                    >
                        {(item) => <Select.Item id={item.id} label={item.label} />}
                    </Select>
                </div>
                <Button color="secondary" size="sm" onClick={() => void loadTaggedRows()} isDisabled={taggedLoading}>
                    Reload tagged
                </Button>
            </div>

            <MomentTaggedTable
                rows={taggedRows}
                loading={taggedLoading}
                error={taggedError}
                page={taggedPage}
                totalPages={toTotalPages(taggedTotal)}
                selectedKeys={taggedSelection}
                onSelectedKeysChange={setTaggedSelection}
                onPageChange={setTaggedPage}
                onOpenTransaction={handleOpenTransaction}
                bulkActionBar={
                    <MomentsBulkActionBar
                        selectedCount={taggedSelection.size}
                        label="tagged rows"
                        selectedAmount={taggedSelection.size > 0 ? taggedSelectedAmount : null}
                        onClearSelection={() => setTaggedSelection(new Set())}
                        actions={[
                            {
                                key: "remove",
                                label: "Remove from moment",
                                color: "secondary-destructive",
                                onPress: () => void runTaggedBulkAction("remove"),
                                isDisabled: pendingBulkAction !== null,
                                isLoading: pendingBulkAction === "tagged-remove",
                            },
                            {
                                key: "move",
                                label: "Move to target",
                                color: "primary",
                                onPress: () => void runTaggedBulkAction("move"),
                                isDisabled:
                                    pendingBulkAction !== null ||
                                    taggedMoveTargetMomentId === "none" ||
                                    Number(taggedMoveTargetMomentId) === selectedMomentId,
                                isLoading: pendingBulkAction === "tagged-move",
                            },
                        ]}
                    />
                }
            />
        </div>
    );

    const candidatesPanel = (
        <div className="space-y-4">
            {bulkError ? <div className="rounded-lg border border-error-secondary bg-error-primary p-3 text-sm text-error-primary">{bulkError}</div> : null}
            {bulkNotice ? <div className="rounded-lg border border-success-secondary bg-success-primary p-3 text-sm text-success-primary">{bulkNotice}</div> : null}

            <div className="flex flex-wrap items-end gap-3">
                <div className="w-full max-w-xs">
                    <Select
                        label="Candidate status"
                        items={CANDIDATE_STATUS_OPTIONS}
                        selectedKey={candidateStatusFilter}
                        onSelectionChange={(key) => {
                            if (!key) return;
                            setCandidateStatusFilter(String(key) as CandidateStatusFilter);
                            setCandidatesPage(1);
                        }}
                    >
                        {(item) => <Select.Item id={item.id} label={item.label} />}
                    </Select>
                </div>
                <Button color="secondary" size="sm" onClick={() => void loadCandidateRows()} isDisabled={candidatesLoading}>
                    Reload candidates
                </Button>
                <DemoGuard>
                    <Button
                        color="secondary"
                        size="sm"
                        onClick={() => void handleRefreshCandidates()}
                        isLoading={candidatesRefreshing}
                        isDisabled={pendingBulkAction !== null}
                    >
                        Refresh from range
                    </Button>
                </DemoGuard>
            </div>

            <MomentCandidatesTable
                rows={candidateRows}
                loading={candidatesLoading}
                error={candidatesError}
                page={candidatesPage}
                totalPages={toTotalPages(candidatesTotal)}
                selectedKeys={candidatesSelection}
                statusFilter={candidateStatusFilter}
                actionBusy={pendingBulkAction !== null}
                onSelectedKeysChange={setCandidatesSelection}
                onPageChange={setCandidatesPage}
                onDecideSplit={(splitId, decision) => void runCandidatesDecision(decision, [splitId])}
                onOpenTransactionSplit={handleOpenTransactionSplit}
                bulkActionBar={
                    <MomentsBulkActionBar
                        selectedCount={candidatesSelection.size}
                        label="candidate rows"
                        selectedAmount={candidatesSelection.size > 0 ? candidatesSelectedAmount : null}
                        onClearSelection={() => setCandidatesSelection(new Set())}
                        actions={[
                            {
                                key: "accept",
                                label: "Accept selected",
                                color: "primary",
                                onPress: () => void runCandidatesDecision("accepted", toIds(candidatesSelection)),
                                isDisabled: pendingBulkAction !== null,
                                isLoading: pendingBulkAction === "candidates-accepted",
                            },
                            {
                                key: "reject",
                                label: "Reject selected",
                                color: "secondary-destructive",
                                onPress: () => void runCandidatesDecision("rejected", toIds(candidatesSelection)),
                                isDisabled: pendingBulkAction !== null,
                                isLoading: pendingBulkAction === "candidates-rejected",
                            },
                        ]}
                    />
                }
            />
        </div>
    );

    return (
        <section className="flex flex-1 flex-col gap-6">
            <header className="flex flex-wrap items-start justify-between gap-3">
                <div className="space-y-1">
                    <h1 className="text-xl font-semibold text-primary">Moments</h1>
                    <p className="text-sm text-tertiary">Create and manage moments, then review tagged and candidate transactions in one overlay.</p>
                </div>
                {isTrueEmptyState ? null : (
                    <Button color="primary" onClick={openCreateMomentModal}>
                        Create moment
                    </Button>
                )}
            </header>

            <MomentsList
                moments={moments}
                loading={momentsLoading}
                error={momentsError}
                onRetry={() => void loadMoments()}
                onCreateMoment={openCreateMomentModal}
                onOpenMoment={handleOpenMoment}
            />

            <MomentOverlay
                isOpen={overlayOpen}
                moment={selectedMoment}
                activeTab={activeTab}
                taggedCount={taggedTotal}
                candidatesCount={candidatesTotal}
                onOpenChange={handleOverlayOpenChange}
                onTabChange={setActiveTab}
                onAddCoverImage={openCoverImagePicker}
                onRemoveCoverImage={() => void handleRemoveCoverImage()}
                onEditMoment={openEditModal}
                onDeleteMoment={openDeleteConfirm}
                coverImageSaving={coverImageSaving}
                coverImageError={coverImageError}
                taggedPanel={taggedPanel}
                candidatesPanel={candidatesPanel}
            />
            <input
                ref={coverFileInputRef}
                type="file"
                accept={MOMENT_COVER_UPLOAD_ACCEPT}
                className="hidden"
                onChange={handleCoverImageUpload}
            />

            <ModalOverlay isOpen={createOpen} onOpenChange={(open) => !open && !createSaving && resetCreateState()}>
                <Modal className="my-auto">
                    <Dialog className="mx-auto max-w-xl rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <form
                            className="flex w-full flex-col gap-4"
                            onSubmit={(event) => {
                                event.preventDefault();
                                void handleCreateMoment();
                            }}
                        >
                            <header className="space-y-1">
                                <h2 className="text-lg font-semibold text-primary">Create moment</h2>
                                <p className="text-sm text-tertiary">Set the name and date range to start candidate discovery right away.</p>
                            </header>

                            <Input
                                label="Name"
                                placeholder="Ski Week 2025"
                                value={createDraft.name}
                                isDisabled={createSaving}
                                onChange={(value) => updateCreateDraft({ name: value })}
                            />

                            <div className="flex flex-wrap gap-1.5">
                                {DATE_SHORTCUTS.map((shortcut) => (
                                    <Button
                                        key={shortcut.label}
                                        type="button"
                                        color="tertiary"
                                        size="sm"
                                        isDisabled={createSaving}
                                        onClick={() => updateCreateDraft(shortcut.get())}
                                    >
                                        {shortcut.label}
                                    </Button>
                                ))}
                            </div>

                            <div className="grid gap-3 sm:grid-cols-2">
                                <div className="space-y-1">
                                    <p className="text-sm font-medium text-secondary">Start date</p>
                                    <DatePicker
                                        aria-label="Start date"
                                        value={createStartDateValue}
                                        maxValue={createEndDateValue ?? undefined}
                                        isDisabled={createSaving}
                                        onChange={(value) => updateCreateDraft({ startDate: value?.toString() ?? "" })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <p className="text-sm font-medium text-secondary">End date</p>
                                    <DatePicker
                                        aria-label="End date"
                                        value={createEndDateValue}
                                        minValue={createStartDateValue ?? undefined}
                                        isDisabled={createSaving}
                                        onChange={(value) => updateCreateDraft({ endDate: value?.toString() ?? "" })}
                                    />
                                </div>
                            </div>

                            <TextArea
                                label="Description"
                                placeholder="Optional notes about this moment"
                                value={createDraft.description}
                                isDisabled={createSaving}
                                rows={3}
                                onChange={(value) => updateCreateDraft({ description: value })}
                            />

                            {createError ? (
                                <div className="rounded-lg border border-error-secondary bg-error-primary p-3 text-sm text-error-primary">{createError}</div>
                            ) : null}

                            <footer className="flex items-center justify-end gap-2 border-t border-secondary pt-2">
                                <Button type="button" color="tertiary" isDisabled={createSaving} onClick={resetCreateState}>
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button type="submit" color="primary" isLoading={createSaving} isDisabled={createSaving || Boolean(createValidationError)}>
                                        Create moment
                                    </Button>
                                </DemoGuard>
                            </footer>
                        </form>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={Boolean(reassignConfirmState)} onOpenChange={(open) => !open && setReassignConfirmState(null)}>
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex w-full flex-col gap-4">
                            <header className="space-y-1">
                                <h2 className="text-lg font-semibold text-primary">Confirm reassignment</h2>
                                <p className="text-sm text-tertiary">{REASSIGN_CONFIRM_TEXT}</p>
                            </header>
                            {reassignSplitDetails.length > 0 ? (
                                <ul className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-secondary bg-secondary px-3 py-2">
                                    {reassignSplitDetails.slice(0, 10).map((item, i) => (
                                        <li key={i} className="flex items-center justify-between gap-3 text-sm">
                                            <span className="truncate text-primary">{item.label || "Untitled"}</span>
                                            <span className="shrink-0 font-medium text-secondary">{formatAmount(item.amount, String(item.currency ?? "EUR"))}</span>
                                        </li>
                                    ))}
                                    {reassignSplitDetails.length > 10 ? (
                                        <li className="text-xs text-tertiary">+{reassignSplitDetails.length - 10} more</li>
                                    ) : null}
                                </ul>
                            ) : null}
                            <footer className="flex items-center justify-end gap-2 border-t border-secondary pt-2">
                                <Button type="button" color="tertiary" isDisabled={pendingBulkAction !== null} onClick={() => setReassignConfirmState(null)}>
                                    Cancel
                                </Button>
                                <Button
                                    type="button"
                                    color="primary"
                                    isLoading={pendingBulkAction !== null}
                                    isDisabled={pendingBulkAction !== null}
                                    onClick={() => void handleConfirmReassign()}
                                >
                                    Confirm reassignment
                                </Button>
                            </footer>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={editOpen} onOpenChange={(open) => !open && !editSaving && resetEditState()}>
                <Modal className="my-auto">
                    <Dialog className="mx-auto max-w-xl rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <form
                            className="flex w-full flex-col gap-4"
                            onSubmit={(event) => {
                                event.preventDefault();
                                void handleEditMoment();
                            }}
                        >
                            <header className="space-y-1">
                                <h2 className="text-lg font-semibold text-primary">Edit moment</h2>
                                <p className="text-sm text-tertiary">Update the name, date range, or description of this moment.</p>
                            </header>

                            <Input
                                label="Name"
                                placeholder="Ski Week 2025"
                                value={editDraft.name}
                                isDisabled={editSaving}
                                onChange={(value) => updateEditDraft({ name: value })}
                            />

                            <div className="flex flex-wrap gap-1.5">
                                {DATE_SHORTCUTS.map((shortcut) => (
                                    <Button
                                        key={shortcut.label}
                                        type="button"
                                        color="tertiary"
                                        size="sm"
                                        isDisabled={editSaving}
                                        onClick={() => updateEditDraft(shortcut.get())}
                                    >
                                        {shortcut.label}
                                    </Button>
                                ))}
                            </div>

                            <div className="grid gap-3 sm:grid-cols-2">
                                <div className="space-y-1">
                                    <p className="text-sm font-medium text-secondary">Start date</p>
                                    <DatePicker
                                        aria-label="Start date"
                                        value={editStartDateValue}
                                        maxValue={editEndDateValue ?? undefined}
                                        isDisabled={editSaving}
                                        onChange={(value) => updateEditDraft({ startDate: value?.toString() ?? "" })}
                                    />
                                </div>
                                <div className="space-y-1">
                                    <p className="text-sm font-medium text-secondary">End date</p>
                                    <DatePicker
                                        aria-label="End date"
                                        value={editEndDateValue}
                                        minValue={editStartDateValue ?? undefined}
                                        isDisabled={editSaving}
                                        onChange={(value) => updateEditDraft({ endDate: value?.toString() ?? "" })}
                                    />
                                </div>
                            </div>

                            <TextArea
                                label="Description"
                                placeholder="Optional notes about this moment"
                                value={editDraft.description}
                                isDisabled={editSaving}
                                rows={3}
                                onChange={(value) => updateEditDraft({ description: value })}
                            />

                            {editError ? (
                                <div className="rounded-lg border border-error-secondary bg-error-primary p-3 text-sm text-error-primary">{editError}</div>
                            ) : null}

                            <footer className="flex items-center justify-end gap-2 border-t border-secondary pt-2">
                                <Button type="button" color="tertiary" isDisabled={editSaving} onClick={resetEditState}>
                                    Cancel
                                </Button>
                                <Button type="submit" color="primary" isLoading={editSaving} isDisabled={editSaving || Boolean(editValidationError)}>
                                    Save changes
                                </Button>
                            </footer>
                        </form>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={deleteConfirmOpen} onOpenChange={(open) => !open && !deleteDeleting && setDeleteConfirmOpen(false)}>
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex w-full flex-col gap-4">
                            <header className="space-y-1">
                                <h2 className="text-lg font-semibold text-primary">Delete moment</h2>
                                <p className="text-sm text-tertiary">
                                    Are you sure you want to delete <span className="font-medium text-primary">{selectedMoment?.name}</span>?
                                </p>
                                {(selectedMoment?.tagged_splits_count ?? 0) > 0 ? (
                                    <p className="text-sm text-warning-primary">
                                        {selectedMoment?.tagged_splits_count} tagged split{(selectedMoment?.tagged_splits_count ?? 0) !== 1 ? "s" : ""} will lose their moment association.
                                    </p>
                                ) : null}
                            </header>

                            {deleteError ? (
                                <div className="rounded-lg border border-error-secondary bg-error-primary p-3 text-sm text-error-primary">{deleteError}</div>
                            ) : null}

                            <footer className="flex items-center justify-end gap-2 border-t border-secondary pt-2">
                                <Button type="button" color="tertiary" isDisabled={deleteDeleting} onClick={() => setDeleteConfirmOpen(false)}>
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button
                                        type="button"
                                        color="primary-destructive"
                                        isLoading={deleteDeleting}
                                        isDisabled={deleteDeleting}
                                        onClick={() => void handleDeleteMoment()}
                                    >
                                        Delete moment
                                    </Button>
                                </DemoGuard>
                            </footer>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </section>
    );
};

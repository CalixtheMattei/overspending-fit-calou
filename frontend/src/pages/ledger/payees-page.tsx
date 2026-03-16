import { useEffect, useMemo, useState } from "react";
import { Edit01, Plus, Trash01 } from "@untitledui/icons";
import type { SortDescriptor } from "@react-types/shared";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Table, TableCard } from "@/components/application/table/table";
import { Tabs } from "@/components/application/tabs/tabs";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { ButtonUtility } from "@/components/base/buttons/button-utility";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";
import { Toggle } from "@/components/base/toggle/toggle";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import type { AutomaticPayeeSeed, Payee } from "@/services/payees";
import {
    applyAutomaticPayee,
    createPayee,
    deletePayee,
    fetchAutomaticPayees,
    fetchPayees,
    ignoreAutomaticPayee,
    restoreAutomaticPayee,
    updatePayee,
} from "@/services/payees";

const PAYEE_COLUMNS = [
    { id: "name", name: "Payee", isSortable: true },
    { id: "kind", name: "Kind", isSortable: true },
    { id: "count", name: "Transactions", isSortable: true },
    { id: "actions", name: "Actions", isSortable: false },
] as const;

type PayeeColumn = (typeof PAYEE_COLUMNS)[number];
type PayeeColumnId = PayeeColumn["id"];
type PayeeKindValue = "unknown" | "person" | "merchant";

const PAYEE_KIND_OPTIONS = [
    { id: "unknown", label: "Unknown" },
    { id: "person", label: "Person" },
    { id: "merchant", label: "Merchant" },
];

const CREATE_MODAL_TABS = [
    { id: "manual", label: "Manual" },
    { id: "automatic", label: "Automatic" },
] as const;

type CreateModalTabId = (typeof CREATE_MODAL_TABS)[number]["id"];

const getKindBadgeColor = (kind: string) => {
    if (kind === "person") return "brand";
    if (kind === "merchant") return "success";
    return "gray";
};

export const PayeesPage = () => {
    const [payees, setPayees] = useState<Payee[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [searchQuery, setSearchQuery] = useState("");
    const [createName, setCreateName] = useState("");
    const [createKind, setCreateKind] = useState<PayeeKindValue>("unknown");
    const [createError, setCreateError] = useState<string | null>(null);
    const [createOpen, setCreateOpen] = useState(false);
    const [createTab, setCreateTab] = useState<CreateModalTabId>("manual");

    const [automaticSeeds, setAutomaticSeeds] = useState<AutomaticPayeeSeed[]>([]);
    const [automaticLoading, setAutomaticLoading] = useState(false);
    const [automaticError, setAutomaticError] = useState<string | null>(null);
    const [automaticQuery, setAutomaticQuery] = useState("");
    const [showDismissed, setShowDismissed] = useState(false);

    const [applySeed, setApplySeed] = useState<AutomaticPayeeSeed | null>(null);
    const [applyName, setApplyName] = useState("");
    const [applyKind, setApplyKind] = useState<PayeeKindValue>("merchant");
    const [applyOverwrite, setApplyOverwrite] = useState(false);
    const [applySaving, setApplySaving] = useState(false);
    const [applyError, setApplyError] = useState<string | null>(null);
    const [applySummary, setApplySummary] = useState<string | null>(null);

    const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor | undefined>();
    const [editState, setEditState] = useState<{
        payee: Payee | null;
        name: string;
        kind: PayeeKindValue;
        error: string | null;
        isSaving: boolean;
    }>({
        payee: null,
        name: "",
        kind: "unknown",
        error: null,
        isSaving: false,
    });

    const [deleteTarget, setDeleteTarget] = useState<Payee | null>(null);
    const [deleteError, setDeleteError] = useState<string | null>(null);

    const refreshPayees = async () => {
        const data = await fetchPayees({ q: searchQuery.trim() || undefined, limit: 200 });
        setPayees(data);
    };

    const refreshAutomaticSeeds = async () => {
        const data = await fetchAutomaticPayees({
            q: automaticQuery.trim() || undefined,
            limit: 100,
            include_ignored: showDismissed,
        });
        setAutomaticSeeds(data);
    };

    useEffect(() => {
        let isActive = true;
        const loadPayees = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await fetchPayees({ q: searchQuery.trim() || undefined, limit: 200 });
                if (!isActive) return;
                setPayees(data);
            } catch (err) {
                if (!isActive) return;
                setError(err instanceof Error ? err.message : "Failed to load payees.");
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };

        void loadPayees();
        return () => {
            isActive = false;
        };
    }, [searchQuery]);

    useEffect(() => {
        if (!createOpen || createTab !== "automatic") {
            return;
        }

        let isActive = true;
        const timer = setTimeout(async () => {
            setAutomaticLoading(true);
            setAutomaticError(null);
            try {
                const data = await fetchAutomaticPayees({
                    q: automaticQuery.trim() || undefined,
                    limit: 100,
                    include_ignored: showDismissed,
                });
                if (!isActive) return;
                setAutomaticSeeds(data);
            } catch (err) {
                if (!isActive) return;
                setAutomaticError(err instanceof Error ? err.message : "Failed to load automatic payees.");
            } finally {
                if (isActive) {
                    setAutomaticLoading(false);
                }
            }
        }, 250);

        return () => {
            isActive = false;
            clearTimeout(timer);
        };
    }, [createOpen, createTab, automaticQuery, showDismissed]);

    const handleCreate = async () => {
        const name = createName.trim();
        if (!name) return;
        try {
            const created = await createPayee({ name, kind: createKind });
            setPayees((prev) => {
                const exists = prev.some((item) => item.id === created.id);
                const next = exists ? prev.map((item) => (item.id === created.id ? created : item)) : [...prev, created];
                return next.sort((a, b) => a.name.localeCompare(b.name));
            });
            setCreateName("");
            setCreateError(null);
            setCreateOpen(false);
            setCreateTab("manual");
        } catch (err) {
            setCreateError(err instanceof Error ? err.message : "Failed to create payee.");
        }
    };

    const closeCreateModal = () => {
        setCreateOpen(false);
        setCreateTab("manual");
        setCreateError(null);
        setAutomaticError(null);
        setAutomaticQuery("");
        setShowDismissed(false);
    };

    const kindLabelById = useMemo(() => {
        return new Map(PAYEE_KIND_OPTIONS.map((option) => [option.id, option.label]));
    }, []);

    const sortedPayees = useMemo(() => {
        if (!sortDescriptor?.column) {
            return [...payees].sort((a, b) => a.name.localeCompare(b.name));
        }

        const column = String(sortDescriptor.column) as PayeeColumnId;
        const direction = sortDescriptor.direction === "descending" ? -1 : 1;

        const compare = (valueA: string | number, valueB: string | number) => {
            if (typeof valueA === "number" && typeof valueB === "number") {
                return valueA - valueB;
            }
            return String(valueA).localeCompare(String(valueB), undefined, { sensitivity: "base" });
        };

        return [...payees].sort((a, b) => {
            let result = 0;
            if (column === "name") {
                result = compare(a.name, b.name);
            } else if (column === "kind") {
                const labelA = kindLabelById.get(a.kind) ?? a.kind;
                const labelB = kindLabelById.get(b.kind) ?? b.kind;
                result = compare(labelA, labelB);
            } else if (column === "count") {
                result = compare(a.transaction_count ?? 0, b.transaction_count ?? 0);
            }

            if (result === 0) {
                result = a.name.localeCompare(b.name);
            }

            return result * direction;
        });
    }, [kindLabelById, payees, sortDescriptor]);

    const handleSortChange = (descriptor: SortDescriptor) => {
        const column = String(descriptor.column) as PayeeColumnId;
        if (column === "actions") return;
        setSortDescriptor(descriptor);
    };

    const canCreate = createName.trim().length > 0 && createKind !== "unknown";

    const openEditModal = (payee: Payee) => {
        setEditState({
            payee,
            name: payee.name,
            kind: payee.kind as PayeeKindValue,
            error: null,
            isSaving: false,
        });
    };

    const closeEditModal = () => {
        setEditState({
            payee: null,
            name: "",
            kind: "unknown",
            error: null,
            isSaving: false,
        });
    };

    const openApplyModal = (seed: AutomaticPayeeSeed) => {
        setApplySeed(seed);
        setApplyName(seed.name);
        setApplyKind("merchant");
        setApplyOverwrite(false);
        setApplySaving(false);
        setApplyError(null);
        setCreateOpen(false);
    };

    const closeApplyModal = () => {
        setApplySeed(null);
        setApplyName("");
        setApplyKind("merchant");
        setApplyOverwrite(false);
        setApplySaving(false);
        setApplyError(null);
    };

    return (
        <section className="flex flex-1 flex-col gap-8">
            <header className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="flex flex-col gap-2">
                    <h1 className="text-2xl font-semibold text-primary">Payees</h1>
                    <p className="text-sm text-tertiary">Manage the people and merchants associated with your transactions.</p>
                </div>
                <Button
                    color="primary"
                    iconLeading={Plus}
                    onClick={() => {
                        setCreateError(null);
                        setCreateTab("manual");
                        setAutomaticQuery("");
                        setShowDismissed(false);
                        setCreateOpen(true);
                    }}
                >
                    Create payees
                </Button>
            </header>

            {applySummary && (
                <div className="rounded-lg border border-success-subtle bg-success-primary/10 px-4 py-3 text-sm text-success-primary">
                    {applySummary}
                </div>
            )}

            <TableCard.Root>
                <TableCard.Header
                    title="Payees"
                    description="Review, edit, and remove payees in bulk."
                    contentTrailing={
                        <div className="w-full md:w-auto md:min-w-[260px]">
                            <Input
                                aria-label="Search payees"
                                placeholder="Search payees"
                                value={searchQuery}
                                onChange={(value) => setSearchQuery(value)}
                            />
                        </div>
                    }
                />
                {loading ? (
                    <div className="flex justify-center py-10">
                        <LoadingIndicator label="Loading payees..." />
                    </div>
                ) : error ? (
                    <div className="px-6 pb-6 text-sm text-error-primary">{error}</div>
                ) : (
                    <Table aria-label="Payees table" sortDescriptor={sortDescriptor} onSortChange={handleSortChange}>
                        <Table.Header columns={PAYEE_COLUMNS}>
                            {(column) => (
                                <Table.Head allowsSorting={column.isSortable}>
                                    <span className="text-xs font-semibold text-secondary">{column.name}</span>
                                </Table.Head>
                            )}
                        </Table.Header>
                        <Table.Body items={sortedPayees}>
                            {(payee) => {
                                return (
                                    <Table.Row id={String(payee.id)} columns={PAYEE_COLUMNS}>
                                        {(column) => (
                                            <Table.Cell>
                                                {column.id === "name" && <span className="text-sm text-primary">{payee.name}</span>}
                                                {column.id === "kind" && (
                                                    <Badge size="sm" color={getKindBadgeColor(payee.kind)}>
                                                        {payee.kind}
                                                    </Badge>
                                                )}
                                                {column.id === "count" && <span className="text-sm text-primary">{payee.transaction_count}</span>}
                                                {column.id === "actions" && (
                                                    <div className="flex items-center justify-end gap-2">
                                                        <ButtonUtility icon={Edit01} tooltip="Edit payee" onClick={() => openEditModal(payee)} />
                                                        <ButtonUtility
                                                            icon={Trash01}
                                                            tooltip="Delete payee"
                                                            onClick={() => {
                                                                setDeleteError(null);
                                                                setDeleteTarget(payee);
                                                            }}
                                                        />
                                                    </div>
                                                )}
                                            </Table.Cell>
                                        )}
                                    </Table.Row>
                                );
                            }}
                        </Table.Body>
                    </Table>
                )}
            </TableCard.Root>

            <ModalOverlay isOpen={createOpen} onOpenChange={(open) => !open && closeCreateModal()}>
                <Modal>
                    <Dialog className="max-w-2xl rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Create payee</h4>
                                <p className="text-sm text-tertiary">Create manually or use automatic suggestions from linked imports.</p>
                            </div>
                            <Tabs
                                selectedKey={createTab}
                                onSelectionChange={(key) => setCreateTab(key as CreateModalTabId)}
                                className="flex flex-col gap-4"
                            >
                                <Tabs.List
                                    aria-label="Create payee tabs"
                                    size="sm"
                                    type="button-border"
                                    items={CREATE_MODAL_TABS}
                                    className="w-fit"
                                >
                                    {(item) => <Tabs.Item id={item.id}>{item.label}</Tabs.Item>}
                                </Tabs.List>
                                <Tabs.Panel id="manual">
                                    <div className="flex flex-col gap-4">
                                        <Input
                                            label="Name"
                                            placeholder="Add a payee"
                                            value={createName}
                                            onChange={(value) => setCreateName(value)}
                                        />
                                        <Select
                                            label="Kind"
                                            items={PAYEE_KIND_OPTIONS}
                                            selectedKey={createKind}
                                            onSelectionChange={(key) => key && setCreateKind(String(key) as PayeeKindValue)}
                                        >
                                            {(item) => <Select.Item id={item.id} label={item.label} />}
                                        </Select>
                                        {createError && (
                                            <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                                {createError}
                                            </div>
                                        )}
                                        <div className="flex justify-end gap-2">
                                            <Button color="tertiary" onClick={closeCreateModal}>
                                                Cancel
                                            </Button>
                                            <DemoGuard>
                                                <Button color="primary" onClick={handleCreate} isDisabled={!canCreate}>
                                                    Create
                                                </Button>
                                            </DemoGuard>
                                        </div>
                                    </div>
                                </Tabs.Panel>
                                <Tabs.Panel id="automatic">
                                    <div className="flex flex-col gap-4">
                                        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                                            <Input
                                                aria-label="Search automatic payees"
                                                placeholder="Search deduced payees"
                                                value={automaticQuery}
                                                onChange={(value) => setAutomaticQuery(value)}
                                            />
                                            <Toggle
                                                label="Show dismissed"
                                                isSelected={showDismissed}
                                                onChange={setShowDismissed}
                                                slim
                                                size="sm"
                                            />
                                        </div>
                                        <div className="overflow-hidden rounded-xl ring-1 ring-secondary">
                                            <div className="grid grid-cols-[minmax(0,1fr)_auto_auto] gap-3 border-b border-secondary bg-secondary px-4 py-2">
                                                <span className="text-xs font-semibold text-secondary">Name</span>
                                                <span className="text-xs font-semibold text-secondary">Linked transactions</span>
                                                <span className="text-xs font-semibold text-secondary">Actions</span>
                                            </div>
                                            {automaticLoading ? (
                                                <div className="flex justify-center py-8">
                                                    <LoadingIndicator label="Loading automatic payees..." />
                                                </div>
                                            ) : automaticError ? (
                                                <div className="px-4 py-6 text-sm text-error-primary">{automaticError}</div>
                                            ) : automaticSeeds.length === 0 ? (
                                                <div className="px-4 py-6 text-sm text-tertiary">No automatic payees found.</div>
                                            ) : (
                                                <div className="divide-y divide-secondary">
                                                    {automaticSeeds.map((seed) => (
                                                        <div
                                                            key={seed.canonical_name}
                                                            className="grid grid-cols-[minmax(0,1fr)_auto_auto] items-center gap-3 px-4 py-3"
                                                        >
                                                            <span className="truncate text-sm text-primary">{seed.name}</span>
                                                            <Badge size="sm" color={seed.is_ignored ? "warning" : "gray"}>
                                                                {seed.linked_transaction_count}
                                                            </Badge>
                                                            <div className="flex items-center gap-2">
                                                                <Button size="sm" color="secondary" onClick={() => openApplyModal(seed)}>
                                                                    Use
                                                                </Button>
                                                                {seed.is_ignored ? (
                                                                    <DemoGuard>
                                                                        <Button
                                                                            size="sm"
                                                                            color="tertiary"
                                                                            onClick={async () => {
                                                                                try {
                                                                                    setAutomaticError(null);
                                                                                    await restoreAutomaticPayee(seed.canonical_name);
                                                                                    await refreshAutomaticSeeds();
                                                                                } catch (err) {
                                                                                    setAutomaticError(err instanceof Error ? err.message : "Failed to restore suggestion.");
                                                                                }
                                                                            }}
                                                                        >
                                                                            Restore
                                                                        </Button>
                                                                    </DemoGuard>
                                                                ) : (
                                                                    <DemoGuard>
                                                                        <Button
                                                                            size="sm"
                                                                            color="tertiary"
                                                                            onClick={async () => {
                                                                                try {
                                                                                    setAutomaticError(null);
                                                                                    await ignoreAutomaticPayee(seed.canonical_name);
                                                                                    await refreshAutomaticSeeds();
                                                                                } catch (err) {
                                                                                    setAutomaticError(err instanceof Error ? err.message : "Failed to dismiss suggestion.");
                                                                                }
                                                                            }}
                                                                        >
                                                                            Dismiss
                                                                        </Button>
                                                                    </DemoGuard>
                                                                )}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex justify-end">
                                            <Button color="tertiary" onClick={closeCreateModal}>
                                                Close
                                            </Button>
                                        </div>
                                    </div>
                                </Tabs.Panel>
                            </Tabs>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={!!applySeed} onOpenChange={(open) => !open && closeApplyModal()}>
                <Modal>
                    <Dialog className="max-w-lg rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Apply automatic payee</h4>
                                <p className="text-sm text-tertiary">
                                    {applySeed
                                        ? `${applySeed.linked_transaction_count} matched transactions for "${applySeed.name}".`
                                        : "Apply this payee to matched transactions."}
                                </p>
                            </div>
                            <Input
                                label="Payee name"
                                value={applyName}
                                onChange={(value) => setApplyName(value)}
                                placeholder="Payee name"
                            />
                            <Select
                                label="Kind"
                                items={PAYEE_KIND_OPTIONS}
                                selectedKey={applyKind}
                                onSelectionChange={(key) => key && setApplyKind(String(key) as PayeeKindValue)}
                            >
                                {(item) => <Select.Item id={item.id} label={item.label} />}
                            </Select>
                            <Toggle
                                label="Overwrite existing payees"
                                hint="When off, only transactions without a payee are updated."
                                isSelected={applyOverwrite}
                                onChange={setApplyOverwrite}
                                slim
                                size="sm"
                            />
                            {applyError && (
                                <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                    {applyError}
                                </div>
                            )}
                            <div className="flex justify-end gap-2">
                                <Button color="tertiary" onClick={closeApplyModal} isDisabled={applySaving}>
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button
                                        color="primary"
                                        isDisabled={applySaving || !applySeed || !applyName.trim() || applyKind === "unknown"}
                                        onClick={async () => {
                                            if (!applySeed) return;
                                            setApplySaving(true);
                                            setApplyError(null);
                                            try {
                                                const result = await applyAutomaticPayee({
                                                    seed_canonical_name: applySeed.canonical_name,
                                                    payee_name: applyName.trim(),
                                                    kind: applyKind,
                                                    overwrite_existing: applyOverwrite,
                                                });
                                                await refreshPayees();
                                                await refreshAutomaticSeeds();
                                                setApplySummary(
                                                    `Applied "${result.payee.name}" to ${result.updated_transaction_count} of ${result.matched_transaction_count} matched transactions.`,
                                                );
                                                closeApplyModal();
                                            } catch (err) {
                                                setApplyError(err instanceof Error ? err.message : "Failed to apply automatic payee.");
                                                setApplySaving(false);
                                            }
                                        }}
                                    >
                                        {applySaving ? "Applying..." : "Apply"}
                                    </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={!!editState.payee} onOpenChange={(open) => !open && closeEditModal()}>
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Edit payee</h4>
                                <p className="text-sm text-tertiary">Update the payee name and kind.</p>
                            </div>
                            <Input
                                label="Name"
                                placeholder="Payee name"
                                value={editState.name}
                                onChange={(value) => setEditState((prev) => ({ ...prev, name: value }))}
                            />
                            <Select
                                label="Kind"
                                items={PAYEE_KIND_OPTIONS}
                                selectedKey={editState.kind}
                                onSelectionChange={(key) => key && setEditState((prev) => ({ ...prev, kind: String(key) as PayeeKindValue }))}
                            >
                                {(item) => <Select.Item id={item.id} label={item.label} />}
                            </Select>
                            {editState.error && (
                                <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                    {editState.error}
                                </div>
                            )}
                            <div className="flex justify-end gap-2">
                                <Button color="tertiary" onClick={closeEditModal} isDisabled={editState.isSaving}>
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button
                                        color="primary"
                                        isDisabled={
                                            editState.isSaving ||
                                            !editState.name.trim() ||
                                            !editState.payee ||
                                            (editState.payee &&
                                                editState.name.trim() === editState.payee.name &&
                                                editState.kind === editState.payee.kind)
                                        }
                                        onClick={async () => {
                                            if (!editState.payee) return;
                                            const name = editState.name.trim();
                                            if (!name) return;
                                            setEditState((prev) => ({ ...prev, isSaving: true }));
                                            try {
                                                const updated = await updatePayee(editState.payee.id, {
                                                    name,
                                                    kind: editState.kind,
                                                });
                                                setPayees((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
                                                closeEditModal();
                                            } catch (err) {
                                                setEditState((prev) => ({
                                                    ...prev,
                                                    isSaving: false,
                                                    error: err instanceof Error ? err.message : "Failed to update payee.",
                                                }));
                                            }
                                        }}
                                    >
                                        {editState.isSaving ? "Saving..." : "Update"}
                                    </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Delete payee</h4>
                                <p className="text-sm text-tertiary">
                                    {deleteTarget
                                        ? `${deleteTarget.transaction_count} transactions use this payee. They will become unassigned.`
                                        : "This will unassign transactions from the payee."}
                                </p>
                            </div>
                            {deleteError && (
                                <div className="rounded-lg border border-error-subtle bg-error-primary/10 p-3 text-xs text-error-primary">
                                    {deleteError}
                                </div>
                            )}
                            <div className="flex justify-end gap-2">
                                <Button color="tertiary" onClick={() => setDeleteTarget(null)}>
                                    Cancel
                                </Button>
                                <DemoGuard>
                                    <Button
                                        color="primary"
                                        onClick={async () => {
                                            if (!deleteTarget) return;
                                            try {
                                                await deletePayee(deleteTarget.id);
                                                setPayees((prev) => prev.filter((item) => item.id !== deleteTarget.id));
                                                setDeleteTarget(null);
                                            } catch (err) {
                                                setDeleteError(err instanceof Error ? err.message : "Failed to delete payee.");
                                            }
                                        }}
                                    >
                                        Delete
                                    </Button>
                                </DemoGuard>
                            </div>
                        </div>
                    </Dialog>
                </Modal>
            </ModalOverlay>
        </section>
    );
};

import { useEffect, useMemo, useState } from "react";
import { Edit01, Plus, Trash01 } from "@untitledui/icons";
import type { SortDescriptor } from "@react-types/shared";
import { Dialog, Modal, ModalOverlay } from "@/components/application/modals/modal";
import { Table, TableCard } from "@/components/application/table/table";
import { Badge } from "@/components/base/badges/badges";
import { Button } from "@/components/base/buttons/button";
import { DemoGuard } from "@/components/base/demo-guard/DemoGuard";
import { Input } from "@/components/base/input/input";
import { Select } from "@/components/base/select/select";
import { Dropdown } from "@/components/base/dropdown/dropdown";
import { LoadingIndicator } from "@/components/application/loading-indicator/loading-indicator";
import { INTERNAL_ACCOUNT_TYPE_OPTIONS } from "@/components/ledger/constants";
import type { InternalAccount } from "@/services/internal-accounts";
import { createInternalAccount, deleteInternalAccount, fetchInternalAccounts, updateInternalAccount } from "@/services/internal-accounts";

const ACCOUNT_COLUMNS = [
    { id: "name", name: "Account", isSortable: true },
    { id: "type", name: "Type", isSortable: true },
    { id: "actions", name: "Actions", isSortable: false },
] as const;

type AccountColumn = (typeof ACCOUNT_COLUMNS)[number];
type AccountColumnId = AccountColumn["id"];

export const InternalAccountsPage = () => {
    const [accounts, setAccounts] = useState<InternalAccount[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [createName, setCreateName] = useState("");
    const [createType, setCreateType] = useState("none");
    const [createError, setCreateError] = useState<string | null>(null);
    const [createOpen, setCreateOpen] = useState(false);
    const [sortDescriptor, setSortDescriptor] = useState<SortDescriptor | undefined>();

    const [editState, setEditState] = useState<{
        account: InternalAccount | null;
        name: string;
        error: string | null;
        isSaving: boolean;
    }>({
        account: null,
        name: "",
        error: null,
        isSaving: false,
    });

    const [deleteTarget, setDeleteTarget] = useState<InternalAccount | null>(null);
    const [deleteError, setDeleteError] = useState<string | null>(null);

    useEffect(() => {
        let isActive = true;
        const loadAccounts = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await fetchInternalAccounts();
                if (!isActive) return;
                setAccounts(data);
            } catch (err) {
                if (!isActive) return;
                setError(err instanceof Error ? err.message : "Failed to load internal accounts.");
            } finally {
                if (isActive) {
                    setLoading(false);
                }
            }
        };

        loadAccounts();

        return () => {
            isActive = false;
        };
    }, []);

    const handleCreate = async () => {
        const name = createName.trim();
        if (!name) return;
        try {
            const created = await createInternalAccount({
                name,
                type: createType === "none" ? null : createType,
            });
            setAccounts((prev) => [...prev, created].sort((a, b) => a.position - b.position));
            setCreateName("");
            setCreateError(null);
            setCreateOpen(false);
        } catch (err) {
            setCreateError(err instanceof Error ? err.message : "Failed to create internal account.");
        }
    };

    const closeCreateModal = () => {
        setCreateOpen(false);
        setCreateError(null);
    };

    const closeEditModal = () => {
        setEditState({
            account: null,
            name: "",
            error: null,
            isSaving: false,
        });
    };

    const refreshAccounts = async () => {
        const data = await fetchInternalAccounts();
        setAccounts(data);
    };

    const typeLabelById = useMemo(() => {
        return new Map(INTERNAL_ACCOUNT_TYPE_OPTIONS.map((option) => [option.id, option.label]));
    }, []);

    const sortedAccounts = useMemo(() => {
        if (!sortDescriptor?.column) {
            return [...accounts].sort((a, b) => a.position - b.position);
        }

        const column = String(sortDescriptor.column) as AccountColumnId;
        const direction = sortDescriptor.direction === "descending" ? -1 : 1;

        const compare = (valueA: string | number, valueB: string | number) => {
            if (typeof valueA === "number" && typeof valueB === "number") {
                return valueA - valueB;
            }
            return String(valueA).localeCompare(String(valueB), undefined, { sensitivity: "base" });
        };

        return [...accounts].sort((a, b) => {
            let result = 0;
            if (column === "name") {
                result = compare(a.name, b.name);
            } else if (column === "type") {
                const labelA = typeLabelById.get(a.type ?? "none") ?? "No type";
                const labelB = typeLabelById.get(b.type ?? "none") ?? "No type";
                result = compare(labelA, labelB);
            }

            if (result === 0) {
                result = a.position - b.position;
            }

            return result * direction;
        });
    }, [accounts, sortDescriptor, typeLabelById]);

    const handleSortChange = (descriptor: SortDescriptor) => {
        const column = String(descriptor.column) as AccountColumnId;
        if (column === "actions") return;
        setSortDescriptor(descriptor);
    };

    const canCreate = createName.trim().length > 0;

    return (
        <section className="flex flex-1 flex-col gap-8">
            <header className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="flex flex-col gap-2">
                    <h1 className="text-2xl font-semibold text-primary">Internal Accounts</h1>
                    <p className="text-sm text-tertiary">Organize buckets for transfers and internal balances.</p>
                </div>
                <Button
                    color="primary"
                    iconLeading={Plus}
                    onClick={() => {
                        setCreateError(null);
                        setCreateOpen(true);
                    }}
                >
                    Create account
                </Button>
            </header>

            <TableCard.Root>
                <TableCard.Header title="Internal accounts" description="Rename and delete internal accounts." />
                {loading ? (
                    <div className="flex justify-center py-10">
                        <LoadingIndicator label="Loading internal accounts..." />
                    </div>
                ) : error ? (
                    <div className="px-6 pb-6 text-sm text-error-primary">{error}</div>
                ) : (
                    <Table aria-label="Internal accounts table" sortDescriptor={sortDescriptor} onSortChange={handleSortChange}>
                        <Table.Header columns={ACCOUNT_COLUMNS}>
                            {(column) => (
                                <Table.Head allowsSorting={column.isSortable}>
                                    <span className="text-xs font-semibold text-secondary">{column.name}</span>
                                </Table.Head>
                            )}
                        </Table.Header>
                        <Table.Body items={sortedAccounts}>
                            {(account) => (
                                <Table.Row id={String(account.id)} columns={ACCOUNT_COLUMNS}>
                                    {(column) => (
                                        <Table.Cell>
                                            {column.id === "name" && <span className="text-sm text-primary">{account.name}</span>}
                                            {column.id === "type" && (
                                                <Badge size="sm" color="gray">
                                                    {typeLabelById.get(account.type ?? "none") ?? "No type"}
                                                </Badge>
                                            )}
                                            {column.id === "actions" && (
                                                <div className="flex justify-end">
                                                    <Dropdown.Root>
                                                        <Dropdown.DotsButton className="rounded-md p-1" />
                                                        <Dropdown.Popover className="w-44">
                                                            <Dropdown.Menu
                                                                onAction={(key) => {
                                                                    const action = String(key);
                                                                    if (action === "edit") {
                                                                        setEditState({
                                                                            account,
                                                                            name: account.name,
                                                                            error: null,
                                                                            isSaving: false,
                                                                        });
                                                                        return;
                                                                    }
                                                                    if (action === "remove") {
                                                                        setDeleteError(null);
                                                                        setDeleteTarget(account);
                                                                    }
                                                                }}
                                                            >
                                                                <Dropdown.Item id="edit" icon={Edit01} label="Edit" />
                                                                <Dropdown.Item id="remove" icon={Trash01} label="Remove" />
                                                            </Dropdown.Menu>
                                                        </Dropdown.Popover>
                                                    </Dropdown.Root>
                                                </div>
                                            )}
                                        </Table.Cell>
                                    )}
                                </Table.Row>
                            )}
                        </Table.Body>
                    </Table>
                )}
            </TableCard.Root>

            <ModalOverlay isOpen={createOpen} onOpenChange={(open) => !open && closeCreateModal()}>
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Create account</h4>
                                <p className="text-sm text-tertiary">Add an internal account with an optional type.</p>
                            </div>
                            <Input
                                label="Name"
                                placeholder="Savings"
                                value={createName}
                                onChange={(value) => setCreateName(value)}
                            />
                            <Select
                                label="Type"
                                items={INTERNAL_ACCOUNT_TYPE_OPTIONS}
                                selectedKey={createType}
                                onSelectionChange={(key) => key && setCreateType(String(key))}
                            >
                                {(item) => <Select.Item id={item.id} label={item.label} icon={item.icon} />}
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
                    </Dialog>
                </Modal>
            </ModalOverlay>

            <ModalOverlay isOpen={!!editState.account} onOpenChange={(open) => !open && closeEditModal()}>
                <Modal>
                    <Dialog className="max-w-md rounded-2xl bg-primary p-6 shadow-xl ring-1 ring-secondary">
                        <div className="flex flex-col gap-4">
                            <div>
                                <h4 className="text-lg font-semibold text-primary">Edit internal account</h4>
                                <p className="text-sm text-tertiary">Rename this internal account.</p>
                            </div>
                            <Input
                                label="Name"
                                placeholder="Internal account name"
                                value={editState.name}
                                onChange={(value) => setEditState((prev) => ({ ...prev, name: value }))}
                            />
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
                                        !editState.account ||
                                        !editState.name.trim() ||
                                        editState.name.trim() === editState.account.name
                                    }
                                    onClick={async () => {
                                        if (!editState.account) return;
                                        const name = editState.name.trim();
                                        if (!name) return;

                                        setEditState((prev) => ({ ...prev, isSaving: true, error: null }));
                                        try {
                                            const updated = await updateInternalAccount(editState.account.id, { name });
                                            setAccounts((prev) =>
                                                prev.map((item) => (item.id === updated.id ? updated : item)).sort((a, b) => a.position - b.position),
                                            );
                                            closeEditModal();
                                        } catch (err) {
                                            setEditState((prev) => ({
                                                ...prev,
                                                isSaving: false,
                                                error: err instanceof Error ? err.message : "Failed to update account.",
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
                                <h4 className="text-lg font-semibold text-primary">Delete internal account</h4>
                                <p className="text-sm text-tertiary">
                                    {deleteTarget
                                        ? `${deleteTarget.split_count} splits use this account. They will become unassigned.`
                                        : "This will remove the account from splits."}
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
                                                await deleteInternalAccount(deleteTarget.id);
                                                await refreshAccounts();
                                                setDeleteTarget(null);
                                            } catch (err) {
                                                setDeleteError(err instanceof Error ? err.message : "Failed to delete account.");
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

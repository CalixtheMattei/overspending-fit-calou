import { DotsHorizontal, HelpCircle, LineChartUp01, PiggyBank01, Wallet02 } from "@untitledui/icons";

export const TRANSACTION_TYPE_OPTIONS = [
    { id: "all", label: "All types" },
    { id: "expense", label: "Expense" },
    { id: "income", label: "Income" },
    { id: "transfer", label: "Transfer" },
    { id: "refund", label: "Refund" },
];

export const INTERNAL_ACCOUNT_TYPE_OPTIONS = [
    { id: "none", label: "No type", icon: HelpCircle },
    { id: "cash", label: "Cash", icon: Wallet02 },
    { id: "savings", label: "Savings", icon: PiggyBank01 },
    { id: "investments", label: "Investments", icon: LineChartUp01 },
    { id: "other", label: "Other", icon: DotsHorizontal },
];

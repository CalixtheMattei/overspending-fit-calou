export const formatDate = (value?: string | null, locale = "fr-FR") => {
    if (!value) return "-";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString(locale);
};

export const formatDateTime = (value?: string | null, locale = "fr-FR") => {
    if (!value) return "-";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" });
};

export const formatAmount = (value?: string | number | null, currency = "EUR", locale = "fr-FR") => {
    if (value === null || value === undefined || value === "") return "-";
    const numberValue = typeof value === "number" ? value : Number(value);
    if (Number.isNaN(numberValue)) return String(value);
    return new Intl.NumberFormat(locale, { style: "currency", currency }).format(numberValue);
};

export const amountClass = (value?: string | number | null) => {
    const numberValue = typeof value === "number" ? value : Number(value);
    if (Number.isNaN(numberValue) || numberValue === 0) return "text-tertiary";
    return numberValue < 0 ? "text-error-primary" : "text-success-primary";
};

export const formatPercent = (value?: number | null) => {
    if (value === null || value === undefined || Number.isNaN(value)) return "-";
    return `${value.toFixed(1)}%`;
};

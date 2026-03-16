export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
    status: number;
    detail: unknown;

    constructor(message: string, status: number, detail: unknown = null) {
        super(message);
        this.name = "ApiError";
        this.status = status;
        this.detail = detail;
    }
}

export class DemoModeError extends ApiError {
    constructor() {
        super("This action is disabled in demo mode.", 403, { demo_mode: true });
        this.name = "DemoModeError";
    }
}

type FastApiValidationError = {
    loc?: unknown;
    msg?: unknown;
};

const formatFastApiErrors = (detail: unknown) => {
    if (!Array.isArray(detail)) return null;
    const messages = detail
        .map((item) => {
            if (!item || typeof item !== "object") return null;
            const error = item as FastApiValidationError;
            const locParts = Array.isArray(error.loc) ? error.loc.map((part) => String(part)) : [];
            const loc = locParts.length ? locParts.join(".") : null;
            const msg = typeof error.msg === "string" ? error.msg : null;
            if (loc && msg) return `${loc}: ${msg}`;
            if (msg) return msg;
            return null;
        })
        .filter((value): value is string => Boolean(value));

    return messages.length ? messages.join("; ") : null;
};

export const apiFetch = async <T>(path: string, options: RequestInit = {}): Promise<T> => {
    const response = await fetch(`${API_BASE_URL}${path}`, options);

    if (!response.ok) {
        let message = "Request failed";
        let detail: unknown = null;
        try {
            const data = await response.json();
            detail = data?.detail ?? null;
            if (response.status === 403 && data?.demo_mode === true) {
                throw new DemoModeError();
            }
            if (Array.isArray(detail)) {
                message = formatFastApiErrors(detail) ?? message;
            } else if (typeof detail === "string") {
                message = detail;
            } else if (detail && typeof detail === "object" && typeof (detail as { message?: unknown }).message === "string") {
                message = String((detail as { message: unknown }).message);
            }
        } catch (error) {
            const text = await response.text();
            if (text) {
                message = text;
                detail = text;
            }
        }
        throw new ApiError(message, response.status, detail);
    }

    if (response.status === 204) {
        return null as T;
    }

    return (await response.json()) as T;
};

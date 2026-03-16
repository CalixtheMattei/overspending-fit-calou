import type { FC } from "react";
import {
    AlertCircle,
    Bell01,
    BookOpen01,
    Calendar,
    CheckCircle,
    FileCode01,
    LifeBuoy01,
    PlayCircle,
    SearchLg,
    Settings01,
    Stars02,
    UploadCloud02,
    Wallet02,
} from "@untitledui/icons";

type IconComponent = FC<{ className?: string }>;

const FALLBACK_ICON = SearchLg;

const normalizeCategoryIconKey = (iconKey: string | null | undefined): string =>
    (iconKey || "")
        .replace(/([a-z0-9])([A-Z])/g, "$1-$2")
        .replace(/[_\s]+/g, "-")
        .replace(/[^a-zA-Z0-9-]+/g, "-")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "")
        .toLowerCase();

const ICON_COMPONENT_BY_KEY = new Map<string, IconComponent>();

const registerCategoryIconAliases = (icon: IconComponent, keys: string[]) => {
    for (const key of keys) {
        ICON_COMPONENT_BY_KEY.set(normalizeCategoryIconKey(key), icon);
    }
};

registerCategoryIconAliases(Wallet02, [
    "arrow-down",
    "arrow-trend-up",
    "bank",
    "bitcoin-sign",
    "building-columns",
    "chart-candlestick",
    "chart-line-up",
    "circle-dollar-to-slot",
    "coins",
    "envelope-open-dollar",
    "hand-holding-dollar",
    "landmark",
    "money-bill-transfer",
    "money-bill-wave",
    "money-check",
    "money-from-bracket",
    "piggyBank",
    "sack-dollar",
    "vault",
]);

registerCategoryIconAliases(Settings01, [
    "briefcase",
    "briefcase-arrow-right",
    "building",
    "building-user",
    "business-time",
    "calculator-simple",
    "clothes-hanger",
    "garage",
    "hammer",
    "heat",
    "home",
    "house-building",
    "house-crack",
    "jug-detergent",
    "legal",
    "phone-office",
    "shirt",
    "user-tie",
    "users",
]);

registerCategoryIconAliases(Calendar, [
    "bus",
    "car",
    "car-building",
    "car-wash",
    "car-wrench",
    "carSide",
    "cars",
    "clock",
    "earth",
    "gas-pump",
    "globe",
    "motorcycle",
    "parking",
    "plane",
    "taxi",
    "train",
    "truck",
]);

registerCategoryIconAliases(BookOpen01, [
    "books",
    "graduation-cap",
    "paperclip",
    "school",
    "user-graduate",
]);

registerCategoryIconAliases(FileCode01, [
    "box-taped",
    "file-contract",
    "file-invoice",
    "files",
    "print",
    "tag",
]);

registerCategoryIconAliases(UploadCloud02, [
    "bolt",
    "droplet",
    "laptop",
    "mobile",
    "server",
]);

registerCategoryIconAliases(PlayCircle, [
    "beer-mug",
    "burger",
    "burger-soda",
    "cake",
    "cameraMovie",
    "cocktail",
    "cookie-bite",
    "cup-togo",
    "football",
    "gamepadModern",
    "headphones",
    "masks-theater",
    "palette",
    "popcorn",
    "salad",
    "sportsball",
    "umbrella-beach",
    "umbrellaBeach",
    "utensils",
    "wineGlass",
]);

registerCategoryIconAliases(LifeBuoy01, [
    "baby",
    "bandage",
    "capsules",
    "eye",
    "files-medical",
    "hand-heart",
    "medkit",
    "paw",
    "pawSimple",
    "stethoscope",
    "tooth",
    "user-doctor",
]);

registerCategoryIconAliases(Stars02, ["bullseye-pointer", "gift", "gifts", "seedling"]);
registerCategoryIconAliases(CheckCircle, ["badgeCheck", "shield-quartered"]);
registerCategoryIconAliases(Bell01, ["bell-concierge", "megaphone"]);
registerCategoryIconAliases(AlertCircle, ["circle-question", "smoking", "wine-glass-crack"]);

export type CategoryIconResolution = {
    Icon: IconComponent;
    isFallback: boolean;
    normalizedKey: string;
};

export const resolveCategoryIconInfo = (iconKey: string | null | undefined): CategoryIconResolution => {
    const normalizedKey = normalizeCategoryIconKey(iconKey);
    const Icon = normalizedKey ? ICON_COMPONENT_BY_KEY.get(normalizedKey) : undefined;
    return {
        Icon: Icon ?? FALLBACK_ICON,
        isFallback: !Icon,
        normalizedKey,
    };
};

export const resolveCategoryIcon = (iconKey: string | null | undefined): IconComponent => resolveCategoryIconInfo(iconKey).Icon;

const CATEGORY_LABEL_OVERRIDES: Record<string, string> = {
    cryptos: "Crypto",
    real_estates: "Real Estate",
};

const ACRONYM_TOKENS = new Set(["vat", "sepa"]);

const toTitleCaseToken = (token: string): string => {
    if (!token) return token;
    if (ACRONYM_TOKENS.has(token.toLowerCase())) {
        return token.toUpperCase();
    }
    return token.charAt(0).toUpperCase() + token.slice(1).toLowerCase();
};

export const formatCategoryValue = (value: string): string => {
    const raw = (value || "").trim();
    if (!raw) return "";

    const normalizedKey = raw.toLowerCase();
    if (CATEGORY_LABEL_OVERRIDES[normalizedKey]) {
        return CATEGORY_LABEL_OVERRIDES[normalizedKey];
    }

    const normalized = raw
        .replace(/[_-]+/g, " ")
        .replace(/([a-z])([A-Z])/g, "$1 $2")
        .replace(/\s+/g, " ")
        .trim();

    if (!normalized) {
        return "";
    }
    return normalized
        .split(" ")
        .map((token) => toTitleCaseToken(token))
        .join(" ");
};

export const getCategoryDisplayLabel = (category: { name: string; display_name?: string | null } | null | undefined): string => {
    if (!category) return "";
    const displayName = category.display_name?.trim();
    if (displayName) {
        return displayName;
    }
    return formatCategoryValue(category.name) || category.name;
};

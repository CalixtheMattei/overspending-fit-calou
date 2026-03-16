import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AppShell } from "@/components/layouts/app-shell";
import { UserProfileProvider } from "@/features/profile/profile-provider";
import { AnalyticsPage } from "@/pages/analytics-page";
import { CategoryDrilldownPage } from "@/pages/category-drilldown-page";
import { LedgerDashboardPage } from "@/pages/ledger/dashboard-page";
import { CategoriesPage } from "@/pages/ledger/categories-page";
import { InternalAccountsPage } from "@/pages/ledger/internal-accounts-page";
import { PayeesPage } from "@/pages/ledger/payees-page";
import { ImportsPage } from "@/pages/imports-page";
import { MomentsPage } from "@/pages/moments-page";
import { NotFound } from "@/pages/not-found";
import { ProfilePage } from "@/pages/profile-page";
import { RulesPage } from "@/pages/rules-page";
import { RouteProvider } from "@/providers/router-provider";
import { ThemeProvider } from "@/providers/theme-provider";
import "@/styles/globals.css";

createRoot(document.getElementById("root")!).render(
    <StrictMode>
        <ThemeProvider>
            <BrowserRouter>
                <UserProfileProvider>
                    <RouteProvider>
                        <Routes>
                            <Route path="/" element={<AppShell />}>
                                <Route index element={<Navigate to="/imports" replace />} />
                                <Route path="imports" element={<ImportsPage />} />
                                <Route path="imports/:importId" element={<ImportsPage />} />
                                <Route path="inbox" element={<Navigate to="/ledger" replace />} />
                                <Route path="ledger">
                                    <Route index element={<LedgerDashboardPage />} />
                                    <Route path="dashboard" element={<LedgerDashboardPage />} />
                                    <Route path="payees" element={<PayeesPage />} />
                                    <Route path="internal-accounts" element={<InternalAccountsPage />} />
                                    <Route path="categories" element={<CategoriesPage />} />
                                </Route>
                                <Route path="rules" element={<RulesPage />} />
                                <Route path="analytics" element={<AnalyticsPage />} />
                                <Route path="analytics/category/:categoryRef" element={<CategoryDrilldownPage />} />
                                <Route path="moments" element={<MomentsPage />} />
                                <Route path="profile" element={<ProfilePage />} />
                            </Route>
                            <Route path="*" element={<NotFound />} />
                        </Routes>
                    </RouteProvider>
                </UserProfileProvider>
            </BrowserRouter>
        </ThemeProvider>
    </StrictMode>,
);

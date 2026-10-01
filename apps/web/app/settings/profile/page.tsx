import type { Metadata } from "next";
import { Suspense } from "react";

import { ProfileView } from "@/features/profile/profile-view";

export const metadata: Metadata = { title: "Profile & resume · RoleRadarAI" };

export default function ProfilePage() {
  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold tracking-tight">Profile &amp; resume</h1>
        <p className="text-sm text-muted">
          Your master resume is the evidence for every match. Files are stored privately on this
          machine.
        </p>
      </header>
      <Suspense fallback={<p className="text-sm text-muted">Loading profile…</p>}>
        <ProfileView />
      </Suspense>
    </section>
  );
}

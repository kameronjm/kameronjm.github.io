"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type EVOpportunity, type Fixture } from "@/lib/api";

export default function Dashboard() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [opportunities, setOpportunities] = useState<EVOpportunity[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([api.getFixtures(), api.getEVOpportunities()])
      .then(([f, o]) => {
        if (f.status === "fulfilled") setFixtures(f.value);
        if (o.status === "fulfilled") setOpportunities(o.value);
      })
      .finally(() => setLoading(false));
  }, []);

  const topOpps = opportunities.slice(0, 5);

  return (
    <>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="mt-1 text-gray-400">Real-time sports analytics overview</p>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active Fixtures" value={loading ? "..." : fixtures.length} />
        <StatCard label="+EV Opportunities" value={loading ? "..." : opportunities.length} color="emerald" />
        <StatCard
          label="Best Edge"
          value={loading ? "..." : opportunities.length > 0 ? `${opportunities[0].ev_percentage.toFixed(1)}%` : "—"}
          color="amber"
        />
        <StatCard
          label="Avg Edge"
          value={
            loading
              ? "..."
              : opportunities.length > 0
                ? `${(opportunities.reduce((s, o) => s + o.ev_percentage, 0) / opportunities.length).toFixed(1)}%`
                : "—"
          }
        />
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Top +EV Opportunities</h2>
            <Link href="/opportunities" className="text-sm text-brand-400 hover:text-brand-300">
              View all &rarr;
            </Link>
          </div>
          {loading ? (
            <Skeleton rows={5} />
          ) : topOpps.length === 0 ? (
            <p className="py-8 text-center text-gray-500">No opportunities found yet. The engine is scanning...</p>
          ) : (
            <div className="space-y-3">
              {topOpps.map((o) => (
                <div key={o.id} className="flex items-center justify-between rounded-lg bg-gray-800/50 px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">{o.selection}</p>
                    <p className="text-xs text-gray-400">
                      {o.home_team} vs {o.away_team} &middot; {o.sportsbook}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="badge-green">+{o.ev_percentage.toFixed(1)}% EV</p>
                    <p className="mt-1 text-xs text-gray-400">
                      {o.odds_american > 0 ? "+" : ""}{o.odds_american}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Today&apos;s Fixtures</h2>
            <span className="text-sm text-gray-400">{fixtures.length} games</span>
          </div>
          {loading ? (
            <Skeleton rows={5} />
          ) : fixtures.length === 0 ? (
            <p className="py-8 text-center text-gray-500">No fixtures loaded yet.</p>
          ) : (
            <div className="space-y-3">
              {fixtures.slice(0, 6).map((f) => (
                <div key={f.id} className="flex items-center justify-between rounded-lg bg-gray-800/50 px-4 py-3">
                  <div>
                    <p className="text-sm font-medium">
                      {f.away_team} <span className="text-gray-500">@</span> {f.home_team}
                    </p>
                    <p className="text-xs text-gray-400">
                      {f.league_code} &middot; {new Date(f.scheduled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </p>
                  </div>
                  <span className={`text-xs font-medium ${f.status === "scheduled" ? "text-gray-400" : "text-emerald-400"}`}>
                    {f.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <QuickAction
          title="Train a Model"
          description="Select features and build a custom ML model for any league"
          href="/models"
          cta="Open Model Builder"
        />
        <QuickAction
          title="+EV Scanner"
          description="Browse all positive expected value betting opportunities"
          href="/opportunities"
          cta="View Opportunities"
        />
        <QuickAction
          title="Portfolio Tracker"
          description="Track your simulated bankroll and placed bets"
          href="/portfolio"
          cta="Manage Portfolio"
        />
      </div>
    </>
  );
}

function StatCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  const colorMap: Record<string, string> = {
    emerald: "text-emerald-400",
    amber: "text-amber-400",
    red: "text-red-400",
  };
  return (
    <div className="card">
      <p className="stat-label">{label}</p>
      <p className={`stat-value mt-1 ${colorMap[color ?? ""] ?? "text-white"}`}>{value}</p>
    </div>
  );
}

function QuickAction({ title, description, href, cta }: { title: string; description: string; href: string; cta: string }) {
  return (
    <div className="card flex flex-col justify-between">
      <div>
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-gray-400">{description}</p>
      </div>
      <Link href={href} className="btn-primary mt-4 text-center">
        {cta}
      </Link>
    </div>
  );
}

function Skeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-14 animate-pulse rounded-lg bg-gray-800/50" />
      ))}
    </div>
  );
}

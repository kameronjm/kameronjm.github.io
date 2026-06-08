"use client";

import { useEffect, useState } from "react";
import { api, type EVOpportunity } from "@/lib/api";

export default function OpportunitiesPage() {
  const [opportunities, setOpportunities] = useState<EVOpportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [minEv, setMinEv] = useState(0);
  const [marketFilter, setMarketFilter] = useState("all");

  useEffect(() => {
    setLoading(true);
    api.getEVOpportunities(minEv).then(setOpportunities).catch(() => {}).finally(() => setLoading(false));
  }, [minEv]);

  const filtered = marketFilter === "all" ? opportunities : opportunities.filter((o) => o.market_type === marketFilter);
  const markets = [...new Set(opportunities.map((o) => o.market_type))];

  return (
    <>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">+EV Opportunities</h1>
        <p className="mt-1 text-gray-400">
          Live positive expected value bets across all sportsbooks
        </p>
      </div>

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">Min EV %</label>
          <input
            type="number"
            className="input-field w-28"
            value={minEv}
            step={0.5}
            min={0}
            onChange={(e) => setMinEv(Number(e.target.value))}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-gray-400">Market Type</label>
          <select className="select-field w-40" value={marketFilter} onChange={(e) => setMarketFilter(e.target.value)}>
            <option value="all">All Markets</option>
            {markets.map((m) => <option key={m} value={m}>{m.replace("_", " ")}</option>)}
          </select>
        </div>
        <div className="ml-auto text-sm text-gray-400">
          {filtered.length} opportunit{filtered.length === 1 ? "y" : "ies"}
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-gray-900 border border-gray-800" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-16">
          <svg className="h-12 w-12 text-gray-700" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
          </svg>
          <p className="mt-4 text-gray-500">No +EV opportunities found. Try lowering the minimum EV threshold.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((o) => (
            <div key={o.id} className="card flex items-center gap-6">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-3">
                  <h3 className="text-sm font-semibold truncate">{o.selection}</h3>
                  <span className="badge-green">+{o.ev_percentage.toFixed(1)}% EV</span>
                </div>
                <p className="mt-1 text-sm text-gray-400">
                  {o.home_team} vs {o.away_team}
                </p>
              </div>

              <div className="hidden sm:grid grid-cols-4 gap-6 text-center flex-shrink-0">
                <div>
                  <p className="stat-label">Sportsbook</p>
                  <p className="mt-0.5 text-sm font-medium">{o.sportsbook}</p>
                </div>
                <div>
                  <p className="stat-label">Market</p>
                  <p className="mt-0.5 text-sm font-medium">{o.market_type.replace("_", " ")}</p>
                </div>
                <div>
                  <p className="stat-label">Odds</p>
                  <p className="mt-0.5 text-sm font-bold">
                    {o.odds_american > 0 ? "+" : ""}{o.odds_american}
                  </p>
                </div>
                <div>
                  <p className="stat-label">Edge</p>
                  <p className={`mt-0.5 text-sm font-bold ${o.edge > 0.05 ? "text-emerald-400" : "text-amber-400"}`}>
                    {(o.edge * 100).toFixed(1)}%
                  </p>
                </div>
              </div>

              <div className="hidden lg:block text-center flex-shrink-0 w-32">
                <p className="stat-label">Fair Prob</p>
                <div className="mt-1 h-2 w-full rounded-full bg-gray-800">
                  <div
                    className="h-2 rounded-full bg-brand-500"
                    style={{ width: `${o.fair_probability * 100}%` }}
                  />
                </div>
                <p className="mt-0.5 text-xs text-gray-400">
                  {(o.fair_probability * 100).toFixed(0)}% vs {(o.implied_probability * 100).toFixed(0)}%
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}

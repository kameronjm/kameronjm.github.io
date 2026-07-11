"use client";

import { useEffect, useState } from "react";
import { api, type Portfolio } from "@/lib/api";

export default function PortfolioPage() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [portfolioId, setPortfolioId] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");

  const [newName, setNewName] = useState("My Portfolio");
  const [newBalance, setNewBalance] = useState(10000);
  const [showCreate, setShowCreate] = useState(true);

  useEffect(() => {
    const saved = localStorage.getItem("portfolio_id");
    if (saved) {
      setPortfolioId(saved);
      setShowCreate(false);
      loadPortfolio(saved);
    }
  }, []);

  async function loadPortfolio(id: string) {
    setLoading(true);
    setError("");
    try {
      const p = await api.getPortfolio(id);
      setPortfolio(p);
      setShowCreate(false);
    } catch {
      setError("Portfolio not found. Create a new one.");
      setShowCreate(true);
      localStorage.removeItem("portfolio_id");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate() {
    setCreating(true);
    setError("");
    try {
      const p = await api.createPortfolio({
        starting_balance: newBalance,
        currency: "USD",
        name: newName,
      });
      setPortfolio(p);
      setPortfolioId(p.id);
      localStorage.setItem("portfolio_id", p.id);
      setShowCreate(false);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create portfolio");
    } finally {
      setCreating(false);
    }
  }

  const pnlColor = (portfolio?.total_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-red-400";
  const pnlSign = (portfolio?.total_pnl ?? 0) >= 0 ? "+" : "";
  const balancePct = portfolio
    ? ((portfolio.current_balance / portfolio.starting_balance) * 100 - 100).toFixed(1)
    : "0";

  return (
    <>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Portfolio</h1>
        <p className="mt-1 text-gray-400">Simulated bankroll and betting performance</p>
      </div>

      {showCreate ? (
        <div className="mx-auto max-w-md">
          <div className="card">
            <h2 className="mb-4 text-lg font-semibold">Create Portfolio</h2>
            <div className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-400">Portfolio Name</label>
                <input
                  className="input-field"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-400">Starting Balance ($)</label>
                <input
                  type="number"
                  className="input-field"
                  value={newBalance}
                  min={1}
                  onChange={(e) => setNewBalance(Number(e.target.value))}
                />
              </div>
              {error && <p className="text-sm text-red-400">{error}</p>}
              <button onClick={handleCreate} disabled={creating} className="btn-primary w-full">
                {creating ? "Creating..." : "Create Portfolio"}
              </button>
            </div>

            <div className="mt-6 border-t border-gray-800 pt-4">
              <p className="mb-2 text-xs text-gray-500">Or load an existing portfolio by ID:</p>
              <div className="flex gap-2">
                <input
                  className="input-field flex-1 font-mono text-xs"
                  placeholder="portfolio UUID"
                  value={portfolioId}
                  onChange={(e) => setPortfolioId(e.target.value)}
                />
                <button
                  onClick={() => loadPortfolio(portfolioId)}
                  disabled={!portfolioId}
                  className="btn-secondary"
                >
                  Load
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : loading ? (
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 animate-pulse rounded-xl bg-gray-900 border border-gray-800" />
          ))}
        </div>
      ) : portfolio ? (
        <>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <div className="card">
              <p className="stat-label">Current Balance</p>
              <p className="stat-value mt-1 text-white">
                ${portfolio.current_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
              <p className={`mt-1 text-xs font-medium ${Number(balancePct) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {Number(balancePct) >= 0 ? "+" : ""}{balancePct}% from start
              </p>
            </div>
            <div className="card">
              <p className="stat-label">Total P&L</p>
              <p className={`stat-value mt-1 ${pnlColor}`}>
                {pnlSign}${Math.abs(portfolio.total_pnl).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="card">
              <p className="stat-label">Total Bets</p>
              <p className="stat-value mt-1 text-white">{portfolio.total_bets}</p>
            </div>
            <div className="card">
              <p className="stat-label">Win Rate</p>
              <p className={`stat-value mt-1 ${portfolio.win_rate > 52 ? "text-emerald-400" : portfolio.win_rate > 0 ? "text-amber-400" : "text-gray-400"}`}>
                {portfolio.win_rate}%
              </p>
            </div>
          </div>

          <div className="mt-6 card">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">{portfolio.name}</h2>
                <p className="text-xs text-gray-500 font-mono">{portfolio.id}</p>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-400">Started</p>
                <p className="text-sm font-medium">
                  {new Date(portfolio.created_at).toLocaleDateString()}
                </p>
              </div>
            </div>

            <div className="mt-6 rounded-lg bg-gray-800/50 p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-400">Starting Balance</p>
                  <p className="text-lg font-bold">${portfolio.starting_balance.toLocaleString()}</p>
                </div>
                <svg className="h-6 w-6 text-gray-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M17.25 8.25L21 12m0 0l-3.75 3.75M21 12H3" />
                </svg>
                <div className="text-right">
                  <p className="text-sm text-gray-400">Current Balance</p>
                  <p className={`text-lg font-bold ${pnlColor}`}>
                    ${portfolio.current_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 flex gap-3">
            <button
              onClick={() => loadPortfolio(portfolio.id)}
              className="btn-secondary"
            >
              Refresh
            </button>
            <button
              onClick={() => {
                setShowCreate(true);
                setPortfolio(null);
                localStorage.removeItem("portfolio_id");
              }}
              className="btn-secondary"
            >
              Switch Portfolio
            </button>
          </div>
        </>
      ) : null}
    </>
  );
}

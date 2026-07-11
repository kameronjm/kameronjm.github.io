"use client";

import { useState } from "react";
import { api, type TrainResponse, type BacktestResponse } from "@/lib/api";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const LEAGUES = ["NBA", "NFL", "MLB"];
const TARGET_TYPES = ["regression", "classification"];

const FEATURES_BY_CATEGORY: Record<string, string[]> = {
  Offense: [
    "points", "field_goals_made", "field_goals_attempted", "field_goal_pct",
    "three_pointers_made", "three_pointers_attempted", "three_point_pct",
    "free_throws_made", "free_throws_attempted", "free_throw_pct",
    "total_yards", "passing_yards", "rushing_yards", "hits", "runs", "rbi",
  ],
  Defense: [
    "rebounds", "offensive_rebounds", "defensive_rebounds", "steals", "blocks",
    "turnovers", "sacks", "interceptions", "errors",
  ],
  Playmaking: [
    "assists", "assist_to_turnover_ratio",
  ],
  Advanced: [
    "pace", "offensive_rating", "defensive_rating", "true_shooting_pct",
    "effective_fg_pct", "usage_rate",
  ],
  "Opponent (mirrored)": [
    "Opponent points", "Opponent rebounds", "Opponent assists",
    "Opponent field_goal_pct", "Opponent three_point_pct", "Opponent turnovers",
    "Opponent steals", "Opponent blocks",
  ],
  "Starting Pitcher": [
    "Starting Pitcher era", "Starting Pitcher whip",
    "Starting Pitcher strikeouts", "Starting Pitcher innings_pitched",
    "Starting Pitcher hits_allowed", "Starting Pitcher walks",
  ],
};

export default function ModelBuilderPage() {
  const [league, setLeague] = useState("NBA");
  const [targetVariable, setTargetVariable] = useState("total_points");
  const [targetType, setTargetType] = useState("regression");
  const [rollingWindow, setRollingWindow] = useState(10);
  const [modelName, setModelName] = useState("");
  const [selectedFeatures, setSelectedFeatures] = useState<Set<string>>(new Set());

  const [training, setTraining] = useState(false);
  const [trainResult, setTrainResult] = useState<TrainResponse | null>(null);
  const [trainError, setTrainError] = useState("");

  const [backtesting, setBacktesting] = useState(false);
  const [btResult, setBtResult] = useState<BacktestResponse | null>(null);
  const [btStart, setBtStart] = useState("2025-01-01");
  const [btEnd, setBtEnd] = useState("2026-06-01");
  const [btThreshold, setBtThreshold] = useState(3.0);

  function toggleFeature(f: string) {
    setSelectedFeatures((prev) => {
      const next = new Set(prev);
      if (next.has(f)) next.delete(f);
      else next.add(f);
      return next;
    });
  }

  function selectAll(features: string[]) {
    setSelectedFeatures((prev) => {
      const next = new Set(prev);
      features.forEach((f) => next.add(f));
      return next;
    });
  }

  function clearAll() {
    setSelectedFeatures(new Set());
  }

  async function handleTrain() {
    if (selectedFeatures.size === 0) return;
    setTraining(true);
    setTrainError("");
    setTrainResult(null);
    setBtResult(null);
    try {
      const result = await api.trainModel({
        league,
        target_variable: targetVariable,
        target_type: targetType,
        feature_list: Array.from(selectedFeatures),
        rolling_window: rollingWindow,
        name: modelName || undefined,
      });
      setTrainResult(result);
    } catch (e: unknown) {
      setTrainError(e instanceof Error ? e.message : "Training failed");
    } finally {
      setTraining(false);
    }
  }

  async function handleBacktest() {
    if (!trainResult) return;
    setBacktesting(true);
    try {
      const result = await api.runBacktest(trainResult.model_id, {
        start_date: new Date(btStart).toISOString(),
        end_date: new Date(btEnd).toISOString(),
        ev_threshold: btThreshold,
        unit_size: 1.0,
      });
      setBtResult(result);
    } catch {
      setBtResult(null);
    } finally {
      setBacktesting(false);
    }
  }

  return (
    <>
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Model Builder</h1>
        <p className="mt-1 text-gray-400">
          Train custom ML models with dynamic feature selection
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Left column: Configuration */}
        <div className="space-y-6 xl:col-span-2">
          {/* Model Configuration */}
          <div className="card">
            <h2 className="mb-4 text-lg font-semibold">Configuration</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-400">League</label>
                <select className="select-field" value={league} onChange={(e) => setLeague(e.target.value)}>
                  {LEAGUES.map((l) => <option key={l}>{l}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-400">Target Variable</label>
                <input
                  className="input-field"
                  value={targetVariable}
                  onChange={(e) => setTargetVariable(e.target.value)}
                  placeholder="e.g. total_points"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-400">Model Type</label>
                <select className="select-field" value={targetType} onChange={(e) => setTargetType(e.target.value)}>
                  {TARGET_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-400">
                  Rolling Window: {rollingWindow}
                </label>
                <input
                  type="range"
                  min={3}
                  max={50}
                  value={rollingWindow}
                  onChange={(e) => setRollingWindow(Number(e.target.value))}
                  className="mt-2 w-full accent-brand-500"
                />
              </div>
            </div>
            <div className="mt-4">
              <label className="mb-1 block text-xs font-medium text-gray-400">
                Model Name <span className="text-gray-600">(optional)</span>
              </label>
              <input
                className="input-field max-w-md"
                value={modelName}
                onChange={(e) => setModelName(e.target.value)}
                placeholder="Auto-generated if blank"
              />
            </div>
          </div>

          {/* Feature Selection */}
          <div className="card">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold">Feature Selection</h2>
                <p className="text-sm text-gray-400">
                  {selectedFeatures.size} feature{selectedFeatures.size !== 1 ? "s" : ""} selected
                </p>
              </div>
              <button onClick={clearAll} className="text-xs text-gray-400 hover:text-gray-200">
                Clear all
              </button>
            </div>

            <div className="space-y-4">
              {Object.entries(FEATURES_BY_CATEGORY).map(([category, features]) => (
                <div key={category}>
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-300">{category}</h3>
                    <button
                      onClick={() => selectAll(features)}
                      className="text-xs text-brand-400 hover:text-brand-300"
                    >
                      Select all
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {features.map((f) => (
                      <button
                        key={f}
                        onClick={() => toggleFeature(f)}
                        className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                          selectedFeatures.has(f)
                            ? "bg-brand-600/20 text-brand-400 ring-1 ring-brand-500/30"
                            : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
                        }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-6">
              <button
                onClick={handleTrain}
                disabled={training || selectedFeatures.size === 0}
                className="btn-primary w-full sm:w-auto"
              >
                {training ? (
                  <span className="flex items-center justify-center gap-2">
                    <Spinner /> Training Model...
                  </span>
                ) : (
                  `Train Model (${selectedFeatures.size} features)`
                )}
              </button>
              {trainError && (
                <p className="mt-3 text-sm text-red-400">{trainError}</p>
              )}
            </div>
          </div>
        </div>

        {/* Right column: Results */}
        <div className="space-y-6">
          {/* Training Results */}
          <div className="card">
            <h2 className="mb-4 text-lg font-semibold">Training Results</h2>
            {trainResult ? (
              <div className="space-y-4">
                <div className="rounded-lg bg-gray-800/50 p-4">
                  <p className="text-sm font-medium text-gray-300">{trainResult.name}</p>
                  <p className="mt-0.5 text-xs text-gray-500 font-mono">{trainResult.model_id}</p>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <MetricBox
                    label="R-Value"
                    value={trainResult.r_value?.toFixed(4) ?? "—"}
                    quality={trainResult.r_value && trainResult.r_value > 0.5 ? "good" : trainResult.r_value && trainResult.r_value > 0.3 ? "ok" : "bad"}
                  />
                  <MetricBox
                    label="Test Loss"
                    value={trainResult.test_loss?.toFixed(4) ?? "—"}
                  />
                  <MetricBox
                    label="Train Samples"
                    value={trainResult.train_samples?.toLocaleString() ?? "—"}
                  />
                  <MetricBox
                    label="Test Samples"
                    value={trainResult.test_samples?.toLocaleString() ?? "—"}
                  />
                </div>
                <MetricBox
                  label="Features Used"
                  value={String(trainResult.feature_count)}
                />
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="rounded-full bg-gray-800 p-4">
                  <svg className="h-8 w-8 text-gray-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                </div>
                <p className="mt-3 text-sm text-gray-500">
                  Select features and train a model to see results
                </p>
              </div>
            )}
          </div>

          {/* Backtest */}
          {trainResult && (
            <div className="card">
              <h2 className="mb-4 text-lg font-semibold">Backtest</h2>
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-400">Start Date</label>
                    <input type="date" className="input-field" value={btStart} onChange={(e) => setBtStart(e.target.value)} />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-gray-400">End Date</label>
                    <input type="date" className="input-field" value={btEnd} onChange={(e) => setBtEnd(e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-gray-400">EV Threshold (%)</label>
                  <input
                    type="number"
                    className="input-field"
                    value={btThreshold}
                    step={0.5}
                    min={0}
                    onChange={(e) => setBtThreshold(Number(e.target.value))}
                  />
                </div>
                <button
                  onClick={handleBacktest}
                  disabled={backtesting}
                  className="btn-secondary w-full"
                >
                  {backtesting ? (
                    <span className="flex items-center justify-center gap-2">
                      <Spinner /> Running Backtest...
                    </span>
                  ) : (
                    "Run Backtest"
                  )}
                </button>
              </div>

              {btResult && (
                <div className="mt-5 space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <MetricBox label="ROI" value={`${btResult.roi_percentage}%`} quality={btResult.roi_percentage > 0 ? "good" : "bad"} />
                    <MetricBox label="Win Rate" value={`${btResult.win_percentage}%`} quality={btResult.win_percentage > 52 ? "good" : "bad"} />
                    <MetricBox label="Total Bets" value={String(btResult.total_bets)} />
                    <MetricBox label="Net Units" value={btResult.net_units.toFixed(2)} quality={btResult.net_units > 0 ? "good" : "bad"} />
                    <MetricBox label="Record" value={`${btResult.wins}W - ${btResult.losses}L`} />
                    <MetricBox label="Max Drawdown" value={`${btResult.max_drawdown}%`} quality={btResult.max_drawdown < 20 ? "good" : "bad"} />
                  </div>

                  {btResult.bankroll_history.length > 1 && (
                    <div className="mt-4">
                      <p className="mb-2 text-xs font-medium text-gray-400">Bankroll Curve</p>
                      <div className="h-48 w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <LineChart
                            data={btResult.bankroll_history.map((v, i) => ({ bet: i, balance: v }))}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                            <XAxis dataKey="bet" tick={{ fontSize: 10, fill: "#6b7280" }} />
                            <YAxis tick={{ fontSize: 10, fill: "#6b7280" }} domain={["dataMin - 5", "dataMax + 5"]} />
                            <Tooltip
                              contentStyle={{ backgroundColor: "#111827", border: "1px solid #374151", borderRadius: "8px" }}
                              labelStyle={{ color: "#9ca3af" }}
                              itemStyle={{ color: "#60a5fa" }}
                            />
                            <Line
                              type="monotone"
                              dataKey="balance"
                              stroke="#3b82f6"
                              strokeWidth={2}
                              dot={false}
                            />
                          </LineChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function MetricBox({ label, value, quality }: { label: string; value: string; quality?: "good" | "ok" | "bad" }) {
  const colorMap = { good: "text-emerald-400", ok: "text-amber-400", bad: "text-red-400" };
  return (
    <div className="rounded-lg bg-gray-800/50 px-3 py-2.5">
      <p className="stat-label">{label}</p>
      <p className={`mt-0.5 text-lg font-bold ${quality ? colorMap[quality] : "text-white"}`}>{value}</p>
    </div>
  );
}

function Spinner() {
  return (
    <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

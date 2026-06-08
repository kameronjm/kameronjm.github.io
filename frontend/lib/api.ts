const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export interface EVOpportunity {
  id: string;
  fixture_id: string;
  home_team: string;
  away_team: string;
  sportsbook: string;
  market_type: string;
  selection: string;
  odds_american: number;
  implied_probability: number;
  fair_probability: number;
  edge: number;
  ev_percentage: number;
  discovered_at: string;
  recommended_kelly_wager: number | null;
}

export interface TrainResponse {
  model_id: string;
  config_id: string;
  name: string;
  r_value: number | null;
  test_loss: number | null;
  train_samples: number | null;
  test_samples: number | null;
  feature_count: number;
}

export interface BacktestResponse {
  model_id: string;
  total_bets: number;
  wins: number;
  losses: number;
  net_units: number;
  win_percentage: number;
  roi_percentage: number;
  max_drawdown: number;
  bankroll_history: number[];
}

export interface Portfolio {
  id: string;
  name: string;
  starting_balance: number;
  current_balance: number;
  currency: string;
  total_bets: number;
  total_pnl: number;
  win_rate: number;
  created_at: string;
}

export interface PlacedBet {
  id: string;
  portfolio_id: string;
  ev_opportunity_id: string;
  stake_amount: number;
  odds_taken: number;
  status: string;
  remaining_balance: number;
  kelly_fraction_used: number | null;
}

export interface Fixture {
  id: string;
  league_code: string;
  home_team: string;
  away_team: string;
  scheduled_at: string;
  status: string;
  season: string;
  home_score: number | null;
  away_score: number | null;
}

export const api = {
  getFixtures: (league?: string) =>
    request<Fixture[]>(`/fixtures${league ? `?league=${league}` : ""}`),

  getEVOpportunities: (minEv = 0, portfolioId?: string) => {
    const params = new URLSearchParams({ min_ev: String(minEv) });
    if (portfolioId) params.set("portfolio_id", portfolioId);
    return request<EVOpportunity[]>(`/ev-opportunities?${params}`);
  },

  trainModel: (body: {
    league: string;
    target_variable: string;
    target_type: string;
    feature_list: string[];
    rolling_window: number;
    name?: string;
  }) => request<TrainResponse>("/models/train", { method: "POST", body: JSON.stringify(body) }),

  runBacktest: (
    modelId: string,
    body: { start_date: string; end_date: string; ev_threshold: number; unit_size: number }
  ) =>
    request<BacktestResponse>(`/models/${modelId}/backtest`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  createPortfolio: (body: { starting_balance: number; currency: string; name: string }) =>
    request<Portfolio>("/portfolio", { method: "POST", body: JSON.stringify(body) }),

  getPortfolio: (id: string) => request<Portfolio>(`/portfolio/${id}`),

  placeBet: (body: {
    portfolio_id: string;
    ev_opportunity_id: string;
    kelly_fraction?: number;
    override_stake?: number;
  }) => request<PlacedBet>("/portfolio/bet", { method: "POST", body: JSON.stringify(body) }),
};

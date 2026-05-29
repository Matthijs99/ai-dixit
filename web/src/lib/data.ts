import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = resolve(here, '../../../data');

export interface ModelStats {
  display_name: string;
  org: string;
  games: number;
  wins: number;
  // Total final-score points across this model's own games. Points-per-game
  // (points / games) is the ranking metric, derived at render.
  points: number;
  // Set on models no longer in the active roster. Kept in stats.json so past
  // games still resolve; shown in a separate "Retired" section on the
  // leaderboard rather than the main ranking.
  retired?: boolean;
}

export interface StatsDoc {
  updated_at: string;
  models: Record<string, ModelStats>;
}

export interface IndexRow {
  game_id: string;
  date: string;
  status: 'complete' | 'errored' | 'turn_limit';
  winner: string | null;
  turns: number;
  final_scores: Record<string, number>;
}

export interface TurnRecord {
  turn: number;
  storyteller: string;
  clue: string | null;
  storyteller_card: number | null;
  submissions: Record<string, number>;
  face_up_order: number[];
  votes: Record<string, number>;
  scores_delta: Record<string, number>;
  scores_total: Record<string, number>;
  degraded: string[];
}

export interface GameDoc {
  game_id: string;
  status: string;
  started_at: string;
  ended_at: string;
  seed: string;
  players: string[];
  turns: TurnRecord[];
  final_scores: Record<string, number>;
}

export function loadStats(): StatsDoc {
  return JSON.parse(readFileSync(resolve(dataDir, 'stats.json'), 'utf-8'));
}

export function loadIndex(): IndexRow[] {
  return JSON.parse(readFileSync(resolve(dataDir, 'index.json'), 'utf-8'));
}

export function loadGame(gameId: string): GameDoc {
  return JSON.parse(readFileSync(resolve(dataDir, 'games', `${gameId}.json`), 'utf-8'));
}

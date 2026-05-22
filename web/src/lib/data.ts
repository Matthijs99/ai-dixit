import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = resolve(here, '../../../data');

export interface ModelElo {
  display_name: string;
  org: string;
  rating: number;
  games: number;
  wins: number;
}

export interface EloDoc {
  updated_at: string;
  models: Record<string, ModelElo>;
}

export interface IndexRow {
  game_id: string;
  date: string;
  status: 'complete' | 'errored' | 'turn_limit';
  winner: string | null;
  turns: number;
  final_scores: Record<string, number>;
  elo_deltas: Record<string, number>;
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
  elo_before: Record<string, number>;
  elo_after: Record<string, number>;
}

export function loadElo(): EloDoc {
  return JSON.parse(readFileSync(resolve(dataDir, 'elo.json'), 'utf-8'));
}

export function loadIndex(): IndexRow[] {
  return JSON.parse(readFileSync(resolve(dataDir, 'index.json'), 'utf-8'));
}

export function loadGame(gameId: string): GameDoc {
  return JSON.parse(readFileSync(resolve(dataDir, 'games', `${gameId}.json`), 'utf-8'));
}

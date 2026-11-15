/**
 * Copyright (c) 2026 Shlok Vane. MIT license.
 *
 * FocusBoard sync client: the token lives in this browser's localStorage,
 * so signing in once on the headset's browser keeps the desk in sync.
 */

export type SyncNote = {
  id: string;
  color: string;
  pos_x: number;
  pos_y: number;
  pos_z: number;
  rot_y: number;
  text: string;
};

let apiBase = '';
let configPromise: Promise<void> | null = null;

function token(): string {
  try {
    return localStorage.getItem('fb_token') || '';
  } catch {
    return '';
  }
}

export function loadConfig(): Promise<void> {
  if (!configPromise) {
    const base = import.meta.env.BASE_URL || './';
    configPromise = fetch(`${base}config.json`, { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : {}))
      .then((cfg: { apiBase?: string }) => {
        apiBase = (cfg.apiBase || '').replace(/\/+$/u, '');
      })
      .catch(() => {
        apiBase = '';
      });
  }
  return configPromise;
}

export function signedIn(): boolean {
  return token() !== '' && apiBase !== '';
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(apiBase + path, { ...init, headers });
  const body = (await res.json().catch(() => ({}))) as T & { error?: string };
  if (!res.ok) {
    throw new Error(body.error || `Sync request failed (${res.status})`);
  }
  return body;
}

export function fetchSignedInUser(): Promise<{ name: string } | null> {
  return call<{ user: { name: string } }>('/api/auth/me')
    .then((r) => r.user)
    .catch(() => null);
}

export function fetchBoard(): Promise<SyncNote[]> {
  return call<{ notes: SyncNote[] }>('/api/notes').then((r) => r.notes);
}

export function saveNoteSpot(
  id: string,
  x: number,
  y: number,
  z: number,
  rotY: number,
): Promise<unknown> {
  return call(`/api/notes/${id}`, {
    method: 'PUT',
    body: JSON.stringify({ x, y, z, rot_y: rotY }),
  });
}

// PROTOTYPE — identitas & OAuth. Bukan kode produksi.
//
// Dua jalur, dan Activity sendiri tidak peduli yang mana yang dipakai:
//   1. DI DALAM DISCORD — handshake Embedded App SDK, authorize, tukar `code`
//      ke backend, lalu `authenticate`. Ini alur resmi (langkah 1-6).
//   2. DI BROWSER BIASA — tidak ada SDK, tidak ada OAuth. Dipakai untuk
//      menguji papan + WebSocket tanpa harus membuka Discord. Identitas dan
//      instance_id dibuat-buat dari query string.
//
// Jalur debug ada karena pengujian satu akun tidak bisa membuka dua Activity
// sekaligus; dengan jalur ini dua jendela browser bisa masuk ke instance yang
// sama dan saling melangkah.

import type { Identity } from './types';

export const CLIENT_ID: string = import.meta.env.VITE_DISCORD_CLIENT_ID ?? '';

/** URL asli yang dimuat Discord — dipakai untuk membangun URL proxy. */
export const ACTIVITY_URL = new URL(window.location.href);

export const IS_DISCORD = ACTIVITY_URL.searchParams.has('instance_id');

export interface DiscordSdkLike {
  instanceId: string | null;
  guildId: string | null;
  channelId: string | null;
  platform: string;
  ready(): Promise<void>;
  commands: {
    authorize(input: Record<string, unknown>): Promise<{ code: string }>;
    authenticate(input: { access_token: string }): Promise<{
      access_token: string;
      user: { id: string; username: string; global_name?: string | null; avatar?: string | null };
    }>;
    [key: string]: unknown;
  };
}

/**
 * Bangun URL backend yang benar di kedua konteks.
 *
 * Di dalam Discord, Activity dimuat dari `{clientId}.discordsays.com` lewat
 * proxy Discord, jadi `/api/...` otomatis diteruskan ke host yang di-mapping.
 * Di browser biasa, Vite yang mem-proxy `/api` ke backend.
 *
 * Keduanya menghasilkan URL relatif yang sama — itulah sebabnya satu jalur
 * kode cukup. Jangan menulis `wss://` absolut: itu akan melewati proxy.
 */
export function apiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `/api${normalized}`;
}

export function wsUrl(params: Record<string, string>): string {
  const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const qs = new URLSearchParams(params).toString();
  // Relatif terhadap origin yang sekarang — Discord atau Vite, keduanya benar.
  return `${scheme}://${window.location.host}${apiUrl('/ws')}?${qs}`;
}

/** Avatar Discord dari hash. */
function avatarUrl(userId: string, hash: string | null | undefined): string | null {
  if (!hash) return null;
  const ext = hash.startsWith('a_') ? 'gif' : 'png';
  return `https://cdn.discordapp.com/avatars/${userId}/${hash}.${ext}?size=64`;
}

/**
 * Identitas dari jalur debug (browser biasa).
 *
 * Query yang dibaca:
 *   ?debug=1                 mengaktifkan jalur debug
 *   &room=NAMA               id instance buatan (default: 'debug-room')
 *   &name=Nama               nama tampilan (default: 'Pemain Debug')
 */
export function debugIdentity(): Identity {
  const q = ACTIVITY_URL.searchParams;
  const room = q.get('room') || 'debug-room';
  const name = q.get('name') || 'Pemain Debug';
  const id = q.get('discord') || `debug-${name.toLowerCase().replace(/\s+/g, '-')}`;
  return { discordId: id, username: name, debug: true, instanceId: room, avatarUrl: null };
}

/**
 * Identitas dari jalur Discord — alur OAuth resmi.
 *
 * Kalau CLIENT_ID kosong, prototype tetap jalan sebagai debug supaya papan bisa
 * diuji sebelum app Discord dibuat. Ini disengaja: prototype ini untuk
 * direaksi, bukan untuk dipakai.
 */
export async function discordIdentity(): Promise<Identity> {
  if (!CLIENT_ID) {
    throw new Error(
      'VITE_DISCORD_CLIENT_ID kosong. Isi activity/prototype/.env (lihat PROTOTYPE.md) ' +
        'atau tambahkan ?debug=1 ke URL.',
    );
  }

  const { DiscordSDK } = await import('@discord/embedded-app-sdk');
  const sdk = new DiscordSDK(CLIENT_ID) as unknown as DiscordSdkLike;

  await sdk.ready();

  const { code } = await sdk.commands.authorize({
    client_id: CLIENT_ID,
    response_type: 'code',
    state: '',
    prompt: 'none',
    scope: ['identify'],
  });

  // Tukar code -> access_token DI BACKEND. client_secret tidak pernah ada di sini.
  const resp = await fetch(apiUrl('/token'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });

  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`tukar token gagal (${resp.status}): ${detail.slice(0, 200)}`);
  }

  const { access_token } = (await resp.json()) as { access_token: string };

  const auth = await sdk.commands.authenticate({ access_token });

  const user = auth.user;
  return {
    discordId: user.id,
    username: user.global_name || user.username,
    debug: false,
    instanceId: sdk.instanceId ?? 'TANPA-INSTANCE',
    avatarUrl: avatarUrl(user.id, user.avatar),
  };
}

/** Pilih jalur berdasarkan konteks. */
export async function resolveIdentity(): Promise<Identity> {
  if (IS_DISCORD) {
    return discordIdentity();
  }
  return debugIdentity();
}

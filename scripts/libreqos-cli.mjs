#!/usr/bin/env node
// Lightweight console runner for the LibreQoS Internet Quality Test endpoints.
// This is not a byte-for-byte browser clone, but it uses the official session
// API, signed transfer URLs, and WebSocket latency probe path.

import { writeFile } from 'node:fs/promises';
import { performance } from 'node:perf_hooks';

const CONTROL = 'https://api-bufferbloat.libreqos.com';
const PING_WS = 'wss://ping-bufferbloat.libreqos.com/ws';
const DEFAULT_DOWNLOAD_URLS = [
  'https://speed.cloudflare.com/__down?bytes=1073741824',
  'https://dl1-bufferbloat.libreqos.com/download?size=1gb',
  'https://dl2-bufferbloat.libreqos.com/download?size=1gb',
  'https://dl3-bufferbloat.libreqos.com/download?size=1gb',
  'https://dl4-bufferbloat.libreqos.com/download?size=1gb',
];

function usage() {
  console.log(`Usage: scripts/libreqos-cli.mjs [options]

Runs a console approximation of the LibreQoS standard bufferbloat test.

Options:
  --json-out <path>        Write full JSON result to a file
  --baseline-ms <n>        Baseline phase duration (default: 8100)
  --phase-ms <n>           Download/upload/bidirectional duration (default: 10000)
  --cooldown-ms <n>        Cooldown phase duration (default: 3000)
  --download-streams <n>   Download stream count (default: 6)
  --upload-streams <n>     Upload stream count (default: 3)
  --help                   Show this help

Notes:
  - Requires Node with global fetch and WebSocket support.
  - Does not force a source bind; run from the host/interface you want tested.
  - Uses p90 phase latency minus baseline p5 for bufferbloat deltas.
`);
}

function parseArgs(argv) {
  const opts = {
    jsonOut: null,
    baselineMs: 8100,
    phaseMs: 10000,
    cooldownMs: 3000,
    downloadStreams: 6,
    uploadStreams: 3,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === '--help' || arg === '-h') {
      usage();
      process.exit(0);
    }
    const next = () => {
      i += 1;
      if (i >= argv.length) throw new Error(`missing value for ${arg}`);
      return argv[i];
    };
    if (arg === '--json-out') opts.jsonOut = next();
    else if (arg === '--baseline-ms') opts.baselineMs = positiveInt(next(), arg);
    else if (arg === '--phase-ms') opts.phaseMs = positiveInt(next(), arg);
    else if (arg === '--cooldown-ms') opts.cooldownMs = positiveInt(next(), arg);
    else if (arg === '--download-streams') opts.downloadStreams = positiveInt(next(), arg);
    else if (arg === '--upload-streams') opts.uploadStreams = positiveInt(next(), arg);
    else throw new Error(`unknown argument: ${arg}`);
  }
  return opts;
}

function positiveInt(value, name) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) throw new Error(`${name} must be a positive integer`);
  return parsed;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function percentile(values, p) {
  const xs = values.filter(Number.isFinite).sort((a, b) => a - b);
  if (!xs.length) return null;
  const idx = (xs.length - 1) * p;
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  if (lo === hi) return xs[lo];
  return xs[lo] + (xs[hi] - xs[lo]) * (idx - lo);
}

function stats(samples) {
  const xs = samples.filter(Number.isFinite);
  const mean = xs.length ? xs.reduce((sum, x) => sum + x, 0) / xs.length : null;
  return {
    samples: xs.length,
    min: percentile(xs, 0),
    p5: percentile(xs, 0.05),
    p50: percentile(xs, 0.50),
    p75: percentile(xs, 0.75),
    p90: percentile(xs, 0.90),
    p95: percentile(xs, 0.95),
    p99: percentile(xs, 0.99),
    max: percentile(xs, 1),
    mean,
  };
}

async function startSession() {
  const configResponse = await fetch(`${CONTROL}/test/config?mode=standard`, { cache: 'no-store' });
  if (!configResponse.ok) throw new Error(`config failed: HTTP ${configResponse.status}`);
  const config = await configResponse.json();
  if (config?.turnstile?.enabled) {
    throw new Error('LibreQoS API currently requires Turnstile; use the browser test instead.');
  }

  const response = await fetch(`${CONTROL}/test/start?mode=standard`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: '{}',
  });
  if (!response.ok) throw new Error(`start failed: HTTP ${response.status} ${await response.text()}`);
  return response.json();
}

function connectWebSocket() {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(PING_WS);
    const pending = new Map();
    const timer = setTimeout(() => reject(new Error('WebSocket connect timeout')), 5000);
    ws.addEventListener('open', () => {
      clearTimeout(timer);
      resolve({ ws, pending });
    });
    ws.addEventListener('message', event => {
      try {
        const data = JSON.parse(event.data);
        const done = pending.get(data.clientTime);
        if (!done) return;
        pending.delete(data.clientTime);
        const elapsed = performance.now() - Number(data.clientTime);
        const serverMs = Number(data.serverProcessingTime || 0);
        done(Math.max(0, elapsed - serverMs));
      } catch (_) {
        // Ignore malformed probe responses; timeout path handles missing samples.
      }
    });
    ws.addEventListener('error', () => reject(new Error('WebSocket error')));
  });
}

function wsPing(conn, streamId = 1) {
  const clientTime = performance.now();
  return new Promise(resolve => {
    const timeout = setTimeout(() => {
      conn.pending.delete(clientTime);
      resolve(Number.NaN);
    }, 5000);
    conn.pending.set(clientTime, rtt => {
      clearTimeout(timeout);
      resolve(rtt);
    });
    conn.ws.send(JSON.stringify({ type: 'ping', timestamp: clientTime, streamId }));
  });
}

async function latencyPhase(conn, phaseMs, load = async () => ({})) {
  const samples = [];
  const started = performance.now();
  const deadline = started + phaseMs;
  const loadPromise = load(deadline, phaseMs);
  let stream = 1;
  while (performance.now() < deadline) {
    samples.push(await wsPing(conn, stream));
    stream = stream === 4 ? 1 : stream + 1;
    await sleep(200);
  }
  return { latency: stats(samples), ...(await loadPromise) };
}

async function downloadLoad(session, deadline, phaseMs, streams) {
  const bytesByStream = new Array(streams).fill(0);
  const token = session.downloadToken ? `&token=${encodeURIComponent(session.downloadToken)}` : '';
  const measurementUrl = session.endpoints?.measurement?.[0]?.downloads?.['1gb']?.url;
  const urls = DEFAULT_DOWNLOAD_URLS.map((url, index) => (index === 0 ? url : `${url}${token}`));
  if (measurementUrl) urls.push(measurementUrl);

  await Promise.all(bytesByStream.map(async (_, index) => {
    while (performance.now() < deadline) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), Math.max(100, deadline - performance.now()));
      try {
        const response = await fetch(urls[index % urls.length], { cache: 'no-store', signal: controller.signal });
        const reader = response.body?.getReader();
        while (reader && performance.now() < deadline) {
          const { done, value } = await reader.read();
          if (done) break;
          bytesByStream[index] += value?.byteLength || 0;
        }
        try { await reader?.cancel(); } catch (_) {}
      } catch (_) {
        await sleep(100);
      } finally {
        clearTimeout(timeout);
        controller.abort();
      }
    }
  }));

  const bytes = bytesByStream.reduce((sum, value) => sum + value, 0);
  return { downloadMbps: (bytes * 8) / (phaseMs * 1000) };
}

async function uploadLoad(session, deadline, phaseMs, streams) {
  const uploadUrl = session.endpoints?.measurement?.[0]?.upload?.url || `${CONTROL}/upload`;
  const chunk = new Uint8Array(1024 * 1024);
  const bytesByStream = new Array(streams).fill(0);

  await Promise.all(bytesByStream.map(async (_, index) => {
    while (performance.now() < deadline) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), Math.max(100, deadline - performance.now()));
      try {
        const response = await fetch(uploadUrl, { method: 'POST', body: chunk, signal: controller.signal });
        if (response.ok) bytesByStream[index] += chunk.byteLength;
      } catch (_) {
        await sleep(100);
      } finally {
        clearTimeout(timeout);
      }
    }
  }));

  const bytes = bytesByStream.reduce((sum, value) => sum + value, 0);
  return { uploadMbps: (bytes * 8) / (phaseMs * 1000) };
}

function grade(deltaMs) {
  if (deltaMs < 5) return 'A+';
  if (deltaMs < 30) return 'A';
  if (deltaMs < 60) return 'B';
  if (deltaMs < 200) return 'C';
  if (deltaMs < 400) return 'D';
  return 'F';
}

function delta(phase, baselineP5) {
  if (!Number.isFinite(phase?.latency?.p90) || !Number.isFinite(baselineP5)) return null;
  return Math.max(0, phase.latency.p90 - baselineP5);
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  const session = await startSession();
  const conn = await connectWebSocket();

  console.error(`Session: ${session.sessionId}`);
  console.error(`Server: ${session.edgeLocation || session.location || 'unknown'} ASN ${session.asn || '?'} ${session.asOrganization || ''}`.trim());

  try {
    const baseline = await latencyPhase(conn, opts.baselineMs);
    const download = await latencyPhase(conn, opts.phaseMs, (deadline, ms) =>
      downloadLoad(session, deadline, ms, opts.downloadStreams));
    const upload = await latencyPhase(conn, opts.phaseMs, (deadline, ms) =>
      uploadLoad(session, deadline, ms, opts.uploadStreams));
    const bidirectional = await latencyPhase(conn, opts.phaseMs, (deadline, ms) => Promise.all([
      downloadLoad(session, deadline, ms, Math.max(1, Math.floor(opts.downloadStreams * 2 / 3))),
      uploadLoad(session, deadline, ms, Math.max(1, Math.floor(opts.uploadStreams * 2 / 3))),
    ]).then(([downloadResult, uploadResult]) => ({ ...downloadResult, ...uploadResult })));
    const cooldown = await latencyPhase(conn, opts.cooldownMs);

    const baselineP5 = baseline.latency.p5;
    const bufferbloat = {
      downloadIncreaseMs: delta(download, baselineP5),
      uploadIncreaseMs: delta(upload, baselineP5),
      bidirectionalIncreaseMs: delta(bidirectional, baselineP5),
    };
    bufferbloat.totalIncreaseMs = Math.max(bufferbloat.downloadIncreaseMs ?? 0, bufferbloat.uploadIncreaseMs ?? 0);
    bufferbloat.totalGrade = grade(bufferbloat.totalIncreaseMs);

    const result = {
      timestamp: new Date().toISOString(),
      session: {
        id: session.sessionId,
        server: session.edgeLocation || session.location,
        asn: session.asn,
        isp: session.asOrganization,
        ipVersion: session.ipVersion,
      },
      phases: { baseline, download, upload, bidirectional, cooldown },
      bufferbloat,
    };

    const json = `${JSON.stringify(result, null, 2)}\n`;
    if (opts.jsonOut) await writeFile(opts.jsonOut, json, 'utf8');
    process.stdout.write(json);
  } finally {
    conn.ws.close();
  }
}

main().catch(error => {
  console.error(`ERROR: ${error.message}`);
  process.exit(1);
});

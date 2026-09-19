// Manual, temporary OSCAR relay. Importing this module never binds or calls Docker.
import http from 'node:http';
import { Duplex } from 'node:stream';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';

export const LIMITS = Object.freeze({
  clients: 32, backends: 16, headers: 16384, headerCount: 100,
  body: 1048576, buffer: 65536, stderr: 4096,
  headersMs: 10000, connectMs: 10000, requestMs: 30000,
  sessionMs: 900000, drainMs: 5000,
});
const ID = /^[a-f0-9]{64}$/;
const IMAGE = /^sha256:[a-f0-9]{64}$/;
const AUTHORITIES = new Set(['127.0.0.1:8089', 'localhost:8089']);
const HOP = new Set(['connection', 'keep-alive', 'proxy-authenticate',
  'proxy-authorization', 'te', 'trailer', 'transfer-encoding', 'upgrade']);
const REQUIRED_ENV = {
  START_DOCKER: 'false', HARDEN_DESKTOP: 'true', RESTART_APP: 'false',
  PIXELFLUX_WAYLAND: 'false', PELORUS: 'false', NO_GAMEPAD: 'true',
  SELKIES_FILE_TRANSFERS: '', SELKIES_COMMAND_ENABLED: 'false',
  SELKIES_AUDIO_ENABLED: 'false', SELKIES_MICROPHONE_ENABLED: 'false',
  SELKIES_GAMEPAD_ENABLED: 'false', SELKIES_UI_SIDEBAR_SHOW_FILES: 'false',
  SELKIES_UI_SIDEBAR_SHOW_APPS: 'false',
};
const fail = (message) => { throw new Error(message); };
const timer = (fn, ms) => { const t = setTimeout(fn, ms); t.unref(); return t; };

export function validateExpected(e) {
  if (!ID.test(e.containerId) || !IMAGE.test(e.imageId) || !IMAGE.test(e.sourceImageId) || !/^[a-f0-9]{40}$/.test(e.revision)) fail('Invalid immutable identity');
  if (!Number.isSafeInteger(e.uid) || e.uid <= 0 || !Number.isSafeInteger(e.gid) || e.gid < 0) fail('Invalid GUI identity');
  for (const p of [e.configPath, e.cardPath]) {
    if (typeof p !== 'string' || !/^\/Users\/titocr\/container-data\/cpap-monitor-candidate\/[^/]+\/(config|card)$/.test(p) || p.includes('/../')) fail('Invalid candidate path');
  }
  if (!e.configPath.endsWith('/config') || !e.cardPath.endsWith('/card') || e.configPath.slice(0, -6) !== e.cardPath.slice(0, -4)) fail('Candidate roots differ');
}

export function validateContainer(info, e, epoch) {
  validateExpected(e);
  const h = info.HostConfig ?? {}, s = info.State ?? {}, c = info.Config ?? {};
  if (info.Id !== e.containerId || info.Image !== e.imageId || c.Image !== e.sourceImageId || c.Labels?.['org.opencontainers.image.revision'] !== e.revision) fail('Container identity mismatch');
  if (c.Labels?.['com.docker.compose.project'] !== 'cpap-monitor-candidate' || c.Labels?.['com.docker.compose.service'] !== 'oscar') fail('Wrong candidate project');
  if (!s.Running || s.Paused || s.Restarting || !s.StartedAt) fail('Candidate not running');
  const next = `${s.StartedAt}/${info.RestartCount}`;
  if (epoch && next !== epoch) fail('Candidate restarted');
  if (h.NetworkMode !== 'none' || Object.keys(h.PortBindings ?? {}).length || h.PublishAllPorts) fail('Candidate has networking');
  for (const [name, net] of Object.entries(info.NetworkSettings?.Networks ?? {})) {
    if (name !== 'none' || net.IPAddress || net.GlobalIPv6Address || net.Gateway || net.IPv6Gateway) fail('Routable endpoint');
  }
  if (Object.values(info.NetworkSettings?.Ports ?? {}).some(Boolean)) fail('Published port');
  if (h.Privileged || !['', 'private'].includes(h.PidMode ?? '') || !['', 'private'].includes(h.IpcMode ?? '') || !['', 'private'].includes(h.UTSMode ?? '') || h.UsernsMode === 'host' || h.CgroupnsMode === 'host' || (h.Devices ?? []).length || (h.DeviceRequests ?? []).length || (h.DeviceCgroupRules ?? []).length || (h.CapAdd ?? []).length) fail('Unexpected privileges');
  if (!(h.SecurityOpt ?? []).some(x => x === 'no-new-privileges' || x === 'no-new-privileges:true')) fail('Missing no-new-privileges');
  if (!['', 'no'].includes(h.RestartPolicy?.Name ?? '') || h.Memory !== 2147483648 || h.NanoCpus !== 2000000000 || h.ShmSize !== 268435456) fail('Unexpected resource/startup policy');
  if (h.LogConfig?.Type !== 'json-file' || h.LogConfig.Config?.['max-size'] !== '10m' || h.LogConfig.Config?.['max-file'] !== '3') fail('Unbounded logs');
  const mounts = info.Mounts ?? [];
  if (mounts.length !== 2) fail('Unexpected mounts');
  for (const [dest, path, rw] of [['/config', e.configPath, true], ['/sdcard', e.cardPath, false]]) {
    const m = mounts.find(x => x.Destination === dest);
    if (!m || m.Type !== 'bind' || m.Source !== path || m.RW !== rw || (m.Propagation && m.Propagation !== 'rprivate')) fail('Unexpected mount');
  }
  const env = Object.fromEntries((c.Env ?? []).map(x => { const n = x.indexOf('='); return [x.slice(0, n), x.slice(n + 1)]; }));
  for (const [key, value] of Object.entries({...REQUIRED_ENV, PUID: String(e.uid), PGID: String(e.gid)})) if (env[key] !== value) fail(`Unexpected environment: ${key}`);
  return next;
}

function rawValues(req, key) {
  const values = [];
  for (let n = 0; n < req.rawHeaders.length; n += 2) if (req.rawHeaders[n].toLowerCase() === key) values.push(req.rawHeaders[n + 1]);
  return values;
}
export function validateRequest(req, upgrade = false, limits = LIMITS) {
  if (req.httpVersion !== '1.1' || !req.url?.startsWith('/') || req.url.startsWith('//') || /[\\\x00-\x20\x7f]/.test(req.url)) fail('Invalid request target');
  if (!['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'].includes(req.method)) fail('Disallowed method');
  if (req.rawHeaders.length / 2 > limits.headerCount) fail('Too many headers');
  for (const key of ['host', 'origin', 'content-length', 'transfer-encoding', 'sec-fetch-site', 'upgrade', 'sec-websocket-key', 'sec-websocket-version']) if (rawValues(req, key).length > 1) fail('Duplicate security header');
  const hosts = rawValues(req, 'host');
  if (hosts.length !== 1 || !AUTHORITIES.has(hosts[0])) fail('Invalid Host');
  const origin = `http://${hosts[0]}`;
  if (req.headers.origin !== undefined && req.headers.origin !== origin) fail('Invalid Origin');
  if (req.headers['sec-fetch-site'] && !['same-origin', 'none'].includes(req.headers['sec-fetch-site'])) fail('Cross-site request');
  if (req.headers.expect || req.headers['content-length'] && req.headers['transfer-encoding']) fail('Ambiguous framing');
  const length = req.headers['content-length'];
  if (length !== undefined && (!/^\d+$/.test(length) || Number(length) > limits.body)) fail('Body too large');
  if (req.headers['transfer-encoding'] && req.headers['transfer-encoding'].toLowerCase() !== 'chunked') fail('Invalid transfer encoding');
  if (upgrade) {
    if (req.method !== 'GET' || req.headers.origin !== origin || req.headers.upgrade?.toLowerCase() !== 'websocket' || req.headers['sec-websocket-version'] !== '13' || !/^[A-Za-z0-9+/]{22}==$/.test(req.headers['sec-websocket-key'] ?? '') || req.headers['transfer-encoding'] || Number(length ?? 0) !== 0) fail('Invalid WebSocket upgrade');
    if (!String(req.headers.connection).toLowerCase().split(',').map(x => x.trim()).includes('upgrade')) fail('Missing upgrade token');
  } else if (req.headers.upgrade) fail('Unsupported upgrade');
  return hosts[0];
}

export function cleanHeaders(headers, upgrade = false) {
  const blocked = new Set([...HOP, ...String(headers.connection ?? '').toLowerCase().split(',').map(x => x.trim())]);
  const clean = {};
  for (const [key, value] of Object.entries(headers)) {
    const lower = key.toLowerCase();
    if (!blocked.has(lower) && lower !== 'forwarded' && !lower.startsWith('x-forwarded-') && lower !== 'access-control-allow-origin' && lower !== 'access-control-allow-credentials') clean[lower] = value;
  }
  if (upgrade) { clean.connection = 'Upgrade'; clean.upgrade = 'websocket'; }
  return clean;
}

// No shell, TTY, dynamic helper arguments or runtime context lookup.
export function execArgs(endpoint, e) {
  if (endpoint !== 'unix:///Users/titocr/.orbstack/run/docker.sock') fail('Not the Studio OrbStack endpoint');
  validateExpected(e);
  return ['--host', endpoint, 'exec', '-i', '--user', `${e.uid}:${e.gid}`, '--workdir', '/', e.containerId,
    '/usr/bin/python3', '-I', '/usr/local/bin/cpap-stream-bridge'];
}

export function childDuplex(child, limits = LIMITS) {
  let errorBytes = 0, reapTimer, killTimer, processEnded = false, escalated = false;
  let processDone;
  const processClosed = new Promise(resolve => { processDone = resolve; });
  child.once('close', (code, signal) => {
    processEnded = true;
    clearTimeout(reapTimer); clearTimeout(killTimer);
    const clean = !escalated && code === 0 && signal === null;
    processDone(clean);
    if (!clean) stream.destroy(new Error('Remote helper completion unproven'));
  });
  const stream = new Duplex({
    readableHighWaterMark: limits.buffer, writableHighWaterMark: limits.buffer,
    read() { child.stdout.resume(); },
    write(chunk, encoding, callback) { child.stdin.write(chunk, encoding, callback); },
    final(callback) { child.stdin.end(callback); },
    destroy(error, callback) {
      // EOF is the helper's normal cleanup signal. Do not assume killing the CLI
      // also kills Docker's remote exec process.
      child.stdin.end(); child.stdout.resume();
      if (!processEnded) reapTimer = timer(() => {
        escalated = true;
        // Arm first: a synchronous close in an injected process adapter must
        // cancel escalation just as the real asynchronous close does.
        killTimer = timer(() => { child.kill('SIGKILL'); processDone(false); }, limits.drainMs);
        child.kill('SIGTERM');
      }, limits.drainMs);
      callback(error);
    },
  });
  child.stdout.on('data', chunk => { if (!stream.destroyed && !stream.push(chunk)) child.stdout.pause(); });
  child.stdout.on('end', () => stream.push(null));
  child.stdout.on('error', () => stream.destroy(new Error('Backend output failed')));
  child.stdin.on('error', () => stream.destroy(new Error('Backend input failed')));
  child.stderr.on('data', chunk => { errorBytes += chunk.length; if (errorBytes > limits.stderr) stream.destroy(new Error('Backend stderr limit')); });
  child.stderr.on('error', () => stream.destroy(new Error('Backend stderr failed')));
  child.on('error', () => stream.destroy(new Error('Backend spawn failed')));
  child.on('exit', code => { if (code !== 0) stream.destroy(new Error('Backend exited unsuccessfully')); });
  stream.processClosed = processClosed;
  return stream;
}

/** All host side effects are behind this adapter and occur only on method calls. */
export function dockerAdapter({dockerPath, endpoint, expected, spawnProcess = spawn}) {
  if (!dockerPath?.startsWith('/') || dockerPath.includes('\0')) fail('Absolute Docker executable required');
  const command = execArgs(endpoint, expected);
  const children = new Set();
  const options = {shell: false, env: {PATH: '/usr/bin:/bin', HOME: '/Users/titocr'}, stdio: ['pipe', 'pipe', 'pipe']};
  const launch = args => {
    const c = spawnProcess(dockerPath, args, options); children.add(c);
    c.on('close', () => children.delete(c)); return c;
  };
  async function bounded(args, timeout = 10000) {
    return await new Promise((resolve, reject) => {
      const c = launch(['--host', endpoint, ...args]); let output = '', size = 0, settled = false;
      const done = (err) => { if (settled) return; settled = true; clearTimeout(t); err ? reject(err) : resolve(output); };
      const t = timer(() => { c.kill('SIGKILL'); done(new Error('Docker command deadline')); }, timeout);
      c.stdin.end();
      c.stdout.on('data', b => { size += b.length; if (size > 1048576) { c.kill('SIGKILL'); done(new Error('Docker output limit')); } else output += b.toString(); });
      c.stderr.on('data', b => { size += b.length; if (size > 1048576) { c.kill('SIGKILL'); done(new Error('Docker output limit')); } });
      c.on('error', () => done(new Error('Docker unavailable')));
      c.on('close', code => done(code === 0 ? null : new Error('Docker command failed')));
    });
  }
  return {
    inspect: async () => JSON.parse(await bounded(['inspect', expected.containerId]))[0],
    openBackend: () => childDuplex(launch(command)),
    watch(onFailure) {
      const c = launch(['--host', endpoint, 'events', '--filter', `container=${expected.containerId}`, '--format', '{{.Action}}']);
      let line = '', cancelled = false;
      c.stdin.end();
      c.stdout.on('data', b => {
        line += b.toString(); if (line.length > 65536) return onFailure();
        const lines = line.split('\n'); line = lines.pop();
        for (const action of lines) if (!/^(exec_create:|exec_start:|exec_die$|health_status:)/.test(action)) onFailure();
      });
      c.stderr.on('data', () => onFailure());
      c.on('error', () => { if (!cancelled) onFailure(); });
      c.on('close', () => { if (!cancelled) onFailure(); });
      return () => { cancelled = true; c.kill('SIGTERM'); };
    },
    async finalize() {
      // End remote helpers reliably by stopping only this dedicated candidate.
      // CLI termination alone does not establish remote exec cleanup.
      for (const c of children) { c.stdin.destroy(); c.kill('SIGTERM'); }
      try {
        await bounded(['stop', '-t', '60', expected.containerId], 70000);
        const state = JSON.parse(await bounded(['inspect', expected.containerId]))[0].State;
        if (state.Running) fail('Candidate failed to stop');
      } finally {
        await Promise.all([...children].map(c => new Promise((resolve, reject) => {
          const t = timer(() => reject(new Error('Docker child did not reap')), 5000);
          c.once('close', () => { clearTimeout(t); resolve(); });
          c.kill('SIGKILL');
        })));
      }
    },
  };
}

/** Prepare only; caller must explicitly authorize and call server.listen(). */
export async function prepareRelay({expected, adapter, limits = LIMITS}) {
  validateExpected(expected);
  const epoch = validateContainer(await adapter.inspect(), expected);
  const clients = new Set(), backends = new Set(), agents = new Set(), timers = new Set();
  let pending = 0, stopping = false, closePromise, unwatch = () => {};
  let finish;
  const finished = new Promise(resolve => { finish = resolve; });
  const server = http.createServer({maxHeaderSize: limits.headers, insecureHTTPParser: false});
  server.maxHeadersCount = limits.headerCount + 1;
  server.headersTimeout = limits.headersMs;
  server.requestTimeout = limits.requestMs;
  server.maxRequestsPerSocket = 1;
  server.keepAliveTimeout = 1;
  const reject = (socket, status = 403) => { if (!socket.destroyed) socket.end(`HTTP/1.1 ${status} Rejected\r\nConnection: close\r\nContent-Length: 0\r\n\r\n`); };
  async function close(reason = 'operator-stop') {
    if (closePromise) return closePromise;
    stopping = true;
    closePromise = (async () => {
      unwatch(); for (const t of timers) clearTimeout(t); timers.clear();
      server.close();
      for (const socket of clients) socket.destroy();
      for (const agent of agents) agent.destroy();
      for (const backend of backends) backend.destroy();
      try { await adapter.finalize(); backends.clear(); clients.clear(); finish({ok:true, reason}); }
      catch (error) { finish({ok:false, reason, error}); throw error; }
    })();
    return closePromise;
  }
  const stopOnFailure = () => { close('containment-or-monitor-failure').catch(() => {}); };
  function setTimer(fn, ms) { const t = timer(() => { timers.delete(t); fn(); }, ms); timers.add(t); return t; }
  function clear(t) { clearTimeout(t); timers.delete(t); }
  async function check() { if (stopping) fail('Relay stopping'); validateContainer(await adapter.inspect(), expected, epoch); if (stopping) fail('Relay stopping'); }
  // Event loss is fatal; polling also detects network attachments and same-ID restarts.
  unwatch = adapter.watch(stopOnFailure);
  const poll = async () => { try { await check(); if (!stopping) setTimer(poll, 1000); } catch { stopOnFailure(); } };
  setTimer(poll, 1000); setTimer(() => { close('session-deadline').catch(() => {}); }, limits.sessionMs);
  server.on('connection', socket => {
    if (stopping || clients.size >= limits.clients) return socket.destroy();
    clients.add(socket);
    const t = setTimer(() => socket.destroy(), limits.headersMs);
    socket.once('close', () => { clear(t); clients.delete(socket); });
    socket._cpapHeaderTimer = t;
  });
  server.on('clientError', (_e, socket) => reject(socket, 400));
  server.on('connect', (_req, socket) => reject(socket));
  server.on('checkContinue', (_req, res) => { res.writeHead(417, {Connection: 'close'}); res.end(); });
  server.on('checkExpectation', (_req, res) => { res.writeHead(417, {Connection: 'close'}); res.end(); });
  server.on('error', stopOnFailure);

  async function forward(req, res, socket, head, upgrade) {
    if (req.socket._cpapHeaderTimer) clear(req.socket._cpapHeaderTimer);
    try { validateRequest(req, upgrade, limits); } catch { return reject(socket); }
    if (stopping || pending + backends.size >= limits.backends) return reject(socket, 503);
    pending++;
    try { await check(); } catch { pending--; reject(socket, 503); stopOnFailure(); return; }
    pending--;
    if (stopping || socket.destroyed) return;
    let backend, agent, upstream, deadline, connectDeadline;
    let completed = false, upgraded = false;
    const cleanup = () => {
      if (completed) return; completed = true;
      clear(deadline); clear(connectDeadline);
      upstream?.destroy(); agent?.destroy(); agents.delete(agent);
      backend?.destroy();
      if (backend?.processClosed) {
        backend.processClosed.then(ok => { backends.delete(backend); if (!ok) stopOnFailure(); });
      } else backends.delete(backend);
    };
    const bad = () => { if (!socket.destroyed) { if (res && !res.headersSent) { res.writeHead(502, {Connection: 'close'}); res.end(); } else socket.destroy(); } cleanup(); };
    try {
      backend = adapter.openBackend(); backend.on('error', bad); backends.add(backend);
      agent = new http.Agent({keepAlive: false, maxSockets: 1}); agents.add(agent);
      agent.createConnection = () => backend;
      const headers = cleanHeaders(req.headers, upgrade);
      headers.host = req.headers.host;
      if (req.headers.origin !== undefined) headers.origin = req.headers.origin;
      // Drop compression negotiation so the raw upgraded stream needs no extension handling.
      if (upgrade) delete headers['sec-websocket-extensions'];
      upstream = http.request({host: '127.0.0.1', port: 3000, method: req.method,
        path: req.url, headers, agent, maxHeaderSize: limits.headers, insecureHTTPParser: false});
      upstream.maxHeadersCount = limits.headerCount;
      upstream.on('error', bad);
      socket.once('close', cleanup);
      req.once('aborted', cleanup);
      deadline = setTimer(() => { socket.destroy(); cleanup(); }, upgrade ? limits.sessionMs : limits.requestMs);
      connectDeadline = setTimer(bad, limits.connectMs);
      upstream.on('response', response => {
        clear(connectDeadline);
        if (upgrade) { response.destroy(); return bad(); }
        if (response.rawHeaders.length / 2 > limits.headerCount) return bad();
        const responseHeaders = cleanHeaders(response.headers);
        responseHeaders.connection = 'close';
        res.writeHead(response.statusCode, responseHeaders);
        response.on('error', bad); response.on('aborted', bad);
        res.once('finish', cleanup);
        response.pipe(res);
      });
      upstream.on('upgrade', (response, raw, upstreamHead) => {
        const accept = createHash('sha1').update(req.headers['sec-websocket-key'] + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
        const protocols = String(req.headers['sec-websocket-protocol'] ?? '').split(',').map(x => x.trim());
        if (!upgrade || response.statusCode !== 101 || response.headers.upgrade?.toLowerCase() !== 'websocket' || !String(response.headers.connection).toLowerCase().split(',').map(x => x.trim()).includes('upgrade') || response.headers['content-length'] !== undefined || response.headers['transfer-encoding'] || response.headers['sec-websocket-accept'] !== accept || response.headers['sec-websocket-extensions'] || response.headers['sec-websocket-protocol'] && !protocols.includes(response.headers['sec-websocket-protocol']) || rawValues(response, 'sec-websocket-accept').length !== 1) { raw.destroy(); return bad(); }
        upgraded = true; clear(connectDeadline);
        const h = cleanHeaders(response.headers, true);
        let text = 'HTTP/1.1 101 Switching Protocols\r\n';
        for (const [key, value] of Object.entries(h)) for (const v of Array.isArray(value) ? value : [value]) text += `${key}: ${v}\r\n`;
        socket.write(text + '\r\n');
        if (upstreamHead.length) raw.unshift(upstreamHead);
        if (head.length) socket.unshift(head);
        raw.on('error', bad); raw.once('end', () => socket.end());
        socket.pipe(raw); raw.pipe(socket);
      });
      upstream.on('close', () => { if (!upgraded && !completed && !res?.writableEnded) bad(); });
      let bytes = 0;
      req.on('data', chunk => { bytes += chunk.length; if (bytes > limits.body) { socket.destroy(); cleanup(); } });
      if (upgrade) upstream.end(); else req.pipe(upstream);
    } catch { bad(); }
  }
  server.on('request', (req, res) => { void forward(req, res, req.socket, Buffer.alloc(0), false); });
  server.on('upgrade', (req, socket, head) => { socket.pause(); void forward(req, null, socket, head, true); });
  return {server, close, check, finished, get stopping() { return stopping; },
    get counts() { return {clients: clients.size, backends: backends.size, pending}; }};
}

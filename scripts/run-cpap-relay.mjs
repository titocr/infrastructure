// Explicit manual entry point. Do not invoke before changed-scope approval.
import { readFile, lstat, realpath } from 'node:fs/promises';
import { userInfo } from 'node:os';
import { pathToFileURL } from 'node:url';
import { dockerAdapter, prepareRelay, validateExpected } from './cpap-relay.mjs';

export async function readRunConfiguration(path) {
  if (!path?.startsWith('/Users/titocr/container-data/cpap-monitor-candidate/')) throw new Error('Private candidate configuration required');
  const stat = await lstat(path);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.uid !== userInfo().uid || (stat.mode & 0o077) || stat.size > 16384 || await realpath(path) !== path) throw new Error('Run configuration must be private, owned and not symlinked');
  const config = JSON.parse(await readFile(path, 'utf8'));
  validateExpected(config.expected);
  if (config.expected.uid !== userInfo().uid || config.expected.gid !== userInfo().gid) throw new Error('Candidate ownership differs from current user');
  for (const path of [config.expected.configPath, config.expected.cardPath]) {
    const s = await lstat(path);
    if (!s.isDirectory() || s.isSymbolicLink() || s.uid !== userInfo().uid || (s.mode & 0o077) || await realpath(path) !== path) throw new Error('Candidate directories must be private and canonical');
  }
  if (!config.dockerPath?.startsWith('/')) throw new Error('Absolute Docker path required');
  config.dockerPath = await realpath(config.dockerPath);
  const binary = await lstat(config.dockerPath);
  if (!binary.isFile() || (binary.mode & 0o022) || !(binary.mode & 0o111)) throw new Error('Unsafe Docker executable');
  if (config.endpoint !== 'unix:///Users/titocr/.orbstack/run/docker.sock') throw new Error('Wrong Docker endpoint');
  return config;
}

export async function run(path) {
  if (Number(process.versions.node.split('.')[0]) !== 24) throw new Error('Use reviewed Node 24 runtime');
  const config = await readRunConfiguration(path);
  const relay = await prepareRelay({expected: config.expected, adapter: dockerAdapter(config)});
  const shutdown = () => { relay.close().catch(() => {}); };
  process.once('SIGINT', shutdown); process.once('SIGTERM', shutdown);
  try {
    await relay.check();
    if (relay.stopping) throw new Error('Preflight stopped relay');
    await new Promise((resolve, reject) => {
      relay.server.once('error', reject);
      relay.server.listen({host: '127.0.0.1', port: 8089, exclusive: true}, resolve);
    });
    process.stdout.write('Empty-data diagnostic relay listening on 127.0.0.1:8089; maximum 15 minutes.\n');
    const result = await relay.finished;
    if (!result.ok || result.reason === 'containment-or-monitor-failure') throw new Error('Relay stopped on a safety or cleanup failure; inspect candidate state');
    process.stdout.write('Relay closed and dedicated candidate stopped.\n');
  } finally {
    process.removeListener('SIGINT', shutdown); process.removeListener('SIGTERM', shutdown);
    await relay.close();
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.argv.length !== 4 || process.argv[2] !== '--approved-config') {
    process.stderr.write('Usage after explicit approval: node scripts/run-cpap-relay.mjs --approved-config /absolute/private/run.json\n');
    process.exitCode = 2;
  } else {
    run(process.argv[3]).catch(() => {
      process.stderr.write('Relay failed; verify the dedicated candidate is stopped. No automatic retry.\n');
      process.exitCode = 1;
    });
  }
}

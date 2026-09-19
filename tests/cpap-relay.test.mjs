import test from 'node:test';
import assert from 'node:assert/strict';
import { Duplex, PassThrough } from 'node:stream';
import { EventEmitter } from 'node:events';
import { createHash } from 'node:crypto';
import { LIMITS, validateExpected, validateContainer, validateRequest, cleanHeaders,
  execArgs, childDuplex, dockerAdapter, prepareRelay } from '../scripts/cpap-relay.mjs';

const expected = {
  containerId: 'a'.repeat(64), imageId: 'sha256:' + 'b'.repeat(64), sourceImageId: 'sha256:' + 'd'.repeat(64), revision: 'c'.repeat(40),
  uid: 501, gid: 20,
  configPath: '/Users/titocr/container-data/cpap-monitor-candidate/test/config',
  cardPath: '/Users/titocr/container-data/cpap-monitor-candidate/test/card',
};
const required = {START_DOCKER:'false', HARDEN_DESKTOP:'true', RESTART_APP:'false',
  PIXELFLUX_WAYLAND:'false', PELORUS:'false', NO_GAMEPAD:'true', SELKIES_FILE_TRANSFERS:'',
  SELKIES_COMMAND_ENABLED:'false', SELKIES_AUDIO_ENABLED:'false', SELKIES_MICROPHONE_ENABLED:'false',
  SELKIES_GAMEPAD_ENABLED:'false', SELKIES_UI_SIDEBAR_SHOW_FILES:'false', SELKIES_UI_SIDEBAR_SHOW_APPS:'false',
  PUID:'501', PGID:'20'};
function info() { return {
  Id: expected.containerId, Image: expected.imageId, RestartCount: 0,
  State: {Running:true, StartedAt:'2026-09-19T00:00:00Z'},
  Config: {Image:expected.sourceImageId,Labels:{'org.opencontainers.image.revision':expected.revision,
    'com.docker.compose.project':'cpap-monitor-candidate','com.docker.compose.service':'oscar'},
    Env:Object.entries(required).map(([k,v])=>`${k}=${v}`)},
  HostConfig:{NetworkMode:'none', PortBindings:{}, SecurityOpt:['no-new-privileges:true'],
    Memory:2147483648, NanoCpus:2000000000, ShmSize:268435456, RestartPolicy:{Name:'no'},
    LogConfig:{Type:'json-file',Config:{'max-size':'10m','max-file':'3'}}},
  NetworkSettings:{Networks:{none:{IPAddress:'',GlobalIPv6Address:''}},Ports:{'3000/tcp':null}},
  Mounts:[{Type:'bind',Source:expected.configPath,Destination:'/config',RW:true,Propagation:'rprivate'},
    {Type:'bind',Source:expected.cardPath,Destination:'/sdcard',RW:false,Propagation:'rprivate'}],
}; }
function request(headers={}, fields={}) {
  const h={host:'127.0.0.1:8089',...headers};
  return {httpVersion:'1.1',method:'GET',url:'/',headers:h,rawHeaders:Object.entries(h).flat(),...fields};
}
function websocket(headers={}) { return request({origin:'http://127.0.0.1:8089',connection:'Upgrade',
  upgrade:'websocket','sec-websocket-version':'13','sec-websocket-key':'dGhlIHNhbXBsZSBub25jZQ==',...headers}); }

test('identity permits the none network map but refuses altered mounts, privileges, image or restart',()=>{
  const epoch=validateContainer(info(),expected);
  const mutations=[x=>x.Image='sha256:'+'d'.repeat(64),x=>x.State.StartedAt='later',x=>x.RestartCount++,
    x=>x.HostConfig.NetworkMode='bridge',x=>x.NetworkSettings.Networks.none.IPAddress='172.17.0.2',
    x=>x.NetworkSettings.Networks.other={},x=>x.HostConfig.PortBindings={'3000/tcp':[]},
    x=>x.HostConfig.Privileged=true,x=>x.HostConfig.SecurityOpt=[],x=>x.HostConfig.CapAdd=['SYS_ADMIN'],
    x=>x.Mounts.push({Destination:'/host'}),x=>x.Mounts[1].RW=true,x=>x.HostConfig.Memory=0,
    x=>x.Config.Env.push('START_DOCKER=true'),x=>x.State.Running=false];
  for(const mutate of mutations){const x=info();mutate(x);assert.throws(()=>validateContainer(x,expected,epoch));}
  assert.throws(()=>validateExpected({...expected,containerId:'candidate'}));
  assert.throws(()=>validateExpected({...expected,uid:0}));
});
test('request policy rejects rebinding, cross-origin, absolute targets, framing and duplicate hosts',()=>{
  assert.equal(validateRequest(request()),'127.0.0.1:8089');
  for(const req of [request({host:'evil.test:8089'}),request({origin:'null'}),request({origin:'https://evil.test'}),
    request({'sec-fetch-site':'cross-site'}),request({'sec-fetch-site':'same-site'}),
    request({}, {url:'http://127.0.0.1:8089/'}),request({}, {url:'//evil.test/'}),request({}, {method:'CONNECT'}),
    request({'content-length':'1048577'}),request({'transfer-encoding':'chunked','content-length':'2'}),
    request({}, {rawHeaders:['Host','127.0.0.1:8089','Host','evil.test']})]) assert.throws(()=>validateRequest(req));
});
test('WebSocket policy and forwarding headers fail closed',()=>{
  validateRequest(websocket(),true);
  for(const req of [websocket({origin:undefined}),websocket({origin:'http://localhost:8089'}),
    websocket({upgrade:'h2c'}),websocket({'sec-websocket-key':'bad'}),websocket({'content-length':'1'})]) assert.throws(()=>validateRequest(req,true));
  assert.deepEqual(cleanHeaders({host:'127.0.0.1:8089',connection:'x-secret', 'x-secret':'bad',
    forwarded:'bad','x-forwarded-user':'admin','transfer-encoding':'chunked','access-control-allow-origin':'*'}),{host:'127.0.0.1:8089'});
});
test('exec invocation is fixed, local, no TTY or shell, numeric verified user',()=>{
  const args=execArgs('unix:///Users/titocr/.orbstack/run/docker.sock',expected);
  assert.deepEqual(args.slice(-4),[expected.containerId,'/usr/bin/python3','-I','/usr/local/bin/cpap-stream-bridge']);
  assert.ok(args.includes('501:20'));assert.ok(!args.includes('-t'));
  assert.throws(()=>execArgs('tcp://remote:2375',expected));
});

class MemorySocket extends Duplex {
  constructor(onWrite=()=>{}) { super({allowHalfOpen:true});this.output=[];this.onWrite=onWrite; }
  _read() {}
  _write(chunk,_encoding,done) { this.output.push(Buffer.from(chunk));this.onWrite(chunk,this);done(); }
  setTimeout(){return this;} setNoDelay(){return this;} setKeepAlive(){return this;}
  get text(){return Buffer.concat(this.output).toString();}
}
const turn=()=>new Promise(resolve=>setImmediate(resolve));
async function settle(){for(let i=0;i<12;i++)await turn();}
async function harness(t, backend, limits=LIMITS) {
  let opens=0,finalized=0,watchFailure;
  let state=info();
  const streams=[];
  const adapter={inspect:async()=>state,openBackend:()=>{opens++;const s=new MemorySocket(backend);streams.push(s);return s;},
    watch:cb=>{watchFailure=cb;return()=>{};},finalize:async()=>{finalized++;}};
  const relay=await prepareRelay({expected,adapter,limits});
  t.after(()=>relay.close());
  function connect(raw){const s=new MemorySocket();s.on('error',()=>{});relay.server.emit('connection',s);s.push(Buffer.from(raw));return s;}
  return {relay,connect,streams,get opens(){return opens;},get finalized(){return finalized;},
    change:fn=>fn(state),monitorLost:()=>watchFailure()};
}
function httpBackend(chunk,s){
  if(!s.answered&&Buffer.concat(s.output).includes(Buffer.from('\r\n\r\n'))){
    s.answered=true;queueMicrotask(()=>{s.push(Buffer.from('HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK'));});
  }
}
test('real Node HTTP parsers work through entirely in-memory exec transport',async t=>{
  const h=await harness(t,httpBackend);
  const client=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\nX-Forwarded-User: admin\r\n\r\n');
  await settle();assert.match(client.text,/200 OK/);assert.match(client.text,/OK$/);
  assert.equal(h.opens,1);assert.doesNotMatch(h.streams[0].text,/X-Forwarded-User/i);
  assert.equal(h.relay.counts.backends,0);
});
test('malformed and oversized raw requests never create a backend',async t=>{
  const h=await harness(t,httpBackend);
  for(const raw of [
    'GET / HTTP/1.1\r\nHost: evil.test\r\n\r\n',
    'CONNECT example.com:443 HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n',
    'GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\nHost: evil.test\r\n\r\n',
    'POST / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n',
    'GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\nX-Large: '+ 'a'.repeat(17000)+'\r\n\r\n']) h.connect(raw);
  await settle();assert.equal(h.opens,0);
});
test('pipelined second request cannot bypass policy',async t=>{
  const h=await harness(t,httpBackend);
  h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\nGET /private HTTP/1.1\r\nHost: evil.test\r\n\r\n');
  await settle();assert.ok(h.opens<=1);
  for(const s of h.streams)assert.doesNotMatch(s.text,/private|evil.test/);
});
test('same-ID restart and monitor loss stop relay and finalize session',async t=>{
  const h=await harness(t,httpBackend);h.change(s=>s.RestartCount++);
  h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');
  await settle();assert.equal(h.opens,0);assert.equal(h.relay.stopping,true);assert.equal(h.finalized,1);
  h.monitorLost();await h.relay.close();assert.equal(h.finalized,1);
});
test('active backend and stalled client caps prevent unbounded spawning',async t=>{
  const h=await harness(t,()=>{},{...LIMITS,backends:1,clients:2});
  h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');await settle();
  const second=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');await settle();
  assert.equal(h.opens,1);assert.match(second.text,/503/);
  await h.relay.close();assert.equal(h.relay.counts.backends,0);
});
test('valid WebSocket handshake preserves both already-read heads exactly once',async t=>{
  const accept=createHash('sha1').update('dGhlIHNhbXBsZSBub25jZQ==258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
  const h=await harness(t,(chunk,s)=>{
    if(!s.answered && s.text.includes('\r\n\r\n')){s.answered=true;queueMicrotask(()=>s.push(Buffer.from(
      `HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Accept: ${accept}\r\n\r\nBACKEND_HEAD`)));}
  });
  const c=h.connect('GET /websocket HTTP/1.1\r\nHost: 127.0.0.1:8089\r\nOrigin: http://127.0.0.1:8089\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\nCLIENT_HEAD');
  await settle();assert.match(c.text,/101 Switching/);assert.equal(c.text.split('BACKEND_HEAD').length,2);
  assert.equal(h.streams[0].text.split('CLIENT_HEAD').length,2);
  c.push(Buffer.from('LATER'));await settle();assert.match(h.streams[0].text,/LATER$/);
  c.destroy();await settle();assert.equal(h.relay.counts.backends,0);
});
test('invalid upstream upgrade cannot open raw tunnel',async t=>{
  const h=await harness(t,(chunk,s)=>{if(!s.answered){s.answered=true;queueMicrotask(()=>s.push(Buffer.from('HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Accept: wrong\r\n\r\n')));}});
  const c=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\nOrigin: http://127.0.0.1:8089\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n');
  await settle();assert.doesNotMatch(c.text,/101 Switching/);assert.equal(h.relay.counts.backends,0);
});
test('child transport keeps stderr out of bytes, propagates binary, and bounds stderr',async()=>{
  const child=new EventEmitter();child.stdin=new PassThrough();child.stdout=new PassThrough();child.stderr=new PassThrough();
  let kills=0;child.kill=()=>{kills++;};
  const stream=childDuplex(child);let out=Buffer.alloc(0);stream.on('data',b=>{out=Buffer.concat([out,b]);});
  const errors=[];stream.on('error',e=>errors.push(e));
  child.stderr.write('not a response');child.stdout.write(Buffer.from([0,255,1]));await settle();
  assert.deepEqual(out,Buffer.from([0,255,1]));
  child.stderr.write(Buffer.alloc(4097));await settle();assert.equal(stream.destroyed,true);assert.equal(child.stdin.writableEnded,true);assert.equal(kills,0);assert.equal(errors.length,1);
  child.emit('close',0,null);assert.equal(await stream.processClosed,true);
});
test('adapter creation and module import do not spawn or bind',()=>{
  let calls=0;
  dockerAdapter({dockerPath:'/absolute/docker',endpoint:'unix:///Users/titocr/.orbstack/run/docker.sock',expected,
    spawnProcess:()=>{calls++;throw new Error('Unexpected call');}});
  assert.equal(calls,0);
});

test('oversized streaming body aborts backend and prevents further input',async t=>{
  const h=await harness(t,()=>{},{...LIMITS,body:4});
  const c=h.connect('POST / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\nTransfer-Encoding: chunked\r\n\r\n');
  await settle();c.push(Buffer.from('5\r\n12345\r\n0\r\n\r\n'));await settle();
  assert.equal(h.opens,1);assert.equal(h.streams[0].destroyed,true);assert.equal(h.relay.counts.backends,0);
});
test('abrupt frontend disconnect closes backend',async t=>{
  const h=await harness(t,()=>{});const c=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');
  await settle();c.destroy();await settle();assert.equal(h.streams[0].destroyed,true);assert.equal(h.relay.counts.backends,0);
});
test('invalid upstream response framing fails rather than reaching browser',async t=>{
  const h=await harness(t,(_chunk,s)=>{if(!s.answered){s.answered=true;queueMicrotask(()=>s.push(Buffer.from(
    'HTTP/1.1 200 OK\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n')));}});
  const c=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');await settle();
  assert.match(c.text,/502/);assert.doesNotMatch(c.text,/200 OK/);
});
test('connection-nominated Host and Origin cannot alter backend routing identity',async t=>{
  const h=await harness(t,httpBackend);
  h.connect('GET / HTTP/1.1\r\nHost: localhost:8089\r\nOrigin: http://localhost:8089\r\nConnection: host, origin\r\n\r\n');
  await settle();assert.match(h.streams[0].text,/host: localhost:8089/i);assert.match(h.streams[0].text,/origin: http:\/\/localhost:8089/i);
});
test('stalled frontend sockets count toward cap before headers complete',async t=>{
  const h=await harness(t,()=>{},{...LIMITS,clients:1});
  h.connect('GET / HTTP/1.1\r\n');const second=h.connect('GET / HTTP/1.1\r\n');await settle();
  assert.equal(second.destroyed,true);assert.equal(h.opens,0);
});
test('monitor loss during active request closes both streams and reports cause',async t=>{
  const h=await harness(t,()=>{});const c=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');await settle();
  h.monitorLost();const result=await h.relay.finished;
  assert.equal(result.reason,'containment-or-monitor-failure');assert.equal(c.destroyed,true);assert.equal(h.streams[0].destroyed,true);
});
test('backend slot retained until exec child closes; uncertain cleanup stops session',async t=>{
  let release;
  const h=await harness(t,()=>{},{...LIMITS,backends:1});
  const c=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');await settle();
  h.streams[0].processClosed=new Promise(resolve=>{release=resolve;});
  c.destroy();await settle();assert.equal(h.relay.counts.backends,1);
  const second=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');await settle();assert.match(second.text,/503/);
  release(false);await settle();assert.equal(h.relay.stopping,true);assert.equal(h.finalized,1);
});
test('transport obeys backpressure and preserves full binary input',async()=>{
  const child=new EventEmitter();child.stdin=new PassThrough({highWaterMark:1024});child.stdout=new PassThrough({highWaterMark:1024});child.stderr=new PassThrough();child.kill=()=>{};
  const s=childDuplex(child);s.on('error',()=>{});
  const payload=Buffer.alloc(131072,0xfd);assert.equal(s.write(payload),false);
  let received=Buffer.alloc(0);child.stdin.on('data',b=>{received=Buffer.concat([received,b]);});
  await settle();assert.deepEqual(received,payload);
  s.destroy();child.emit('close',0,null);await s.processClosed;
});

test('connect deadline closes stalled backend without opening another target',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const h=await harness(t,()=>{},{...LIMITS,connectMs:10});
  const c=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');await settle();
  t.mock.timers.tick(11);await settle();assert.match(c.text,/502/);assert.equal(h.relay.counts.backends,0);
});
test('session deadline finalizes the dedicated candidate',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});const h=await harness(t,()=>{},{...LIMITS,sessionMs:15});
  t.mock.timers.tick(16);await settle();assert.equal((await h.relay.finished).reason,'session-deadline');assert.equal(h.finalized,1);
});
test('child cleanup deadline escalates and reports uncertain remote cleanup',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const c=new EventEmitter();c.stdin=new PassThrough();c.stdout=new PassThrough();c.stderr=new PassThrough();
  const signals=[];c.kill=s=>signals.push(s);
  const s=childDuplex(c,{...LIMITS,drainMs:5});s.on('error',()=>{});s.destroy();
  t.mock.timers.tick(5);assert.deepEqual(signals,['SIGTERM']);t.mock.timers.tick(5);
  assert.equal(await s.processClosed,false);assert.deepEqual(signals,['SIGTERM','SIGKILL']);
});
test('backend spawn failure sends a bounded failure response',async t=>{
  const h=await harness(t,(_b,s)=>queueMicrotask(()=>s.destroy(new Error('injected spawn failure'))));
  const c=h.connect('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n');await settle();
  assert.match(c.text,/502/);assert.equal(h.relay.counts.backends,0);
});
test('failed finalization is observable rather than reported as successful cleanup',async()=>{
  const adapter={inspect:async()=>info(),watch:()=>()=>{},openBackend:()=>{throw Error('unused');},finalize:async()=>{throw Error('stop failed');}};
  const r=await prepareRelay({expected,adapter});await assert.rejects(r.close(),/stop failed/);
  assert.equal((await r.finished).ok,false);
});

test('only an un-escalated zero exit without a signal proves helper completion',async()=>{
  for(const [code,signal,clean] of [[0,null,true],[1,null,false],[null,'SIGTERM',false],[null,'SIGKILL',false],[null,null,false]]){
    const c=new EventEmitter();c.stdin=new PassThrough();c.stdout=new PassThrough();c.stderr=new PassThrough();c.kill=()=>{};
    const s=childDuplex(c);s.on('error',()=>{});
    c.emit('close',code,signal);
    assert.equal(await s.processClosed,clean,`${code}/${signal}`);
    if(!clean)assert.equal(s.destroyed,true);
    s.destroy();
  }
});
test('a zero exit after drain escalation still cannot prove helper completion',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const c=new EventEmitter();c.stdin=new PassThrough();c.stdout=new PassThrough();c.stderr=new PassThrough();
  c.kill=()=>c.emit('close',0,null);
  const s=childDuplex(c,{...LIMITS,drainMs:5});s.on('error',()=>{});s.destroy();
  t.mock.timers.tick(5);assert.equal(await s.processClosed,false);
});
test('SIGTERM closing CLI before second timer stops session instead of releasing a reusable slot',async t=>{
  t.mock.timers.enable({apis:['setTimeout']});
  const c=new EventEmitter();c.stdin=new PassThrough();c.stdout=new PassThrough();c.stderr=new PassThrough();
  c.stdin.resume();const signals=[];let finalized=0;
  c.kill=signal=>{signals.push(signal);c.emit('close',null,signal);};
  const backend=childDuplex(c,{...LIMITS,drainMs:5});
  const adapter={inspect:async()=>info(),watch:()=>()=>{},openBackend:()=>backend,finalize:async()=>{finalized++;}};
  const relay=await prepareRelay({expected,adapter});t.after(()=>relay.close());
  const client=new MemorySocket();client.on('error',()=>{});relay.server.emit('connection',client);
  client.push(Buffer.from('GET / HTTP/1.1\r\nHost: 127.0.0.1:8089\r\n\r\n'));await settle();
  client.destroy();await settle();assert.equal(relay.counts.backends,1);
  t.mock.timers.tick(5);await settle();
  assert.equal(await backend.processClosed,false);assert.equal(relay.stopping,true);assert.equal(finalized,1);
  assert.equal((await relay.finished).reason,'containment-or-monitor-failure');
  t.mock.timers.tick(5);assert.deepEqual(signals,['SIGTERM']);
});

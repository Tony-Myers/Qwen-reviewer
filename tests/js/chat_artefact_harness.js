#!/usr/bin/env node
// Behavioural harness for the per-review artefact controls in app/chat.html:
// the extraction evidence appendix, the Human Evidence Appendix and the
// Development-mode trace.
//
// It extracts the page's top-level function declarations, runs them in an
// isolated VM context against a small fake DOM and a controllable fake fetch,
// and prints one JSON object of observations. No browser, server, network or
// model is involved; every response is synthetic and supplied by this file.
//
// Usage: node tests/js/chat_artefact_harness.js [path/to/chat.html]
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const htmlPath = process.argv[2] || path.join(__dirname, '..', '..', 'app', 'chat.html');
const html = fs.readFileSync(htmlPath, 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) throw new Error('No inline <script> block found in ' + htmlPath);
const script = scriptMatch[1];

// ---------------------------------------------------------------------------
// Extract top-level declarations. The scanner skips strings, template
// literals, comments and regular-expression literals so that braces inside
// them do not affect the depth count.
// ---------------------------------------------------------------------------
function scanToEnd(src, start) {
  // Returns the index just after the block that opens at the first '{' found
  // at or after `start` (at depth 0) and closes back to depth 0.
  let i = start;
  let depth = 0;
  let opened = false;
  let prevSignificant = '';
  const templateStack = [];
  while (i < src.length) {
    const c = src[i];
    const n = src[i + 1];
    if (c === '/' && n === '/') { i = src.indexOf('\n', i); if (i < 0) return src.length; continue; }
    if (c === '/' && n === '*') { i = src.indexOf('*/', i + 2) + 2; continue; }
    if (c === '\'' || c === '"') {
      i++;
      while (i < src.length && src[i] !== c) { if (src[i] === '\\') i++; i++; }
      i++; prevSignificant = 'a'; continue;
    }
    if (c === '`') {
      i++;
      while (i < src.length && src[i] !== '`') {
        if (src[i] === '\\') { i += 2; continue; }
        if (src[i] === '$' && src[i + 1] === '{') {
          // Skip the embedded expression by recursive brace scanning.
          const end = scanToEnd(src, i + 1);
          i = end; continue;
        }
        i++;
      }
      i++; prevSignificant = 'a'; continue;
    }
    if (c === '/' && (prevSignificant === '' || '(,=:[!&|?{};+-*%<>~^'.includes(prevSignificant))) {
      // Regular-expression literal.
      i++;
      let inClass = false;
      while (i < src.length) {
        const r = src[i];
        if (r === '\\') { i += 2; continue; }
        if (r === '[') inClass = true;
        else if (r === ']') inClass = false;
        else if (r === '/' && !inClass) break;
        i++;
      }
      i++;
      while (/[a-z]/i.test(src[i] || '')) i++;
      prevSignificant = 'a';
      continue;
    }
    if (c === '{') { depth++; opened = true; }
    else if (c === '}') {
      depth--;
      if (opened && depth === 0) return i + 1;
    }
    if (!/\s/.test(c)) prevSignificant = /[\w$)\]]/.test(c) ? 'a' : c;
    i++;
  }
  throw new Error('Unbalanced block starting at ' + start);
}

const declarations = [];
const declRe = /^(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/gm;
let m;
while ((m = declRe.exec(script)) !== null) {
  const end = scanToEnd(script, m.index);
  declarations.push({ name: m[1], code: script.slice(m.index, end) });
  declRe.lastIndex = end;
}
function constObject(name) {
  const re = new RegExp('^const\\s+' + name + '\\s*=\\s*\\{', 'm');
  const found = re.exec(script);
  if (!found) return '';
  const end = scanToEnd(script, found.index);
  return script.slice(found.index, end) + ';';
}

// ---------------------------------------------------------------------------
// Fake DOM. Elements are created for every id="..." in HTML assigned to
// #reportArea, which is how showReport() replaces the review controls.
// ---------------------------------------------------------------------------
class FakeElement {
  constructor(doc, id, html) {
    this._doc = doc;
    this.id = id;
    this._inner = '';
    this.textContent = '';
    this.disabled = false;
    this.value = undefined;
    this.placeholder = '';
    this.style = { display: html && /style="[^"]*display:\s*none/.test(html) ? 'none' : '' };
  }
  get innerHTML() { return this._inner; }
  set innerHTML(v) {
    this._inner = String(v);
    if (this.id === 'reportArea') this._doc._rebuild(this._inner);
  }
  scrollIntoView() {}
  appendChild() {}
}

class FakeDocument {
  constructor() {
    this.elements = {};
    this.elements.reportArea = new FakeElement(this, 'reportArea', '');
    this.downloads = [];
  }
  _rebuild(html) {
    const keep = this.elements.reportArea;
    this.elements = { reportArea: keep };
    const tagRe = /<[^>]*\bid="([^"]+)"[^>]*>/g;
    let t;
    while ((t = tagRe.exec(html)) !== null) {
      this.elements[t[1]] = new FakeElement(this, t[1], t[0]);
    }
  }
  getElementById(id) { return this.elements[id] || null; }
  createElement() {
    const doc = this;
    return {
      href: '', download: '',
      click() { doc.downloads.push({ name: this.download, href: this.href }); }
    };
  }
  querySelectorAll() { return []; }
}

function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return { promise, resolve };
}

function makeContext() {
  const doc = new FakeDocument();
  const blobs = {};
  let blobCounter = 0;
  const fetchLog = [];
  const pending = [];
  const ctx = {
    console: { log() {}, error() {}, warn() {} },
    document: doc,
    window: { location: { origin: 'http://harness.invalid' } },
    alert() {},
    Blob: class { constructor(parts, opts) { this.parts = parts; this.type = opts && opts.type; } },
    URL: {
      createObjectURL(blob) { const key = 'blob:' + (++blobCounter); blobs[key] = blob; return key; },
      revokeObjectURL() {}
    },
    navigator: { clipboard: { writeText: () => Promise.resolve() } },
    selectedFile: null,
    renderMd: md => '<div class="md">' + md + '</div>',
    fetch(url) {
      fetchLog.push(url);
      const d = deferred();
      pending.push({ url, d });
      return d.promise;
    },
    _blobs: blobs,
    _fetchLog: fetchLog,
    _pending: pending,
  };
  vm.createContext(ctx);
  const names = new Set(declarations.map(d => d.name));
  let code = 'const BASE = window.location.origin;\nlet currentJobId = null;\nlet selectedFile = null;\n';
  code += constObject('ASK_MODES') + '\n';
  for (const d of declarations) {
    if (d.name === 'renderMd') continue; // replaced by the stub above
    code += d.code + '\n';
  }
  code += 'globalThis.__get = n => eval(n);\n';
  vm.runInContext(code, ctx, { filename: 'chat-extract.js' });
  ctx.has = n => names.has(n);
  ctx.currentJob = () => ctx.__get('currentJobId');
  return ctx;
}

function response(status, body) {
  const json = deferred();
  return {
    status, ok: status >= 200 && status < 300,
    json: () => { json.resolve(body); return json.promise; },
  };
}
function delayedJsonResponse(status, body) {
  const json = deferred();
  return {
    resp: { status, ok: status >= 200 && status < 300, json: () => json.promise },
    release: () => json.resolve(body),
  };
}
const tick = () => new Promise(r => setImmediate(r));
async function settle() { for (let i = 0; i < 10; i++) await tick(); }

function respondTo(ctx, fragment, resp) {
  const idx = ctx._pending.findIndex(p => p.url.includes(fragment));
  if (idx < 0) throw new Error('No pending fetch for ' + fragment + '; log=' + JSON.stringify(ctx._fetchLog));
  const [p] = ctx._pending.splice(idx, 1);
  p.d.resolve(resp);
}

function traceFor(job, label) {
  return {
    job_id: job,
    pipeline: 'synthetic-pipeline',
    files: [{ source_name: 'Synthetic source ' + label, source_chunks: ['Synthetic chunk ' + label] }],
    final_synthesis: [],
    final_report: 'Synthetic final report ' + label,
  };
}
function envelope(job, label) {
  return { trace: traceFor(job, label), filename: 'synthetic_' + label + '_review_trace.json' };
}
// Job identity of whatever a function returned, whether an inner trace or an
// (incorrect) endpoint envelope.
function jobOf(value) {
  if (!value || typeof value !== 'object') return value == null ? null : 'non-object';
  if (typeof value.job_id === 'string') return value.job_id;
  if (value.trace && typeof value.trace === 'object' && typeof value.trace.job_id === 'string') return value.trace.job_id;
  return 'unknown';
}
function downloadedJson(ctx) {
  const last = ctx.document.downloads[ctx.document.downloads.length - 1];
  if (!last) return null;
  const blob = ctx._blobs[last.href];
  return { name: last.name, value: JSON.parse(blob.parts.join('')) };
}
function sectionHtml(ctx, id) {
  const el = ctx.document.getElementById(id);
  return el ? el.innerHTML : null;
}
function showReport(ctx, job, opts) {
  ctx.showReport('# Synthetic report ' + job, !!opts.appendix, job, !!opts.trace, !!opts.human);
}

// ---------------------------------------------------------------------------
// Scenarios
// ---------------------------------------------------------------------------
const scenarios = {};

// Trace envelope: the endpoint envelope must be unwrapped before rendering and download.
scenarios.envelope_rendering = async () => {
  const ctx = makeContext();
  showReport(ctx, 'FAKE-A', { trace: true });
  const toggle = ctx.fetchAndToggleDevelopmentTrace();
  await settle();
  respondTo(ctx, '/api/review/trace/FAKE-A', response(200, envelope('FAKE-A', 'alpha')));
  await toggle;
  await settle();
  const shown = sectionHtml(ctx, 'developmentTraceSection') || '';
  await ctx.dlDevelopmentTrace();
  const dl = downloadedJson(ctx);
  return {
    displays_source_name: shown.includes('Synthetic source alpha'),
    displays_source_chunk: shown.includes('Synthetic chunk alpha'),
    displays_no_per_file_message: shown.includes('No per-file trace data are available'),
    download_is_inner_trace: !!dl && dl.value.job_id === 'FAKE-A' && Array.isArray(dl.value.files) && !('trace' in dl.value),
    download_name: dl ? dl.name : null,
    second_fetch_used_cache: ctx._fetchLog.filter(u => u.includes('/trace/FAKE-A')).length === 1,
  };
};

// Trace envelope: a malformed endpoint body is not rendered or downloaded as a trace.
scenarios.malformed_envelope = async () => {
  const results = {};
  for (const [label, body] of [['missing_trace', { filename: 'x.json' }],
                               ['array_trace', { trace: [], filename: 'x.json' }],
                               ['string_trace', { trace: 'text', filename: 'x.json' }],
                               ['other_job_trace', envelope('FAKE-OTHER', 'other')]]) {
    const ctx = makeContext();
    showReport(ctx, 'FAKE-A', { trace: true });
    const toggle = ctx.fetchAndToggleDevelopmentTrace();
    await settle();
    respondTo(ctx, '/api/review/trace/FAKE-A', response(200, body));
    await toggle;
    await settle();
    const shown = sectionHtml(ctx, 'developmentTraceSection') || '';
    results[label] = {
      reported_unavailable: shown.includes('could not be loaded'),
      rendered_trace_view: shown.includes('Development Trace — local debugging material'),
    };
  }
  return results;
};

// Cross-job race: job A's response arrives after job B (Development mode ON) is shown.
// Two timings: the fetch itself resolves late, or the body (json) resolves late.
scenarios.late_response_after_switch_on = async () => {
  const out = {};
  for (const timing of ['late_fetch', 'late_body']) {
    const ctx = makeContext();
    showReport(ctx, 'FAKE-A', { trace: true });
    const toggleA = ctx.fetchAndToggleDevelopmentTrace();
    await settle();
    let release = null;
    if (timing === 'late_body') {
      const delayed = delayedJsonResponse(200, envelope('FAKE-A', 'alpha'));
      respondTo(ctx, '/api/review/trace/FAKE-A', delayed.resp);
      await settle();
      release = delayed.release;
    }
    showReport(ctx, 'FAKE-B', { trace: true });
    if (timing === 'late_fetch') {
      respondTo(ctx, '/api/review/trace/FAKE-A', response(200, envelope('FAKE-A', 'alpha')));
    } else {
      release();
    }
    await toggleA;
    await settle();
    const afterLateA = sectionHtml(ctx, 'developmentTraceSection') || '';
    // Now job B's own request.
    const fetchB = ctx.fetchDevelopmentTrace();
    await settle();
    const bFetched = ctx._fetchLog.some(u => u.includes('/api/review/trace/FAKE-B'));
    if (bFetched) respondTo(ctx, '/api/review/trace/FAKE-B', response(200, envelope('FAKE-B', 'beta')));
    const traceB = await fetchB;
    await ctx.dlDevelopmentTrace();
    const dl = downloadedJson(ctx);
    out[timing] = {
      current_job: ctx.currentJob(),
      b_section_shows_a: afterLateA.includes('alpha'),
      b_requested_own_trace: bFetched,
      b_received_job: jobOf(traceB),
      b_download_job: dl ? jobOf(dl.value) : null,
    };
  }
  return out;
};

// Cross-job race: job A's response arrives after job B (Development mode OFF) is shown.
scenarios.late_response_after_switch_off = async () => {
  const ctx = makeContext();
  showReport(ctx, 'FAKE-A', { trace: true, appendix: true });
  const toggleA = ctx.fetchAndToggleDevelopmentTrace();
  await settle();
  showReport(ctx, 'FAKE-B', { trace: false, appendix: true });
  respondTo(ctx, '/api/review/trace/FAKE-A', response(200, envelope('FAKE-A', 'alpha')));
  await toggleA;
  await settle();
  const reportHtml = ctx.document.getElementById('reportArea').innerHTML;
  // A direct request in B's context must go to B's endpoint, which refuses it.
  const fetchB = ctx.fetchDevelopmentTrace();
  await settle();
  const bFetched = ctx._fetchLog.some(u => u.includes('/api/review/trace/FAKE-B'));
  if (bFetched) respondTo(ctx, '/api/review/trace/FAKE-B', response(404, { error: 'Development trace not enabled for this review' }));
  const traceB = await fetchB;
  return {
    current_job: ctx.currentJob(),
    b_has_trace_controls: ctx.document.getElementById('developmentTraceToggle') !== null,
    b_page_shows_a: reportHtml.includes('alpha'),
    b_requested_own_trace: bFetched,
    b_received_job: jobOf(traceB),
    downloads: ctx.document.downloads.length,
  };
};

// Both appendices are separate artefacts with separate controls and endpoints.
scenarios.two_appendices = async () => {
  const ctx = makeContext();
  showReport(ctx, 'FAKE-A', { appendix: true, human: true });
  const ids = ['appendixToggle', 'appendixDownload', 'humanAppendixToggle', 'humanAppendixDownload'];
  const present = Object.fromEntries(ids.map(id => [id, ctx.document.getElementById(id) !== null]));
  const labels = Object.fromEntries(ids.map(id => {
    const tag = ctx.document.getElementById('reportArea').innerHTML.match(new RegExp('id="' + id + '"[^>]*>([^<]*)<'));
    return [id, tag ? tag[1] : null];
  }));
  const out = { controls_present: present, labels };
  if (!ctx.has('fetchAndToggleHumanAppendix')) {
    out.human_functions_missing = true;
    return out;
  }
  const t1 = ctx.fetchAndToggleAppendix();
  await settle();
  respondTo(ctx, '/api/review/appendix/FAKE-A', response(200, { appendix: '# Evidence appendix\nSynthetic extraction A' }));
  await t1;
  const t2 = ctx.fetchAndToggleHumanAppendix();
  await settle();
  respondTo(ctx, '/api/review/human-appendix/FAKE-A', response(200, { human_appendix: '# Human Evidence Appendix\nSynthetic cards A' }));
  await t2;
  await settle();
  out.extraction_section = (sectionHtml(ctx, 'appendixSection') || '').includes('Synthetic extraction A');
  out.human_section = (sectionHtml(ctx, 'humanAppendixSection') || '').includes('Synthetic cards A');
  out.extraction_section_has_human = (sectionHtml(ctx, 'appendixSection') || '').includes('Synthetic cards A');
  await ctx.dlAppendix();
  await ctx.dlHumanAppendix();
  out.download_names = ctx.document.downloads.map(d => d.name);
  out.download_bodies = ctx.document.downloads.map(d => ctx._blobs[d.href].parts.join(''));
  return out;
};

// An appendix response for job A is not shown or cached under job B.
scenarios.late_appendix_after_switch = async () => {
  const out = {};
  for (const kind of ['extraction', 'human']) {
    const ctx = makeContext();
    if (kind === 'human' && !ctx.has('fetchAndToggleHumanAppendix')) { out[kind] = 'missing'; continue; }
    showReport(ctx, 'FAKE-A', { appendix: true, human: true });
    const toggle = kind === 'human' ? ctx.fetchAndToggleHumanAppendix() : ctx.fetchAndToggleAppendix();
    await settle();
    showReport(ctx, 'FAKE-B', { appendix: true, human: true });
    const endpoint = kind === 'human' ? '/api/review/human-appendix/FAKE-A' : '/api/review/appendix/FAKE-A';
    const field = kind === 'human' ? 'human_appendix' : 'appendix';
    respondTo(ctx, endpoint, response(200, { [field]: 'Appendix text for job A' }));
    await toggle;
    await settle();
    const secId = kind === 'human' ? 'humanAppendixSection' : 'appendixSection';
    const fetchB = kind === 'human' ? ctx.fetchHumanAppendix() : ctx.fetchAppendix();
    await settle();
    const bEndpoint = endpoint.replace('FAKE-A', 'FAKE-B');
    const bFetched = ctx._fetchLog.some(u => u.includes(bEndpoint));
    if (bFetched) respondTo(ctx, bEndpoint, response(200, { [field]: 'Appendix text for job B' }));
    const textB = await fetchB;
    out[kind] = {
      b_section_shows_a: (sectionHtml(ctx, secId) || '').includes('job A'),
      b_requested_own: bFetched,
      b_received: textB,
    };
  }
  return out;
};

(async () => {
  const results = { functions: declarations.map(d => d.name).sort() };
  for (const [name, fn] of Object.entries(scenarios)) {
    try {
      results[name] = await fn();
    } catch (e) {
      results[name] = { error: String(e && e.stack || e) };
    }
  }
  process.stdout.write(JSON.stringify(results, null, 2) + '\n');
})();

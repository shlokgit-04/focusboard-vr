let API = '';
async function loadConfig() {
  if (API) return;
  try { const r = await fetch(new URL('config.json', location.href), { cache: 'no-store' });
    API = (await r.json()).apiBase || ''; } catch { API = ''; }
}
function token() { return localStorage.getItem('fb_token') || ''; }
function saveToken(t) { t ? localStorage.setItem('fb_token', t) : localStorage.removeItem('fb_token'); }
function qs(name) { return new URLSearchParams(location.search).get(name) || ''; }
async function api(path, opts = {}) {
  const headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
  const t = token(); if (t) headers['Authorization'] = 'Bearer ' + t;
  const r = await fetch(API.replace(/\/$/, '') + path, Object.assign({}, opts, { headers }));
  let body = {};
  try { body = await r.json(); } catch { body = {}; }
  if (r.status === 401 && token()) { saveToken(''); location.href = 'login.html?next=' + encodeURIComponent(location.pathname.split('/').pop()); }
  if (!r.ok) throw new Error(body.error || ('Request failed (' + r.status + ')'));
  return body;
}
function msg(el, text, kind) { el.textContent = text || ''; el.className = 'msg' + (text ? ' ' + (kind || 'err') : ''); }
const COLORS = { amber: 'Amber', sage: 'Sage', sky: 'Sky', rose: 'Rose' };

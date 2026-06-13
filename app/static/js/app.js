/* ── Global App JS ─────────────────────────────────────────── */

// ── Toast system ──────────────────────────────────────────────
window.toast = (function () {
  let container = null;

  function getContainer() {
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    return container;
  }

  return {
    show(message, type = 'info', duration = 3500) {
      const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
      const el = document.createElement('div');
      el.className = `toast ${type}`;
      el.innerHTML = `<span>${icons[type] || '•'}</span><span>${message}</span>`;
      getContainer().appendChild(el);
      setTimeout(() => {
        el.style.animation = 'slide-in 0.2s ease reverse';
        setTimeout(() => el.remove(), 200);
      }, duration);
    },
    success: (msg, d) => window.toast.show(msg, 'success', d),
    error: (msg, d) => window.toast.show(msg, 'error', d),
    info: (msg, d) => window.toast.show(msg, 'info', d),
    warning: (msg, d) => window.toast.show(msg, 'warning', d),
  };
})();

// ── API helper ────────────────────────────────────────────────
const MR_ID = document.getElementById('mr-id-meta')?.dataset.mrId
  || '00000000-0000-0000-0000-000000000001';

window.api = {
  async request(method, url, body = null) {
    const opts = {
      method,
      headers: { 'Content-Type': 'application/json', 'X-MR-ID': MR_ID },
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const msg = data?.detail?.message || data?.detail || '操作失败';
      throw new Error(msg);
    }
    return data;
  },
  get: (url) => window.api.request('GET', url),
  post: (url, body) => window.api.request('POST', url, body),
  put: (url, body) => window.api.request('PUT', url, body),
  delete: (url) => window.api.request('DELETE', url),
};

// ── Status helpers ────────────────────────────────────────────
window.statusLabel = {
  PLANNED:     '计划中',
  CHECKED_IN:  '已签到',
  CHECKED_OUT: '已签退',
  COMPLETED:   '已完成',
};

window.complianceLabel = {
  COMPLIANT:       '合规',
  MINOR_VIOLATION: '轻微违规',
  MAJOR_VIOLATION: '严重违规',
};

window.statusBadge = function (status) {
  return `<span class="status-badge status-${status}">${window.statusLabel[status] || status}</span>`;
};

window.complianceBadge = function (result) {
  return `<span class="compliance-badge compliance-${result}">${window.complianceLabel[result] || result}</span>`;
};

// ── Date helpers ──────────────────────────────────────────────
window.fmtDate = function (iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  });
};

window.fmtDateOnly = function (iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
};

// ── Get next week monday/sunday ───────────────────────────────
window.getNextWeekRange = function () {
  const now = new Date();
  const day = now.getDay(); // 0=Sun
  const daysToMonday = day === 0 ? 1 : 8 - day;
  const nextMonday = new Date(now);
  nextMonday.setDate(now.getDate() + daysToMonday);
  nextMonday.setHours(0, 0, 0, 0);
  const nextSunday = new Date(nextMonday);
  nextSunday.setDate(nextMonday.getDate() + 6);
  nextSunday.setHours(23, 59, 59, 0);
  return { start: nextMonday, end: nextSunday };
};

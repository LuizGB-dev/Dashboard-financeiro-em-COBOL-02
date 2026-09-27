let token = localStorage.token;
let dashboardData = null;
let reminders = [];
let calendarCursor = new Date();
let valuesHidden = false;

const $ = (id) => document.getElementById(id);
const money = (value) => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value || 0);

async function api(path, options = {}) {
  options.headers = { ...(options.headers || {}), 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) };
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    let message = await response.text();
    try { message = JSON.parse(message).detail || message; } catch { /* plain text response */ }
    throw new Error(message || `Erro ${response.status}`);
  }
  return response.json();
}

function setMessage(message, type = 'error') {
  const target = $('authMessage');
  target.textContent = message;
  target.className = `form-message ${type}`;
}

async function withLoading(button, loadingText, action) {
  const old = button.textContent;
  button.disabled = true;
  button.textContent = loadingText;
  try { return await action(); } finally { button.disabled = false; button.textContent = old; }
}

function toggleRegister() {
  $('loginForm').hidden = !$('loginForm').hidden;
  $('registerForm').hidden = !$('registerForm').hidden;
  $('reset').hidden = true;
  setMessage('', '');
}

function showReset() {
  $('loginForm').hidden = !$('loginForm').hidden;
  $('registerForm').hidden = true;
  $('reset').hidden = !$('reset').hidden;
  $('resetEmail').value = $('email').value;
  setMessage('', '');
}

async function login() {
  const button = document.querySelector('#loginForm .primary');
  try {
    const result = await withLoading(button, 'Entrando...', () => api('/auth/login', { method: 'POST', body: JSON.stringify({ email: $('email').value, password: $('password').value }) }));
    token = localStorage.token = result.token;
    await load();
  } catch (error) { setMessage(error.message); }
}

async function register() {
  const password = $('registerPassword').value;
  if (password.length < 6) return setMessage('A senha deve ter no mínimo 6 caracteres.');
  if (password !== $('confirmation').value) return setMessage('As senhas informadas não coincidem.');
  const button = document.querySelector('#registerForm .primary');
  try {
    const result = await withLoading(button, 'Criando conta...', () => api('/auth/register', { method: 'POST', body: JSON.stringify({ name: $('name').value, email: $('registerEmail').value, password, confirmation: $('confirmation').value }) }));
    token = localStorage.token = result.token;
    await load();
  } catch (error) { setMessage(error.message); }
}

async function requestReset() {
  try {
    const result = await api('/auth/password-reset/request', { method: 'POST', body: JSON.stringify({ email: $('resetEmail').value }) });
    setMessage(result.message, 'success');
  } catch (error) { setMessage(error.message); }
}

async function confirmReset() {
  if ($('newPassword').value.length < 6) return setMessage('A nova senha deve ter no mínimo 6 caracteres.');
  if ($('newPassword').value !== $('newConfirmation').value) return setMessage('As senhas informadas não coincidem.');
  try {
    const result = await api('/auth/password-reset/confirm', { method: 'POST', body: JSON.stringify({ email: $('resetEmail').value, code: $('resetCode').value, password: $('newPassword').value, confirmation: $('newConfirmation').value }) });
    setMessage(result.message, 'success');
  } catch (error) { setMessage(error.message); }
}

function logout() { localStorage.clear(); location.reload(); }
function togglePrivacy() { valuesHidden = !valuesHidden; renderDashboard(); }
function displayAmount(value) { return valuesHidden ? '••••••' : money(value); }
function toggleTheme() { document.body.classList.toggle('dark'); }

function goTo(section, button) {
  $(section).scrollIntoView({ behavior: 'smooth', block: 'start' });
  document.querySelectorAll('.nav-link').forEach((item) => item.classList.remove('active'));
  if (button) button.classList.add('active');
}

async function saveSalary() {
  const button = document.querySelector('.income-panel .primary');
  try { await withLoading(button, 'Salvando...', () => api('/salary', { method: 'PUT', body: JSON.stringify({ salary: Number($('salary').value || 0) }) })); await load(); } catch (error) { alert(error.message); }
}

function updateTransactionButton() {
  const isExpense = $('kind').value === 'expense';
  const button = $('transactionButton');
  button.textContent = isExpense ? '− Registrar despesa' : '+ Registrar receita';
  button.className = `btn ${isExpense ? 'danger' : 'success'}`;
}

async function add() {
  const button = $('transactionButton');
  if (!$('desc').value || !Number($('amount').value)) return alert('Informe uma descrição e um valor maior que zero.');
  try {
    await withLoading(button, 'Salvando...', () => api(`/${$('kind').value}`, { method: 'POST', body: JSON.stringify({ description: $('desc').value, amount: Number($('amount').value), category: $('category').value, spent_type: $('spent').value, date: new Date().toISOString().slice(0, 10) }) }));
    $('desc').value = ''; $('amount').value = ''; await load();
  } catch (error) { alert(error.message); }
}

function renderDashboard() {
  if (!dashboardData) return;
  const data = dashboardData;
  $('who').textContent = data.name;
  $('salary').value = data.salary || '';
  $('balanceValue').textContent = displayAmount(data.balance);
  $('privacyButton').textContent = valuesHidden ? '◌' : '◉';
  $('summaryCards').innerHTML = [
    ['↓', 'Entradas no período', data.revenues, 'positive'],
    ['↑', 'Saídas no período', data.expenses, 'negative'],
    ['%', 'Renda utilizada', `${data.used_pct}%`, 'neutral'],
  ].map(([icon, label, value, tone]) => `<article class="summary-card ${tone}"><span class="summary-icon">${icon}</span><p>${label}</p><strong class="currency">${typeof value === 'number' ? displayAmount(value) : valuesHidden ? '••••' : value}</strong></article>`).join('');
  const labels = { necessidades: ['Necessidades', '60%', '#336a9a'], desejos: ['Desejos', '30%', '#9a6b33'], investimentos: ['Poupança e investimentos', '20%', '#24755c'] };
  $('budgetBars').innerHTML = Object.entries(labels).map(([key, [label, percent, color]]) => {
    const planned = data.plan[key] || 0, actual = data.actual[key] || 0, used = planned ? Math.round((actual / planned) * 100) : 0;
    return `<div class="budget-row"><div class="budget-label"><span>${label} <small>${percent} recomendado</small></span><strong>${displayAmount(actual)} <small>de ${displayAmount(planned)}</small></strong></div><div class="progress"><span style="width:${Math.min(used, 100)}%;background:${color}"></span></div><small>${used}% utilizado</small></div>`;
  }).join('');
  renderHistory();
}

function renderHistory() {
  if (!dashboardData) return;
  const type = $('historyType').value, period = $('historyPeriod').value;
  const now = new Date();
  const rows = dashboardData.transactions.filter((item) => {
    const date = new Date(`${item.date}T12:00:00`);
    const typeOk = type === 'all' || item.kind === type;
    const periodOk = period === 'all' || (period === 'month' && date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear()) || (period === '30' && (now - date) / 86400000 <= 30);
    return typeOk && periodOk;
  }).sort((a, b) => b.date.localeCompare(a.date));
  $('history').innerHTML = rows.length ? `<div class="table-head"><span>Data</span><span>Descrição</span><span>Categoria</span><span>Valor</span><span></span></div>${rows.map((item) => `<div class="table-row"><span>${new Date(`${item.date}T12:00:00`).toLocaleDateString('pt-BR')}</span><span><b>${item.kind === 'revenue' ? '↓' : '↑'} ${item.description}</b><small>${item.kind === 'revenue' ? 'Receita' : 'Despesa'}</small></span><span>${item.category}</span><strong class="currency ${item.kind === 'revenue' ? 'positive-text' : 'negative-text'}">${item.kind === 'revenue' ? '+' : '−'} ${displayAmount(item.amount)}</strong><button class="delete-button" onclick="del(${item.id})">Excluir</button></div>`).join('')}` : `<div class="empty-state"><span>▤</span><h3>Nenhum lançamento encontrado</h3><p>Registre uma receita ou despesa para acompanhar sua rotina.</p><button class="btn outline" onclick="goTo('overview')">Registrar lançamento</button></div>`;
}

async function del(id) {
  if (!confirm('Excluir este lançamento? Esta ação não pode ser desfeita.')) return;
  await api(`/transactions/${id}`, { method: 'DELETE' }); await load();
}

async function addReminder() {
  const button = document.querySelector('.reminder-form .primary');
  if (!$('remTitle').value || !$('remDate').value) return alert('Informe o lembrete e a data.');
  try {
    await withLoading(button, 'Salvando...', () => api('/reminders', { method: 'POST', body: JSON.stringify({ title: $('remTitle').value, due_date: $('remDate').value, reminder_type: $('remType').value, amount: $('remAmount').value ? Number($('remAmount').value) : null }) }));
    $('remTitle').value = ''; $('remAmount').value = ''; await loadReminders();
  } catch (error) { alert(error.message); }
}

function changeMonth(change) { calendarCursor = new Date(calendarCursor.getFullYear(), calendarCursor.getMonth() + change, 1); renderCalendar(); }
const reminderMeta = { Conta: ['🏠', 'conta'], Despesa: ['↗', 'despesa'], Recebimento: ['↓', 'recebimento'], Investimento: ['◈', 'investimento'] };

function renderCalendar() {
  const year = calendarCursor.getFullYear(), month = calendarCursor.getMonth();
  const first = new Date(year, month, 1).getDay(), last = new Date(year, month + 1, 0).getDate();
  const byDate = reminders.reduce((result, item) => ((result[item.due_date] ||= []).push(item), result), {});
  $('calendarMonth').textContent = calendarCursor.toLocaleDateString('pt-BR', { month: 'long', year: 'numeric' });
  const week = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'].map((day) => `<div class="weekday">${day}</div>`).join('');
  const blank = Array(first).fill('<div class="calendar-day muted"></div>').join('');
  const days = Array.from({ length: last }, (_, index) => {
    const day = index + 1, key = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const entries = byDate[key] || [];
    return `<div class="calendar-day ${key === new Date().toISOString().slice(0, 10) ? 'today' : ''}"><span>${day}</span>${entries.slice(0, 3).map((entry) => `<button class="calendar-event ${reminderMeta[entry.reminder_type][1]}" title="${entry.reminder_type}: ${entry.title}">${reminderMeta[entry.reminder_type][0]} ${entry.title}</button>`).join('')}${entries.length > 3 ? `<small>+${entries.length - 3} lembrete(s)</small>` : ''}</div>`;
  }).join('');
  $('calendar').innerHTML = `<div class="calendar-grid">${week}${blank}${days}</div>`;
  const current = reminders.filter((item) => item.due_date.startsWith(`${year}-${String(month + 1).padStart(2, '0')}`));
  $('reminderList').innerHTML = current.length ? current.sort((a, b) => a.due_date.localeCompare(b.due_date)).map((item) => `<div class="reminder-item"><span class="reminder-icon ${reminderMeta[item.reminder_type][1]}">${reminderMeta[item.reminder_type][0]}</span><div><b>${item.title}</b><small>${new Date(`${item.due_date}T12:00:00`).toLocaleDateString('pt-BR')} · ${item.reminder_type}${item.amount ? ` · ${money(item.amount)}` : ''}</small></div><button class="delete-button" onclick="delReminder(${item.id})">Excluir</button></div>`).join('') : `<div class="empty-inline">Você ainda não tem lembretes neste mês. <button class="text-button" onclick="$('remTitle').focus()">Adicionar o primeiro</button></div>`;
}

async function delReminder(id) {
  if (!confirm('Excluir este lembrete?')) return;
  await api(`/reminders/${id}`, { method: 'DELETE' }); await loadReminders();
}

async function loadReminders() { reminders = await api('/reminders'); renderCalendar(); }
async function loadInsights() { const result = await api('/insights'); $('insights').innerHTML = result.insights.map((text) => `<article class="insight"><span>◌</span><p>${text}</p></article>`).join('') || '<p class="empty-inline">Registre lançamentos para receber insights.</p>'; }
async function load() { dashboardData = await api('/dashboard'); $('authView').hidden = true; $('app').hidden = false; renderDashboard(); await loadReminders(); await loadInsights(); updateTransactionButton(); }

if (token) load().catch(() => logout());

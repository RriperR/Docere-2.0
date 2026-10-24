#!/usr/bin/env node
/** Создать только новые синтетические данные через публичный API, без seed/reset и AI. */
import { randomUUID } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { createRequire } from 'node:module'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(resolve(root, 'frontend/package.json'))
const { chromium } = require('@playwright/test')
const api = process.env.PRODUCT_DEMO_API_URL ?? 'http://localhost:8012/api'
const web = process.env.PRODUCT_DEMO_WEB_URL ?? 'http://127.0.0.1:4174'
const adminEmail = process.env.PRODUCT_DEMO_ADMIN_EMAIL ?? 'product-admin@docere.demo'
const adminPassword = process.env.PRODUCT_DEMO_ADMIN_PASSWORD ?? 'ProductDemo123'
const password = 'ProductDemo123'
const run = `${new Date().toISOString().replace(/\D/g, '').slice(0, 14)}-${randomUUID().slice(0, 8)}`
const output = resolve(process.env.PRODUCT_DEMO_OUTPUT ?? resolve(root, 'artifacts/product-demo', run))

async function call(path, token, body, method = body ? 'POST' : 'GET') {
  const response = await fetch(`${api}${path}`, {
    method, headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body && !(body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}) },
    body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined,
  })
  if (!response.ok) throw new Error(`${method} ${path}: ${response.status} ${await response.text()}`)
  return response.json()
}
const login = async (email, secret = password) => (await call('/auth/login', null, { email, password: secret })).access_token

const documents = [
  { date: '2026-09-16', title: 'Консультация терапевта · сердцебиение', type: 'consultation_result', name: 'consultation', section: 'Первичное обращение', summary: 'Учебный пример: эпизоды сердцебиения после нагрузки. Уточнить связь жалоб с ритмом по дневнику и мониторированию.', rows: [['Жалобы', 'Короткие эпизоды сердцебиения после подъёма по лестнице.'], ['Анамнез', 'Симптомы отмечает около трёх недель; дневник ранее не вела.'], ['Обследование', 'ЭКГ и суточное мониторирование с дневником жалоб.']] },
  { date: '2026-09-19', title: 'ЭКГ · исходное исследование', type: 'exam_result', name: 'ecg', section: 'Инструментальное исследование', summary: 'Учебный пример: на ЭКГ синусовый ритм. Короткая запись не охватывает описанные пациенткой эпизоды.', rows: [['Ритм', 'Синусовый, частота 76 в минуту.'], ['Время записи', 'Утро, в покое; жалоб во время записи не отмечено.'], ['Примечание', 'Для обсуждения нужно сопоставление с дневником симптомов.']] },
  { date: '2026-09-25', title: 'Мониторирование · дневник и заключение', type: 'exam_result', name: 'monitoring', section: 'Суточное наблюдение', summary: 'Учебный пример: два эпизода жалоб отмечены в дневнике. В документе время одной записи дневника требует уточнения.', rows: [['Дневник', '09:20 — лестница; 18:10 — прогулка, ощущение сердцебиения.'], ['Документ', 'Основной ритм синусовый. Отдельно описаны эпизоды учащения.'], ['Пробел данных', 'Одна отметка времени в скане неразборчива; уточнить у автора.']] },
]
const question = 'Как сопоставить жалобы с ЭКГ и мониторированием? Какие данные необходимо уточнить до завершения разбора?'
const opinionText = 'Проверьте сопоставление двух эпизодов из дневника с мониторированием. Достаточно ли материалов для итога и что следует уточнить?'
const replyText = 'Синтетический ответ врача для показа рабочего процесса. ЭКГ выполнена в покое без жалоб; отдельно нужно сверить время записей дневника с мониторированием. Предлагаю уточнить неразборчивую отметку времени у автора документа и сохранить это ограничение в итоге.'
const summary = 'Синтетический учебный итог: три документа собраны в одну последовательность; мнение кардиолога связано с мониторированием. Сопоставление одной отметки дневника остаётся неуточнённым.'

function html(doc) {
  return `<!doctype html><html lang="ru"><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;background:#e9eff5;font:18px/1.6 Arial,sans-serif;color:#22364b;padding:38px}.paper{background:white;min-height:980px;border-radius:14px;overflow:hidden;box-shadow:0 12px 50px #21446620}.head{padding:34px 44px;background:#134d73;color:white}.brand{letter-spacing:3px;font-size:15px;opacity:.8}h1{font-size:30px;line-height:1.25;margin:16px 0}main{padding:34px 44px}.tag{color:#865114;background:#fff4df;border:1px solid #ebd4a8;padding:12px 18px;border-radius:8px;font-size:16px}.patient{display:flex;justify-content:space-between;border-bottom:2px solid #dce8f0;margin:24px 0;padding-bottom:20px}.date{font-size:24px;color:#134d73}table{border-collapse:collapse;width:100%;margin:24px 0}td{padding:20px 0;border-bottom:1px solid #e1e9ef;vertical-align:top}td:first-child{width:28%;font-weight:bold;color:#134d73;padding-right:24px}.note{margin-top:30px;border-left:4px solid #3b9da5;padding:18px 24px;background:#f0f9f9}.footer{padding:24px 44px;color:#6d7e8d;font-size:14px;border-top:1px solid #e1e9ef}</style><div class="paper"><header class="head"><div class="brand">DOCERE / УЧЕБНАЯ КЛИНИКА</div><h1>${doc.section}</h1><div>Медицинская история · материалы для совместного разбора</div></header><main><div class="tag">СИНТЕТИЧЕСКИЙ ДОКУМЕНТ — не медицинское заключение</div><div class="patient"><div><b>Демонстрационная Анна Сергеевна</b><br>Дата рождения: 12.03.1987</div><div class="date">${doc.date.split('-').reverse().join('.')}</div></div><h2>${doc.title}</h2><table>${doc.rows.map(([label, value]) => `<tr><td>${label}</td><td>${value}</td></tr>`).join('')}</table><div class="note">${doc.summary}</div></main><footer class="footer">Все имена, сведения и организации вымышлены. Ручная подготовка для демонстрации продукта, без AI.</footer></div></html>`
}

await mkdir(dirname(output), { recursive: true })
await mkdir(output)
const adminToken = await login(adminEmail, adminPassword)
const admin = await call('/auth/me', adminToken)
const accounts = []
for (const [name, preferredSpecialty, key] of [['Соколова Мария Андреевна', 'Терапия', 'coordinator'], ['Орлов Павел Игоревич', 'Кардиология', 'colleague'], ['Демонстрационный Новый Врач', 'Терапия', 'empty']]) {
  const email = `product-${key}-${run}@example.com`
  await call('/auth/register', null, { fio: name, email, phone: '+79990000001', password })
  let token = await login(email)
  const specialties = await call('/doctor-role-applications/specialties', token)
  const specialty = specialties.includes(preferredSpecialty) ? preferredSpecialty : specialties[0]
  const application = await call('/doctor-role-applications', token, { specialty, reviewer_user_ids: [admin.id] })
  await call(`/doctor-role-applications/${application.id}/review`, adminToken, { decision: 'approved', note: 'Синтетический аккаунт для демонстрации продукта' })
  token = await login(email)
  accounts.push({ key, email, password, user: await call('/auth/me', token), token })
}
const [coordinator, colleague] = accounts
console.log(`Врачи созданы: ${coordinator.email} / ${password}; ${colleague.email} / ${password}`)
const patient = await call('/patients', coordinator.token, { fio: 'Демонстрационная Анна Сергеевна', date_of_birth: '1987-03-12', email: `product-patient-${run}@example.com`, phone: '+79990000002' })
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 900, height: 1200 }, deviceScaleFactor: 1 })
  for (const doc of documents) {
    doc.file = resolve(output, `${doc.date}-${doc.name}.png`)
    await writeFile(resolve(output, `${doc.name}.html`), html(doc))
    await page.setContent(html(doc))
    await page.screenshot({ path: doc.file, fullPage: true })
  }
} finally { await browser.close() }

async function upload() {
  const form = new FormData()
  form.set('ai_requested', 'false')
  for (const doc of documents) form.append('files', new Blob([await readFile(doc.file)], { type: 'image/png' }), `${doc.date}-${doc.name}.png`)
  let job = await call('/archives/imports', coordinator.token, form)
  for (let attempts = 0; attempts < 90; attempts += 1) {
    job = await call(`/archives/imports/${job.id}`, coordinator.token)
    if (job.status === 'needs_review') return job
    if (['failed', 'completed'].includes(job.status)) throw new Error(`Unexpected import state: ${job.status}`)
    await new Promise(resolveSleep => setTimeout(resolveSleep, 1000))
  }
  throw new Error('Import did not reach manual review in 90s')
}
const imported = await upload()
const decisions = imported.report_json.patients.map(candidate => ({
  candidate_id: candidate.candidate_id, action: 'existing', patient_passport_id: patient.id,
  record_groups: candidate.record_groups.map(group => {
    const doc = documents.find(item => group.files.some(file => file.filename.includes(item.name)))
    if (!doc) throw new Error(`Cannot map group ${group.group_id}`)
    return { group_id: group.group_id, action: 'create', record_type: doc.type, event_date: doc.date, title: doc.title, clinical_summary: doc.summary, patient_identity_confirmed: true }
  }),
}))
const resolved = await call(`/archives/imports/${imported.id}/resolve`, coordinator.token, { version: imported.version, decisions })
if (resolved.status !== 'completed' || resolved.report_json.ai_requested) throw new Error('Manual import did not complete without AI')
const records = resolved.report_json.resolved_patients.flatMap(candidate => candidate.record_ids)
if (records.length !== 3) throw new Error(`Expected 3 records, received ${records.length}`)
const review = await upload()
const monitoring = (await call(`/patients/${patient.id}/records`, coordinator.token)).find(item => item.title === documents[2].title)
async function createCase(title) {
  return call('/cases', coordinator.token, { patient_id: patient.id, title, question, record_ids: records })
}
async function invite(view) {
  await call(`/cases/${view.id}/invitations`, coordinator.token, { version: view.case.version, user_id: colleague.user.id })
  return call(`/cases/${view.id}/invitations/accept`, colleague.token, {})
}
const draft = await createCase('Новый разбор · сопоставление жалоб и исследований')
const active = await invite(await createCase('Нужен ответ · дневник и мониторирование'))
const opinion = await call(`/cases/${active.id}/opinions`, coordinator.token, { assignee_id: colleague.user.id, question: opinionText, record_id: monitoring.id })
await call(`/cases/${active.id}/messages`, coordinator.token, { body: 'Синтетический контекст: собрала три документа и выделила неясную отметку дневника. Прошу мнение по материалу мониторирования.', record_id: monitoring.id, idempotency_key: randomUUID() })
const complete = await invite(await createCase('Завершённый разбор · история, мнение и итог'))
const completeOpinion = await call(`/cases/${complete.id}/opinions`, coordinator.token, { assignee_id: colleague.user.id, question: opinionText, record_id: monitoring.id })
await call(`/cases/${complete.id}/messages`, colleague.token, { body: replyText, opinion_id: completeOpinion.id, record_id: monitoring.id, idempotency_key: randomUUID() })
const current = await call(`/cases/${complete.id}`, coordinator.token)
await call(`/cases/${complete.id}/conclusions`, coordinator.token, { version: current.case.version, summary, findings: 'Исходная ЭКГ и дневник относятся к разным условиям. Неясная отметка времени явно указана как пробел данных.', next_actions: 'Учебное действие: запросить уточнение у автора документа; после получения оформить новую версию.', source_ids: records })
const preview = await call(`/cases/${complete.id}/closure-preview`, coordinator.token)
await call(`/cases/${complete.id}/close`, coordinator.token, { version: preview.version, cancel_open_requests: false })
const publication = await call(`/cases/${complete.id}/publish`, coordinator.token, { event_date: '2026-10-01' })
const state = {
  run, api, web, synthetic: true, ai_requested: false,
  accounts: accounts.map(({ token, ...account }) => account), patient, records,
  imports: { completed: imported.id, review: review.id },
  cases: { draft: draft.id, active: active.id, complete: complete.id }, opinion: opinion.id,
  published_record: publication.record_id, documents: documents.map(({ file, ...doc }) => ({ ...doc, file })),
  texts: { question, opinion: opinionText, reply: replyText, summary },
}
const statePath = resolve(output, 'state.json')
await writeFile(statePath, JSON.stringify(state, null, 2), { mode: 0o600 })
await writeFile(resolve(output, 'OPEN-ME.md'), `# Docere: синтетическая демонстрация\n\nВход: ${web}/auth/login\n\nКоординатор: ${coordinator.email} / ${password}\n\nКоллега: ${colleague.email} / ${password}\n\nИстория: ${web}/patients/${patient.id}\n\nРучная проверка импорта: ${web}/upload/review/${review.id}\n\nАктивный вопрос: ${web}/cases/${active.id}\n\nГотовый итог: ${web}/cases/${complete.id}\n\nПодготовка не запускала AI. Доступность анализа зависит от настроек стенда. Данные и клинические тексты вымышлены. Результаты AI или исследований спроса не имитируются.\n`)
console.log(`Готово. PRODUCT_DEMO_STATE=${statePath}\nИнструкция: ${resolve(output, 'OPEN-ME.md')}\nИстория: ${web}/patients/${patient.id}\nАктивный разбор: ${web}/cases/${active.id}\nГотовый итог: ${web}/cases/${complete.id}`)

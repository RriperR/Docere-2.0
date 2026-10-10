interface Breadcrumb { label: string; path: string }

/** Нейтральные подписи маршрутов: URL и идентификаторы не становятся названиями. */
export function getBreadcrumbs(pathname: string): Breadcrumb[] {
  const home = { label: 'Рабочий стол', path: '/dashboard' }
  const [, section, detail, resource] = pathname.split('/')
  if (!section || section === 'dashboard') return [home]
  const labels: Record<string, string> = {
    patients: 'Пациенты', cases: 'Клинические случаи', notifications: 'Входящие',
    'share-requests': 'Доступ к записям', 'doctor-role-request': 'Заявка на роль врача',
    'doctor-role-reviews': 'Проверка заявок врачей', upload: 'Импорт архива',
    admin: 'Управление системой', settings: 'Настройки аккаунта',
  }
  const crumbs = [home, { label: labels[section] ?? 'Страница', path: `/${section}` }]
  if (detail) {
    const label = section === 'cases' ? (detail === 'new' ? 'Новый случай' : 'Совместный разбор') :
      section === 'patients' ? 'Карточка пациента' :
      section === 'upload' ? (detail === 'review' ? 'Проверка материалов' : 'Статус импорта') : 'Подробности'
    crumbs.push({ label, path: `/${section}/${detail}${resource ? `/${resource}` : ''}` })
  }
  return crumbs
}

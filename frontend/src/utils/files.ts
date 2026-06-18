// Должно быть согласовано с MAX_ATTACHMENT_SIZE_MB на бэкенде
// (src/app/presentation/rest/public/v1/records/router.py) и client_max_body_size в nginx.
export const MAX_ATTACHMENT_SIZE_MB = 25
export const MAX_ATTACHMENT_SIZE_BYTES = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024

/** Вернуть текст ошибки, если файл превышает лимит размера, иначе null. */
export const attachmentSizeError = (file: File): string | null =>
  file.size > MAX_ATTACHMENT_SIZE_BYTES ? `Файл «${file.name}» больше ${MAX_ATTACHMENT_SIZE_MB} МБ` : null

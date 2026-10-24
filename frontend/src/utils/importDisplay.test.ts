import { expect, it } from 'vitest'
import { importTaskContext, importTitle } from './importDisplay'

it('describes internal uploads by document count and preserves an original archive name', () => {
  expect(importTitle({ original_filename: 'documents.zip', report_json: { files_total: 3 } })).toBe('Загруженные документы · файлов: 3')
  expect(importTitle({ original_filename: 'Исследования.zip', report_json: { files_total: 3 } })).toBe('Исследования.zip')
  expect(importTaskContext('documents.zip')).toBe('Загруженные документы')
  expect(importTaskContext('Снимок.png')).toBe('Снимок.png')
})

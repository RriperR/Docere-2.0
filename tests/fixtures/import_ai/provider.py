"""Изолированный HTTP-провайдер только для синтетического E2E-стенда.

Запуск: DOCERE_AI_DEMO=1 python provider.py. Не является fallback реальной модели.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer


class SyntheticProvider(BaseHTTPRequestHandler):
    """Вернуть известные факты тестовых PDF/PNG в совместимом wire format."""

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        """Прочитать тестовый запрос без логирования медицинского содержимого."""
        if self.path != '/v1/chat/completions':
            self.send_error(404)
            return
        length = int(self.headers.get('Content-Length', '0'))
        if length > 20 * 1024 * 1024:
            self.send_error(413)
            return
        payload = json.loads(self.rfile.read(length))
        parts = payload['messages'][1]['content']
        text = next(p['text'] for p in parts if p['type'] == 'text')
        page = int(re.search(r'Страница (\d+)', text).group(1))
        fields = {}
        values = {
            'fio': ('Synthetic Patient', 'Synthetic Patient'),
            'date_of_birth': ('1980-01-01', 'Birth date: 01.01.1980'),
            'event_date': ('2026-10-11', 'Event date: 11.10.2026'),
            'record_type': ('exam_result', 'Synthetic examination'),
            'title': ('Тестовое обследование', 'Synthetic examination'),
            'clinical_summary': (
                'Документ содержит синтетический результат обследования.',
                'Synthetic examination completed.',
            ),
        }
        for name, (value, excerpt) in values.items():
            fields[name] = {'value': value, 'sources': [{'page': page, 'excerpt': excerpt}]}
        result = {'fields': fields, 'issues': [], 'multiple_patients': False}
        body = json.dumps(
            {
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(result)}}],
                'usage': {'total_tokens': 100},
            }
        ).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Не сохранять запросы тестового провайдера в журнал."""


if __name__ == '__main__':
    if os.environ.get('DOCERE_AI_DEMO') != '1':
        raise SystemExit('Only the isolated synthetic E2E environment may start this provider')
    HTTPServer(('0.0.0.0', 9009), SyntheticProvider).serve_forever()  # noqa: S104 - isolated Docker network

"""Единые входящие отражают актуальные задачи, а не выдают медицинские права."""

from uuid import UUID

import pytest
from sqlalchemy import delete, select
from test_clinical_cases import invite, setup_case

from app.domain.entities.import_job import ImportJobStatus
from app.infrastructure.db.models.clinical_cases import CaseMemberRow
from app.infrastructure.db.models.medical_records.import_job import ImportJobRow
from app.infrastructure.db.models.medical_records.user_record_link import UserRecordLinkRow
from app.infrastructure.db.session import get_session_factory

pytestmark = pytest.mark.critical


def test_inbox_combines_four_tasks_and_reading_does_not_complete_them(record_client):
    """Приглашение, мнение, независимый sharing и импорт объединяются без дублей."""
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    tasks = client.get('/api/inbox/tasks', headers=headers[1])
    assert tasks.status_code == 200, tasks.text
    assert tasks.json()['total'] == 1
    assert tasks.json()['items'][0]['kind'] == 'invitation'
    assert 'Secret' not in tasks.text
    assert client.get('/api/inbox/tasks', headers=headers[2]).json()['total'] == 0
    client.post('/api/notifications/read-all', headers=headers[1])
    assert client.get('/api/inbox/tasks', headers=headers[1]).json()['total'] == 1
    base = f'/api/cases/{case["id"]}'
    assert client.post(base + '/invitations/accept', headers=headers[1]).status_code == 200
    opinion = client.post(
        base + '/opinions', headers=headers[0], json={'assignee_id': str(ids[1]), 'question': 'Мнение?'}
    )
    assert opinion.status_code == 201, opinion.text
    share = client.post(
        '/api/share-requests',
        headers=headers[0],
        json={'to_user_email': 'peer@cases.example.com', 'record_ids': [records[1]['id']]},
    )
    assert share.status_code == 201, share.text
    with get_session_factory()() as session:
        session.add(
            ImportJobRow(
                uploaded_by_user_id=ids[1], status=ImportJobStatus.NEEDS_REVIEW, original_filename='case-archive.zip'
            )
        )
        session.commit()
    tasks = client.get('/api/inbox/tasks', headers=headers[1]).json()
    assert tasks['total'] == 3
    assert {item['kind'] for item in tasks['items']} == {'opinion_requested', 'share_request', 'import_review'}
    assert next(item for item in tasks['items'] if item['kind'] == 'import_review')['context'] == 'case-archive.zip'
    counts = client.get('/api/inbox/counts', headers=headers[1])
    assert counts.status_code == 200, counts.text
    assert counts.json()['tasks'] == 3
    pages = [
        client.get('/api/inbox/tasks', headers=headers[1], params={'offset': offset, 'limit': 1}).json()['items'][0][
            'key'
        ]
        for offset in range(3)
    ]
    assert len(set(pages)) == 3
    target = base + '/opinions/' + opinion.json()['id']
    assert client.get(target, headers=headers[1]).status_code == 200
    assert client.get(target, headers=headers[2]).status_code == 404
    assert client.get('/api/inbox/tasks?kind=import_review', headers=headers[1]).json()['total'] == 1
    assert client.post(base + '/leave', headers=headers[1]).status_code == 200
    assert client.get('/api/inbox/counts', headers=headers[1]).json()['tasks'] == 2
    assert client.get('/api/inbox/tasks?kind=opinion_requested', headers=headers[1]).json()['total'] == 0


def test_inbox_hides_context_after_material_access_loss(record_client):
    """Проверка всех материалов выполняется до подсчёта и пагинации задач."""
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    case = invite(client, case, headers, ids[1])
    base = f'/api/cases/{case["id"]}'
    client.post(base + '/invitations/accept', headers=headers[1])
    client.post(
        base + '/opinions', headers=headers[0], json={'assignee_id': str(ids[1]), 'question': 'Private question'}
    )
    with get_session_factory()() as session:
        session.execute(
            delete(UserRecordLinkRow).where(
                UserRecordLinkRow.user_id == ids[1], UserRecordLinkRow.record_id == UUID(records[0]['id'])
            )
        )
        assert session.scalar(select(CaseMemberRow).where(CaseMemberRow.user_id == ids[1])).status == 'accepted'
        session.commit()
    result = client.get('/api/inbox/tasks', headers=headers[1])
    assert result.json()['total'] == 0
    assert 'Private' not in result.text
    assert client.get('/api/inbox/counts', headers=headers[1]).json()['tasks'] == 0


def test_conclusion_sources_and_opinion_links_require_full_context(record_client):
    """Названия источников выдаются после ACL и прямые ссылки не обходят членство."""
    client = record_client
    case, records, ids, headers, _ = setup_case(client)
    base = f'/api/cases/{case["id"]}'
    saved = client.post(
        base + '/conclusions',
        headers=headers[0],
        json={'version': case['case']['version'], 'summary': 'Итог', 'source_ids': [records[0]['id']]},
    )
    assert saved.status_code == 201, saved.text
    versions = client.get(base + '/conclusions', headers=headers[0]).json()
    assert versions['items'][0]['sources'][0]['title'] == records[0]['title']
    assert client.get(base + '/conclusions', headers=headers[2]).status_code == 404


def test_inbox_union_works_on_postgresql(postgres_case_client):
    """SQL UNION и фильтры UUID выполняются на PostgreSQL в изолированной схеме."""
    test_inbox_combines_four_tasks_and_reading_does_not_complete_them(postgres_case_client)

"""Пакет сценария комментариев к медицинской записи."""

from app.application.use_cases.medical_records.add_record_comment.dtos import AddRecordCommentDTO
from app.application.use_cases.medical_records.add_record_comment.use_case import AddRecordCommentUseCase

__all__ = ['AddRecordCommentDTO', 'AddRecordCommentUseCase']

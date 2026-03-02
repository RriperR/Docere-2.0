from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.dto.auth_token import AuthToken
from app.application.dto.auth_user_view import AuthUserView
from app.application.use_cases.auth_errors import (
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    InvalidTokenError,
    UserNotFoundError,
)
from app.application.use_cases.get_authenticated_user import GetAuthenticatedUser
from app.application.use_cases.login_user import LoginUser
from app.application.use_cases.register_patient_user import RegisterPatientUser
from app.presentation.rest.auth.dependencies import (
    extract_bearer_token,
    get_authenticated_user_use_case,
    get_login_user,
    get_register_patient_user,
)
from app.presentation.rest.auth.schemas import (
    AuthTokenResponseSchema,
    AuthUserResponseSchema,
    LoginRequestSchema,
    RegisterPatientRequestSchema,
)
from app.presentation.webserver.http_errors import (
    raise_email_already_exists,
    raise_invalid_credentials,
    raise_unauthorized,
)

router = APIRouter(prefix='/auth', tags=['auth'])
register_patient_dependency = Depends(get_register_patient_user)
login_user_dependency = Depends(get_login_user)
authenticated_user_use_case_dependency = Depends(get_authenticated_user_use_case)
bearer_token_extraction_dependency = Depends(extract_bearer_token)


@router.post(
    '/register',
    response_model=AuthUserResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
def register_patient(
    payload: RegisterPatientRequestSchema,
    use_case: RegisterPatientUser = register_patient_dependency,
) -> AuthUserView:
    try:
        return use_case.execute(
            fio=payload.fio,
            email=str(payload.email).lower(),
            phone=payload.phone,
            password=payload.password,
            date_of_birth=payload.date_of_birth,
        )
    except EmailAlreadyExistsError:
        raise_email_already_exists()


@router.post('/login', response_model=AuthTokenResponseSchema)
def login(
    payload: LoginRequestSchema,
    use_case: LoginUser = login_user_dependency,
) -> AuthToken:
    try:
        return use_case.execute(email=str(payload.email).lower(), password=payload.password)
    except InvalidCredentialsError:
        raise_invalid_credentials()


@router.get('/me', response_model=AuthUserResponseSchema)
def get_authenticated_user(
    token: str = bearer_token_extraction_dependency,
    use_case: GetAuthenticatedUser = authenticated_user_use_case_dependency,
) -> AuthUserView:
    try:
        return use_case.execute(token=token)
    except (InvalidTokenError, UserNotFoundError):
        raise_unauthorized('Invalid or expired token')

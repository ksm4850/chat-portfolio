from src.core.exceptions import AppError


class PortfolioNotIngestedError(AppError):
    status_code = 404
    code = "portfolio_not_ingested"
    message = "포트폴리오 콘텐츠가 아직 수집되지 않았다."


class ProjectNotFoundError(AppError):
    status_code = 404
    code = "project_not_found"
    message = "프로젝트를 찾을 수 없다."


class InvalidPortfolioSourceError(AppError):
    status_code = 422
    code = "invalid_portfolio_source"
    message = "포트폴리오 원본이 올바르지 않다."


class SourceFileNotFoundError(AppError):
    status_code = 404
    code = "source_file_not_found"
    message = "projects.json 에 등록된 원본 md 가 아니다."


class MediaNotFoundError(AppError):
    status_code = 404
    code = "media_not_found"
    message = "이미지·동영상을 찾을 수 없다."

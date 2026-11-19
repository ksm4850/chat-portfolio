from src.core.exceptions import AppError


class DocumentNotFoundError(AppError):
    status_code = 404
    code = "document_not_found"
    message = "문서를 찾을 수 없다."


class EmptyDocumentError(AppError):
    status_code = 422
    code = "empty_document"
    message = "문서에 적재할 내용이 없다."


class EmbeddingFailedError(AppError):
    status_code = 502
    code = "embedding_failed"
    message = "임베딩을 만들지 못했다."


class ImportedDocumentError(AppError):
    status_code = 409
    code = "imported_document"
    message = "포트폴리오 문서는 원본 md 를 고쳐 다시 수집한다."

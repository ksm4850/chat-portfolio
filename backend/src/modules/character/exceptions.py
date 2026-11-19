from src.core.exceptions import AppError


class CharacterNotFoundError(AppError):
    status_code = 404
    code = "character_not_found"
    message = "캐릭터를 찾을 수 없다."


class CharacterSlugAlreadyExistsError(AppError):
    status_code = 409
    code = "character_slug_already_exists"
    message = "이미 쓰고 있는 slug 다."

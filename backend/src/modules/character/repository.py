from src.infrastructure.database import BaseRepository
from src.modules.character.models import Character


class CharacterRepository(BaseRepository[Character]):
    model = Character

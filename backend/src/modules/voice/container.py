from dependency_injector import containers, providers

from src.infrastructure.speech import SpeechToText
from src.modules.voice.service import VoiceService


class VoiceContainer(containers.DeclarativeContainer):
    stt = providers.Dependency(instance_of=SpeechToText)

    service = providers.Factory(VoiceService, stt=stt)

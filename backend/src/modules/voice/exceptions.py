from src.core.exceptions import AppError


class SpeechNotConfiguredError(AppError):
    status_code = 503
    code = "speech_not_configured"
    message = "STT 설정이 없다. .env 에 DEEPGRAM_API_KEY 를 넣는다."


class SpeechRecognitionFailedError(AppError):
    status_code = 502
    code = "speech_recognition_failed"
    message = "음성을 인식하지 못했다."

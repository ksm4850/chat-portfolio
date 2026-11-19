/** 원본(md·projects.json)의 `medias/...` 경로를 백엔드가 서빙하는 주소로 바꾼다. */
export const MEDIA_URL = '/api/v1/portfolio/medias/'

export const toMediaUrl = (src?: string) => (src && src.startsWith('medias/') ? MEDIA_URL + src.slice(7) : src)

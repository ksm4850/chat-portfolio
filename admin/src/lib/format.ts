const dateTime = new Intl.DateTimeFormat('ko-KR', { dateStyle: 'short', timeStyle: 'short' })

export const formatDateTime = (value: string) => dateTime.format(new Date(value))

export const PORTFOLIO_PREFIX = 'portfolio:'

export const isPortfolioSource = (source: string) => source.startsWith(PORTFOLIO_PREFIX)

export const portfolioFile = (source: string) => source.slice(PORTFOLIO_PREFIX.length)

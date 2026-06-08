# 소스 구독 정리 포스트모템

**날짜**: 2026-06-05  
**작업자**: 표효성  
**관련 커밋**: `969af83`, `570d0d3`, `4204309`, `16312ac`

---

## 개요

Horizon 수집 소스의 비용 대비 효율을 분석해 저품질·비작동 구독을 일괄 정리했다.  
분석 기준: 최근 7일 fetch 캐시(`data/cache/fetch/`) + 전체 기간 items 캐시(`data/cache/items/`)의 통과율(ai_score ≥ 3.0) 및 평균 점수.

---

## 제거 내역

### 이전 세션 제거 (커밋 `969af83`, `570d0d3`)

| 소스 | 종류 | 제거 시점 | 사유 |
|------|------|-----------|------|
| Techmeme | RSS | 2026-06-04 | 저품질 집계 사이트, 중복 뉴스 多 |
| BBC News | RSS | 2026-06-04 | 통과율 8%, 기술 뉴스 소스 아님 |
| Lobsters | RSS | 2026-06-04 | HN과 중복 커버리지, 독립 가치 낮음 |
| Hacker News (RSS) | RSS | 2026-06-04 | 직접 scraper(`hackernews`)와 중복 |

### 이번 세션 제거 (커밋 `4204309`, `16312ac`)

| 소스 | 종류 | 총수 | 통과율 | 평균점 | 제거 사유 |
|------|------|------|--------|--------|-----------|
| **BBC News** | RSS | 412 | 8% | 1.0 | 이미 이전 세션에서 제거됨 |
| **GitHub Trending Daily** | RSS | 0 | — | — | fetch 기록 없음 (비활성 피드) |
| **요즘IT** | RSS | 0 | — | — | fetch 기록 없음 (비활성 피드) |
| **GONOGO_Korea** | Twitter | 163 | 10% | 1.0 | 한국 주식·경제 위주, 기술 관련성 없음 |
| **babybluecream** | Twitter | 186 | 13% | 1.3 | 이미지 트윗·노이즈 비율 87% |
| **Kurzgesagt** | YouTube | 2 | 0% | 0.8 | 과학 교육 콘텐츠, Horizon 독자 관련성 낮음 |
| **The Diary Of A CEO** | YouTube | 7 | 14% | 1.6 | 인터뷰 중심, 기술 콘텐츠 희박 |
| **r/ArtificialInteligence** | Reddit | 87 | 68% | 3.9 | 6월 fetch 0건, 철자 오류 비공식 커뮤니티 |
| **r/gamedev** | Reddit | 58 | 41% | 2.6 | ≥7점 아이템 0개, 인디게임 독자층 미대상 |
| **r/programming** | Reddit | 72 | 92% | 5.6 | Reddit 인프라 이슈로 함께 제거 (아래 참조) |
| **r/ClaudeCode** | Reddit | 116 | 63% | 3.6 | Reddit 인프라 이슈로 함께 제거 (아래 참조) |

---

## Reddit 제거 상세 — 인프라 이슈

r/programming은 품질 지표(평균 5.6점, ≥7점 22개)가 우수했으나 기술적 한계로 제거.

### 근본 원인

Reddit은 2023년 API 정책 변경으로 **비인증 JSON API 전면 차단(HTTP 403)**.  
Horizon은 무인증 fallback으로 **Arctic Shift**(`arctic-shift.photon-reddit.com`)를 사용하나, Arctic Shift의 구조적 한계가 존재한다.

```
포스트 생성 → Arctic Shift 인덱싱(수십 분 이내, score 캡처) → Horizon fetch
                        ↑
                score = 1  (투표 누적 전)
```

Arctic Shift는 포스트 생성 직후 인덱싱하므로 24h 윈도우 내 모든 포스트의 score = 1.  
`min_score = 10` 필터가 전부 탈락시켜 2026-06-01 이후 일 0~2개로 급감.

### 검토한 대안

| 방법 | 결과 |
|------|------|
| Arctic Shift `sort=score` 파라미터 | 미지원 — 빈 배열 반환 |
| Reddit `/top.json?t=day` (비인증) | HTTP 403 |
| Pushshift.io | HTTP 307 redirect — 유료화 후 서비스 종료 |
| `min_score: 1`로 완화 | 기술적으로 동작하나 최신순 무작위 25개, 인기도 보장 없음 |

### 재활성화 조건

Reddit OAuth 앱 등록(무료) 후 `data/config.json`에 아래 필드 추가:

```json
"reddit": {
  "enabled": true,
  "client_id": "<Reddit App client_id>",
  "client_secret": "<Reddit App client_secret>",
  "user_agent": "Horizon/1.0 by mizelan",
  "backend": "reddit_oauth",
  "subreddits": [
    { "subreddit": "programming", "enabled": true, "sort": "hot", "fetch_limit": 25, "min_score": 10 },
    { "subreddit": "ClaudeCode",  "enabled": true, "sort": "hot", "fetch_limit": 25, "min_score": 10 }
  ]
}
```

앱 등록: https://www.reddit.com/prefs/apps → "script" 타입

---

## 정리 후 현황

### 유지된 소스

| 소스 | 종류 | 통과율 | 평균점 |
|------|------|--------|--------|
| GeekNews | RSS | 87% | 5.1 |
| Dev.to Top Weekly | RSS | 76% | 4.4 |
| OpenAI News | RSS | 80% | 4.8 |
| OpenAI Developers Blog | RSS | — | — |
| Hacker News | Scraper | 96% | 5.9 |
| Claude Blog | Site | 100% | 7.1 |
| Anthropic Engineering Blog | Site | 100% | 7.5 |
| Tildes | Site | 22% | 1.8 |
| Krongggggg | Twitter | 82% | 4.6 |
| GergelyOrosz | Twitter | 69% | 3.8 |
| garrytan | Twitter | 37% | 2.4 |
| steipete | Twitter | 63% | 3.6 |
| ylecun | Twitter | 33% | 2.1 |
| elonmusk | Twitter | 26% | 1.8 |
| karpathy | Twitter | 50% | 3.8 |
| bcherny | Twitter | 67% | 4.0 |
| chester_roh | Twitter | 38% | 3.1 |
| Chester Roh | YouTube | 100% | 5.8 |
| Y Combinator | YouTube | 83% | 5.2 |
| All-In Podcast | YouTube | 43% | 3.0 |
| ScienceADAM | YouTube | 100% | 4.5 |
| Sequoia Capital | YouTube | 100% | 4.8 |
| The Economist | YouTube | 38% | 3.1 |
| karpathy (GitHub) | GitHub | — | — |

### 예상 절감 효과

- 일일 fetch 아이템 수: ~700개 → ~450개 (약 35% 감소)
- Analysis 배치 수: 19~22 → 약 12~14 (동일 비율 감소)
- 주요 절감원: BBC News(~60개/일), GONOGO_Korea+babybluecream(~50개/일), Reddit(~50개/일)

---

## 교훈

1. **통과율을 주기적으로 측정해야 한다.** fetch 수가 많아도 AI 점수 통과율이 낮으면 비용 낭비다.
2. **외부 API 의존 소스는 접근 방식을 명시해야 한다.** Reddit은 공식 API 정책 변경으로 조용히 작동 중단됐다. `optional: true`로 표시했지만 degradation이 수치로 드러나지 않았다.
3. **fetch 기록이 없는 구독은 즉시 제거한다.** GitHub Trending Daily, 요즘IT는 설정만 있고 실제로 한 번도 데이터를 가져오지 않았다.

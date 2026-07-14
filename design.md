# 디자인 가이드 (design.md)
컨셉: 무채색 베이스 + 골드(풍산) 포인트, 당근마켓·배민 느낌의 둥글고 친근한 UI

## 원칙
- 배경은 흰색/연회색 유지, 골드는 버튼·밑줄·뱃지 등 포인트에만 사용 (컬러 블록 채우지 않기)
- 버튼·카드는 각지지 않게 둥글게(rounded), 터치하기 편한 큰 사이즈
- 그림자는 은은하게, 여백은 넉넉하게
- 문구는 부드러운 대화체 존댓말 유지

## 컬러 (CSS 변수)
```css
:root {
  --color-bg: #F7F7F8;
  --color-surface: #FFFFFF;
  --color-surface-muted: #F2F2F3;   /* 잠긴 입력창 배경 */
  --color-border: #E5E5E7;
  --color-text-primary: #1C1C1E;
  --color-text-secondary: #6E6E73;
  --color-text-placeholder: #A0A0A5;

  --color-accent: #C9A227;          /* 풍산 골드 - 정확한 헥스코드 확정시 교체 */
  --color-accent-hover: #B8911E;
  --color-accent-light: #F5EBD1;    /* 선택된 카드/뱃지 배경 */

  --shadow-sm: 0 1px 3px rgba(0,0,0,0.04);
  --shadow-button: 0 2px 8px rgba(201,162,39,0.25);

  --radius-md: 14px;
  --radius-pill: 999px;             /* 버튼용 */
  --font-family: 'Pretendard', -apple-system, sans-serif;
}
```
> 폰트: Pretendard (무료, 토스·당근마켓류가 쓰는 굵고 모던한 한글 웹폰트)

## 헤더 / 탭
- 진한 색 블록 대신 흰 배경 + 하단 얇은 보더로 절제
- 탭 밑줄: 활성 단계는 골드 밑줄 + 굵은 텍스트, 완료 단계는 앞에 `✓` 골드 표시, 나머지는 연회색

## 입력 필드
- 높이 52px, `border-radius: var(--radius-md)`, 포커스 시 골드 테두리 + 옅은 골드 box-shadow 링
- 사번/성명처럼 검증 후 잠긴 필드는 `--color-surface-muted` 배경으로 명확히 구분

## 버튼
- 알약형(`border-radius: var(--radius-pill)`), 높이 52px, 굵은 텍스트
- Primary: 골드 배경 + 어두운 텍스트 + `--shadow-button`, 클릭 시 `transform: scale(0.97)`
- Secondary(이전 등): 흰 배경 + 회색 보더 + 어두운 텍스트

## 금융사 선택
- 단순 라디오 리스트 대신 2열 그리드의 **터치형 카드**로 구성
- 선택 시 골드 테두리 + `--color-accent-light` 배경 + 굵은 텍스트
- 교보생명(간사기관) 카드에는 우측 상단 작은 골드 뱃지 "간사기관" 표시

## 레이아웃
- 모바일 우선, 콘텐츠 최대너비 480px, 좌우 여백 16~20px
- 하단 버튼 영역은 `position: sticky; bottom: 0;`으로 스크롤과 무관하게 고정

## 문구 톤
- 안내/에러 메시지도 나무라지 않고 부드럽게: "사번 또는 성명을 다시 확인해주세요"
- 제출 완료 화면은 친근하게: "제출이 완료됐어요!"

## Do / Don't
| Do | Don't |
|---|---|
| 골드는 버튼·밑줄·뱃지에만 포인트로 | 배경 전체를 골드/진한 컬러로 채우기 |
| 버튼은 알약형으로 둥글게 | 각진 사각 버튼 |
| 잠긴 필드는 무채색 배경으로 구분 | 잠긴 필드도 일반 입력창처럼 표시 |

## 적용 지침
- 위 `:root` 변수를 `styles.css` 최상단에 적용 후, 기존 컴포넌트 class에 반영
- `--color-accent` 값만 교체하면 전체 골드 톤이 자동 반영됨

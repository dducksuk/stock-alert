# stock-alert

미국 주식 조건 알림 봇. 조건에 맞으면 텔레그램으로 알려줍니다. GitHub Actions 에서 무료로 돌아갑니다.

## 1. 조건 알림 (RSI · 급락 등)
- 설정: `config.yaml`
- 실행: `.github/workflows/alert.yml` (정규장 동안 30분마다)

## 2. 목표가 알림 (매수/매도)
앱에서 종목별 매수 목표가·매도 목표가를 넣어두면, 가격이 닿았을 때 텔레그램으로 알려줍니다.

- 🔴 **매수 시점**: 현재가 ≤ 매수 목표가
- 🔵 **매도 시점**: 현재가 ≥ 매도 목표가
- 한 번 알린 뒤에는 가격이 반대쪽으로 1% 이상 벗어났다가 다시 닿아야 또 알립니다. 목표가를 바꾸면 처음부터 다시 감시합니다.
- 실행: `.github/workflows/targets.yml` (정규장 동안 5분마다. GitHub 사정으로 몇 분씩 늦어질 수 있음)

### 앱 (핸드폰)
주소: **https://dducksuk.github.io/stock-alert/**

1. 핸드폰에서 위 주소 열기
2. 홈 화면에 추가
   - 아이폰: Safari → 공유 버튼 → **홈 화면에 추가**
   - 안드로이드: Chrome → 오른쪽 위 ⋮ → **홈 화면에 추가** (또는 앱 설치)
3. 앱의 **설정**에서 GitHub 토큰 입력 (처음 한 번)
   - https://github.com/settings/personal-access-tokens/new
   - Repository access: Only select repositories → `stock-alert`
   - Permissions → Repository → **Contents: Read and write**
4. (선택) Finnhub API 키를 넣으면 앱에서 실시간 현재가와 전체 종목 검색이 됩니다. 없으면 봇이 마지막으로 확인한 가격을 보여줍니다.

토큰과 키는 핸드폰 브라우저에만 저장됩니다.

### 파일
| 파일 | 내용 |
|---|---|
| `price_targets.json` | 앱이 저장하는 목표가 |
| `target_state.json` | 알림 중복 방지 상태 (봇이 관리) |
| `prices.json` | 봇이 마지막으로 확인한 시세 (앱 표시용) |
| `app/` | 웹앱 (GitHub Pages 로 배포) |

목표가를 앱 없이 직접 넣으려면 `price_targets.json` 을 이렇게 고치면 됩니다.
```json
{ "NVDA": { "name": "엔비디아", "buy": 120, "sell": 150 } }
```

## 로컬 실행
```bash
pip install -r requirements.txt
python main.py --dry-run              # 조건 알림 미리보기
python main.py --targets --dry-run    # 목표가 알림 미리보기
python -m pytest -q                   # 테스트
```

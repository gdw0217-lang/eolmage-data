# eolmage-data

토스 미니앱 「얼마게」(생필품 가격 맞히기 퀴즈)가 읽는 상품·가격 파일을 만든다.

- 결과: `docs/products.json` → GitHub Pages 로 공개 (`https://<계정>.github.io/eolmage-data/products.json`)
- 갱신: GitHub Actions 가 매일 아침 공공데이터포털을 확인해, 새 달 파일이 올라왔을 때만 다시 만든다
- 데이터: 한국소비자원 생필품 가격 정보(참가격) — 공공데이터포털 파일데이터 15083256, 이용허락범위 제한 없음
- 대표 가격: 가장 최근 조사일의 정상가(세일·1+1 제외) 중간값, 판매처 15곳 이상 조사된 상품만

```sh
pip install -r requirements.txt
python scripts/update.py
```

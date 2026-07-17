# DB → DC 퇴직연금 제도전환 신청 웹페이지 - 설정 가이드

plan.md 기획에 따라 만든 신청자 페이지(index.html) / 관리자 페이지(admin.html) /
백엔드(app.py, Flask)입니다.

> **왜 Google Apps Script를 안 쓰나요?**
> 원래는 Google Apps Script + Google Sheets로 만들었는데, 일부 회사 사내망에서
> `script.google.com` 도메인 자체를 보안 정책으로 차단해서 신청자가 "Failed to fetch"
> 오류를 겪는 문제가 확인됐습니다. 그래서 백엔드를 Python(Flask)으로 옮기고, 데이터도
> Google Sheets 대신 서버 자체 DB에 저장하고 관리자 페이지에서 직접 관리하도록 했습니다.

> **왜 PythonAnywhere 대신 Render + Turso를 쓰나요?**
> PythonAnywhere 무료 계정은 계정당 웹사이트를 1개만 배포할 수 있어서, 앞으로 다른
> 프로젝트도 배포하려면 매번 새 계정을 만들어야 하는 문제가 있었습니다. 그래서 배포는
> **Render**(GitHub 저장소를 연결해두면 push할 때마다 자동 배포됨, 기존 GitHub Pages
> 방식과 비슷한 편의성)로 옮기고, 데이터는 **Turso**(SQLite와 거의 동일한 SQL을 쓰는
> 무료 클라우드 DB)에 저장합니다. Render 무료 서비스는 재배포/재시작마다 서버 안의
> 파일이 초기화될 수 있어서, DB 파일을 서버 안에 두는 대신 Turso에 분리해두면 배포를
> 아무리 자주 해도 신청 데이터가 사라지지 않습니다.

## 1. Turso 데이터베이스 만들기 (최초 1회)

1. [turso.tech](https://turso.tech) 무료 계정 생성
2. 대시보드에서 새 데이터베이스 생성 (이름은 자유롭게, 예: `dc-transfer`)
3. 데이터베이스 상세 페이지에서 **Database URL**(`libsql://...`)과 **Auth Token**을 발급받아 복사해둡니다.

## 2. 로컬에서 먼저 테스트하기

```powershell
# 프로젝트 폴더에서 (최초 1회만)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# .env.example을 복사해서 .env로 저장한 뒤, 1번에서 받은 값을 채워넣기
copy .env.example .env
notepad .env
```

`.env` 파일에 아래처럼 채워넣습니다.
```
TURSO_DATABASE_URL=libsql://실제-발급받은-주소.turso.io
TURSO_AUTH_TOKEN=실제-발급받은-토큰
```

```powershell
# 서버 실행
python app.py
```

`python app.py`를 실행하면 `http://127.0.0.1:5000` 에서 신청자 페이지가,
`http://127.0.0.1:5000/admin.html` 에서 관리자 페이지가 열립니다.
최초 실행 시 Turso DB에 테이블이 자동 생성되고, 관리자 비밀번호는
**`admin1234`** 로 초기화됩니다. (로그인 후 바로 변경하세요. 아래 4번 참고)

## 3. Render에 배포하기

1. [render.com](https://render.com) 무료 계정 생성 (GitHub 계정으로 로그인 가능)
2. 대시보드에서 **New > Web Service** 클릭 → 이 GitHub 저장소 연결
3. 설정값 입력
   - **Language/Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Instance Type**: Free
4. **Environment Variables** 항목에 아래 두 개를 추가 (1번에서 발급받은 값)
   - `TURSO_DATABASE_URL`
   - `TURSO_AUTH_TOKEN`
5. **Create Web Service** 클릭 → 첫 배포가 자동으로 시작됨 (2~3분 소요)
6. 배포된 `https://프로젝트명.onrender.com` 주소로 접속해서 신청자 페이지가 뜨는지 확인

> 이후에는 `git push`로 코드를 올리기만 하면 Render가 자동으로 재배포합니다.
> PythonAnywhere처럼 콘솔에 접속해서 `git pull` + 수동 `Reload`를 할 필요가 없습니다.

> **주의(무료 티어 콜드스타트)**: Render 무료 서비스는 15분간 요청이 없으면 자동으로
> 슬립 상태가 되고, 이후 첫 접속 시 최대 1분 정도 로딩이 걸릴 수 있습니다. 연 2회, 짧은
> 접수 기간에만 쓰는 이 앱 특성상 큰 문제는 아니지만, 접수 시작 공지에 "처음 접속 시
> 로딩이 걸릴 수 있어요" 정도로 안내하면 좋습니다.

> **주의(사내망 접속 확인 필수)**: `onrender.com` 도메인이 실제 회사 사내망에서
> 차단되지 않는지, 신청자에게 링크를 배포하기 전에 반드시 사내망에서 접속 테스트를
> 해보세요. (`script.google.com`이 막혔던 것과 같은 이유로 막힐 가능성은 낮지만, 배포
> 전 확인이 안전합니다)

## 4. 최초 배포 후 꼭 해야 할 것

1. `admin.html`(`.../admin.html`) 접속 → 기본 비밀번호 `admin1234`로 로그인
2. **설정 / 사번마스터 관리** 화면에서
   - **관리자 비밀번호 변경**: 새 비밀번호로 즉시 교체
   - **접수 설정**: 현재접수회차 입력 (예: `2026-08`)
   - **사번마스터 관리**: 기존 Google Sheets에서 관리하던 대상자 명단을
     `파일 > 다운로드 > CSV`로 내보낸 뒤, **헤더 행(첫 줄)은 지우고** 아래 형식으로
     붙여넣고 "일괄 등록/업데이트" 클릭
     ```
     사번,성명,부서,직급
     10001,홍길동,인사팀,과장
     10002,김철수,생산팀,대리
     ```
     (부서/직급은 비워도 되지만 사번·성명은 필수입니다. 같은 사번을 다시 넣으면 값이 덮어써집니다)

## 5. 접수 운영 (plan.md 5장 참고)

- **접수 시작 전**: 관리자 페이지에서 이번 회차 대상자 사번마스터 CSV 등록, 현재접수회차 값 업데이트
- **접수 진행 중**: 관리자 페이지 "신청 목록"에서 실시간 제출 현황 확인/검색/필터
- **접수 종료 후**: "사번마스터 관리 > 전체 삭제"를 누르면 이후 접근 시 검증 실패로
  자동 차단됩니다. 제출 목록은 삭제되지 않고 그대로 남습니다.
- 제출 데이터는 Turso 클라우드 DB에 저장되므로, Render를 재배포/재시작해도 데이터는
  그대로 유지됩니다. 백업이 필요하면 Turso 대시보드에서 DB를 내보낼 수 있습니다.

## 파일 구조

```
index.html          신청자 페이지
admin.html            관리자 페이지
css/styles.css         공통 스타일 (모바일 반응형)
js/config.js           API_URL 설정 (기본값 "/api", 보통 수정할 필요 없음)
js/api.js              백엔드 호출 공통 함수
js/app.js              신청자 페이지 로직
js/admin.js             관리자 페이지 로직
app.py                 Flask 백엔드 (API + 정적 파일 서빙)
db_client.py            Turso(libSQL) 연결 래퍼
requirements.txt        Python 패키지 목록
.env.example            로컬 개발용 환경변수 예시 (.env로 복사해서 사용, git에는 커밋 안 함)
```

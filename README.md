# DB → DC 퇴직연금 제도전환 신청 웹페이지 - 설정 가이드

plan.md 기획에 따라 만든 신청자 페이지(index.html) / 관리자 페이지(admin.html) /
백엔드(app.py, Flask)입니다.

> **왜 Google Apps Script를 안 쓰나요?**
> 원래는 Google Apps Script + Google Sheets로 만들었는데, 일부 회사 사내망에서
> `script.google.com` 도메인 자체를 보안 정책으로 차단해서 신청자가 "Failed to fetch"
> 오류를 겪는 문제가 확인됐습니다. 같은 사내망에서 `pythonanywhere.com`은 정상 동작하는
> 것을 확인해서, 백엔드를 Python(Flask) + PythonAnywhere로 옮겼습니다. 데이터도
> Google Sheets 대신 서버 자체 DB(SQLite, 파일 하나로 동작하는 가벼운 데이터베이스)에
> 저장하고, 관리자 페이지에서 직접 관리합니다.

## 1. 로컬에서 먼저 테스트하기

```powershell
# 프로젝트 폴더에서 (최초 1회만)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 서버 실행
python app.py
```

`python app.py`를 실행하면 `http://127.0.0.1:5000` 에서 신청자 페이지가,
`http://127.0.0.1:5000/admin.html` 에서 관리자 페이지가 열립니다.
최초 실행 시 `dc_transfer.db` 파일이 자동 생성되고, 관리자 비밀번호는
**`admin1234`** 로 초기화됩니다. (로그인 후 바로 변경하세요. 아래 3번 참고)

## 2. PythonAnywhere에 배포하기

1. [pythonanywhere.com](https://www.pythonanywhere.com) 무료(Beginner) 계정 생성
2. 상단 **Consoles > Bash** 콘솔을 열고 저장소를 내려받습니다.
   ```bash
   git clone https://github.com/won01288/dc-transfer-app.git
   cd dc-transfer-app
   pip install --user -r requirements.txt
   ```
   (GitHub에 아직 push하지 않았다면, **Files** 탭에서 파일을 직접 업로드해도 됩니다)
3. 상단 **Web** 탭 > **Add a new web app** > 도메인은 무료 제공 주소(`계정명.pythonanywhere.com`) 선택
   > **Framework**: "Manual configuration" 선택 (Flask 자동설정이 아니라 우리 코드를 직접 연결) → Python 버전은 3.10 이상 선택
4. **Web** 탭의 **Code** 섹션에서:
   - **Source code**: `/home/계정명/dc-transfer-app`
   - **WSGI configuration file** 링크 클릭 → 파일 내용을 아래처럼 수정
   ```python
   import sys
   path = '/home/계정명/dc-transfer-app'
   if path not in sys.path:
       sys.path.insert(0, path)

   from app import app as application
   ```
5. **Web** 탭 상단의 **Reload** 버튼 클릭
6. `https://계정명.pythonanywhere.com/` 접속해서 신청자 페이지가 뜨는지 확인

> Code.gs 때처럼 코드를 수정하면, PythonAnywhere Bash 콘솔에서 `git pull` 로 최신 코드를
> 받은 뒤 **Web** 탭에서 다시 **Reload** 를 눌러야 반영됩니다.

## 3. 최초 배포 후 꼭 해야 할 것

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

## 4. 접수 운영 (plan.md 5장 참고)

- **접수 시작 전**: 관리자 페이지에서 이번 회차 대상자 사번마스터 CSV 등록, 현재접수회차 값 업데이트
- **접수 진행 중**: 관리자 페이지 "신청 목록"에서 실시간 제출 현황 확인/검색/필터
- **접수 종료 후**: "사번마스터 관리 > 전체 삭제"를 누르면 이후 접근 시 검증 실패로
  자동 차단됩니다. 제출 목록은 삭제되지 않고 그대로 남습니다.
- 제출 데이터는 `dc_transfer.db` 파일(SQLite)에 저장됩니다. 개인정보가 담긴 파일이므로
  **git에 커밋되지 않도록 `.gitignore`에 이미 등록**해뒀고, 필요 시 PythonAnywhere
  **Files** 탭에서 이 파일을 다운로드해 백업할 수 있습니다.

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
requirements.txt        Python 패키지 목록
dc_transfer.db          SQLite DB 파일 (최초 실행 시 자동 생성, git에는 커밋 안 함)
```

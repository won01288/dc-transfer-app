# Turso(libSQL) 연결 래퍼.
# 처음에는 libsql 파이썬 패키지(Rust 네이티브 확장)를 썼는데, Render 무료 티어처럼
# 리소스가 빠듯한 컨테이너에서 내부 Tokio 스레드 런타임이 패닉을 일으켜 워커 프로세스가
# 죽는 문제가 반복됐다. 그래서 Rust 확장 없이, Turso의 HTTP API(Hrana pipeline)를
# 표준 `requests` 라이브러리로 직접 호출하는 방식으로 바꿨다. 매 호출이 순수 HTTP
# 요청/응답이라 네이티브 스레드 문제가 생길 여지가 없다.
# 참고: https://docs.turso.tech/sdk/http/reference
import os

import requests

_TIMEOUT_SECONDS = 10


class Row(dict):
    pass


def _to_arg(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    return {"type": "text", "value": str(value)}


def _from_cell(cell):
    cell_type = cell.get("type")
    if cell_type == "null":
        return None
    if cell_type == "integer":
        return int(cell["value"])
    if cell_type == "float":
        return float(cell["value"])
    return cell.get("value")


class _CursorWrapper:
    def __init__(self, result):
        self._result = result

    def _rows(self):
        # Turso는 key/round처럼 SQL 예약어(KEY, ROUND 함수 등)와 겹치는 컬럼명을
        # 대문자로 바꿔서 돌려주는 경우가 있어, 항상 소문자로 맞춰서 비교한다.
        cols = [c["name"].lower() for c in self._result.get("cols", [])]
        return [Row(zip(cols, (_from_cell(cell) for cell in row))) for row in self._result.get("rows", [])]

    def fetchone(self):
        rows = self._rows()
        return rows[0] if rows else None

    def fetchall(self):
        return self._rows()


class Connection:
    def __init__(self, base_url, auth_token):
        self._pipeline_url = base_url.rstrip("/") + "/v2/pipeline"
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {auth_token}",
                "Content-Type": "application/json",
            }
        )

    def _run(self, stmts):
        requests_body = [
            {"type": "execute", "stmt": {"sql": sql, "args": [_to_arg(p) for p in params]}}
            for sql, params in stmts
        ]
        requests_body.append({"type": "close"})

        resp = self._session.post(
            self._pipeline_url,
            json={"requests": requests_body},
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()

        results = []
        for entry in payload.get("results", []):
            if entry.get("type") == "error":
                error = entry.get("error", {})
                raise RuntimeError(f"Turso 오류: {error.get('message', error)}")
            response = entry.get("response")
            if response and response.get("type") == "execute":
                results.append(response["result"])
        return results

    def execute(self, sql, params=()):
        results = self._run([(sql, params)])
        result = results[0] if results else {"cols": [], "rows": []}
        return _CursorWrapper(result)

    def executescript(self, script):
        statements = [s.strip() for s in script.split(";")]
        stmts = [(s, ()) for s in statements if s]
        if stmts:
            self._run(stmts)

    def commit(self):
        # Turso HTTP pipeline은 요청이 끝나면 바로 커밋되므로 별도 처리가 필요 없다.
        # 기존 sqlite3 스타일 코드(db.commit() 호출)와의 호환을 위해 남겨둔 자리표시자.
        pass

    def close(self):
        self._session.close()


def connect():
    # 대시보드에서 복사/붙여넣기 하는 과정에서 앞뒤 공백이나 줄바꿈이 섞여 들어가면
    # 인증이 실패하므로 strip()으로 방어한다.
    database_url = (os.environ.get("TURSO_DATABASE_URL") or "").strip()
    auth_token = (os.environ.get("TURSO_AUTH_TOKEN") or "").strip()
    if not database_url:
        raise RuntimeError(
            "TURSO_DATABASE_URL 환경변수가 설정되어 있지 않습니다. "
            "Turso 대시보드에서 발급받은 데이터베이스 URL과 인증 토큰을 "
            "TURSO_DATABASE_URL / TURSO_AUTH_TOKEN 환경변수로 설정해주세요."
        )
    http_url = database_url.replace("libsql://", "https://", 1)
    return Connection(http_url, auth_token)

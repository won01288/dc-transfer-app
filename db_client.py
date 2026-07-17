# Turso(libSQL) 연결 래퍼.
# libsql 파이썬 바인딩은 sqlite3와 달리 row_factory를 지원하지 않고 결과를
# 튜플로만 반환하므로, app.py의 기존 코드(row["column"] 형태의 접근)가 그대로
# 동작하도록 cursor.description을 이용해 dict형 Row로 변환해준다.
import os

import libsql


class Row(dict):
    pass


class _CursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def _to_row(self, raw):
        if raw is None:
            return None
        columns = [col[0] for col in self._cursor.description]
        return Row(zip(columns, raw))

    def fetchone(self):
        return self._to_row(self._cursor.fetchone())

    def fetchall(self):
        return [self._to_row(raw) for raw in self._cursor.fetchall()]


class Connection:
    def __init__(self, raw_conn):
        self._conn = raw_conn

    def execute(self, sql, params=()):
        return _CursorWrapper(self._conn.execute(sql, params))

    def executescript(self, script):
        self._conn.executescript(script)

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def connect():
    database_url = os.environ.get("TURSO_DATABASE_URL")
    auth_token = os.environ.get("TURSO_AUTH_TOKEN")
    if not database_url:
        raise RuntimeError(
            "TURSO_DATABASE_URL 환경변수가 설정되어 있지 않습니다. "
            "Turso 대시보드에서 발급받은 데이터베이스 URL과 인증 토큰을 "
            "TURSO_DATABASE_URL / TURSO_AUTH_TOKEN 환경변수로 설정해주세요."
        )
    raw = libsql.connect(database=database_url, auth_token=auth_token or "")
    return Connection(raw)

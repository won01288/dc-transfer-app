// Flask 백엔드(app.py)와 통신하는 공통 함수
// 프론트엔드와 백엔드가 같은 출처(same-origin)에서 서빙되므로 CORS 프리플라이트가
// 발생하지 않아 표준 JSON 형식을 그대로 사용할 수 있습니다.
async function callApi(action, payload) {
  const res = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...payload }),
  });

  if (!res.ok) {
    throw new Error("서버 응답 오류 (" + res.status + ")");
  }

  return res.json();
}

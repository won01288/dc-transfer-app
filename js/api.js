// Apps Script 웹앱과 통신하는 공통 함수
// Content-Type을 "text/plain"으로 보내는 이유:
// application/json으로 보내면 브라우저가 먼저 OPTIONS(preflight) 요청을 보내는데,
// Apps Script 웹앱은 이 요청을 처리하지 못해 CORS 오류가 발생합니다.
// text/plain으로 보내면 preflight 없이 바로 요청이 전달됩니다.
async function callApi(action, payload) {
  if (!API_URL || API_URL.indexOf("http") !== 0) {
    throw new Error("API_URL이 설정되지 않았습니다. js/config.js를 확인해주세요.");
  }

  const res = await fetch(API_URL, {
    method: "POST",
    headers: { "Content-Type": "text/plain;charset=utf-8" },
    body: JSON.stringify({ action, ...payload }),
  });

  if (!res.ok) {
    throw new Error("서버 응답 오류 (" + res.status + ")");
  }

  return res.json();
}

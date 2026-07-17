const $ = (id) => document.getElementById(id);

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

// "■ 신청기준 : ..." 처럼 줄바꿈이 있는 안내문을 <br>로 변환해서 보여준다.
function renderMultiline(text) {
  return escapeHtml(text).replace(/\n/g, "<br>");
}

function renderSection(section) {
  const items = (section.items || [])
    .map((item) => `<li>${renderMultiline(item)}</li>`)
    .join("");
  return `
    <div class="withdrawal-section">
      <h3>${escapeHtml(section.heading)}</h3>
      <ul class="doc-list">${items}</ul>
    </div>
  `;
}

function renderReason(reason, idx) {
  const sections = (reason.sections || []).map(renderSection).join("");
  return `
    <div class="accordion-item" data-idx="${idx}">
      <button class="accordion-header" type="button">
        <span>${escapeHtml(reason.title)}</span>
        <span class="accordion-arrow">▾</span>
      </button>
      <div class="accordion-body hidden">
        <p class="withdrawal-summary">${renderMultiline(reason.summary)}</p>
        ${sections}
      </div>
    </div>
  `;
}

async function loadWithdrawalInfo() {
  try {
    const res = await callApi("withdrawalInfo", {});
    if (!res.success) {
      $("introText").textContent = "안내 정보를 불러오지 못했습니다.";
      return;
    }

    $("introText").innerHTML = renderMultiline(res.intro || "");

    const reasons = res.reasons || [];
    $("reasonList").innerHTML = reasons.map(renderReason).join("");

    document.querySelectorAll(".accordion-header").forEach((btn) => {
      btn.addEventListener("click", () => {
        const body = btn.nextElementSibling;
        const willOpen = body.classList.contains("hidden");
        body.classList.toggle("hidden", !willOpen);
        btn.classList.toggle("open", willOpen);
      });
    });

    // 첫 번째 항목은 기본으로 펼쳐서 보여준다.
    const firstHeader = document.querySelector(".accordion-header");
    if (firstHeader) firstHeader.click();
  } catch (err) {
    $("introText").textContent = "안내 정보를 불러오는 중 오류가 발생했습니다: " + err.message;
  }
}

loadWithdrawalInfo();

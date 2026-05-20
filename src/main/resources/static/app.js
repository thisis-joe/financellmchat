const openButton = document.querySelector("#chatbot-button");
const panel = document.querySelector("#chatbot-panel");
const closeButton = document.querySelector("#chatbot-close");
const chatDate = document.querySelector("#chat-date");
const messages = document.querySelector("#chat-messages");
const form = document.querySelector("#chat-form");
const input = document.querySelector("#chat-input");
const mobileMedia = window.matchMedia("(max-width: 640px)");
let lastQuestionContext = "";
const chatSessionId = getOrCreateSessionId();
let chatHistory = [];

const quickQuestions = {
    "예금": "청년 주택드림 청약통장의 가입대상과 우대이율은 무엇을 확인해야 하나요?",
    "대출": "대출 상품은 아직 제공된 자료가 없나요?",
    "카드": "카드 상품은 아직 제공된 자료가 없나요?",
    "외환": "외환 상품은 아직 제공된 자료가 없나요?",
    "모락": "모락 관련 상품공시 자료는 있나요?",
    "동백전": "동백전 관련 상품공시 자료는 있나요?",
    "사고신고": "사고신고 관련 안내 자료는 있나요?",
    "주요질문": "적립식예금 상품에서 중도해지와 우대이율은 무엇을 봐야 하나요?"
};

const representativeQuestions = [
    "예금 종류를 알려주세요",
    "적립식예금 상품 목록을 알려주세요",
    "50대인데 추천해주세요",
    "만 50세인데 추천해주세요",
    "펫 적금 혜택 받으려면 뭘 해야 해?",
    "장병내일준비적금 만기 때 어떤 서류가 필요해?",
    "청년도약계좌 가입대상 알려줘",
    "주택청약종합저축 가입자격 알려줘",
    "BNK내맘대로 적금 우대이율 조건은?",
    "정기적금 가입기간과 이율은?"
];

const followUpMarkers = ["찾아", "찾아줘", "추천", "골라", "알려줘", "설명해줘", "해줘", "응", "그래"];
const explicitContextTerms = [
    "청년", "청년층", "청년대상", "사회초년", "사회초년생", "대학생", "취준생",
    "군인", "장병", "전역", "입대", "현역",
    "펫", "강아지", "고양이", "반려동물",
    "자이언츠", "롯데", "야구", "농구",
    "직장인", "회사원", "과장", "급여", "월급", "주거래",
    "소액", "소규모", "작은금액", "단기", "짧은기간",
    "임산부", "임신", "출산", "결혼", "신혼", "여성", "여자",
    "시니어", "실버", "어르신", "고령", "노인"
];
const productContextHints = [
    {pattern: /(롯데\s*)?자이언츠|가을\s*야구|야구\s*적금/i, context: "BNK가을야구적금"},
    {pattern: /펫\s*적금|반려동물|강아지|고양이/i, context: "펫 적금"},
    {pattern: /장병|군인|군복무|현역|전역/i, context: "부산은행 장병내일준비적금"},
    {pattern: /청년\s*도약|도약계좌/i, context: "부산은행 청년도약계좌"},
    {pattern: /주택\s*드림|청년\s*주택\s*드림/i, context: "청년 주택드림 청약통장"},
    {pattern: /주택\s*청약\s*종합\s*저축/i, context: "주택청약종합저축"}
];

function todayText() {
    const date = new Date();
    const year = date.getFullYear();
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const weekday = ["일", "월", "화", "수", "목", "금", "토"][date.getDay()];
    return `${year}년 ${month}월 ${day}일(${weekday})`;
}

function isMobileChat() {
    return mobileMedia.matches;
}

function updateChatViewport() {
    const viewport = window.visualViewport;
    const width = viewport?.width ?? window.innerWidth;
    const height = viewport?.height ?? window.innerHeight;
    const top = viewport?.offsetTop ?? 0;

    document.documentElement.style.setProperty("--chat-viewport-width", `${width}px`);
    document.documentElement.style.setProperty("--chat-viewport-height", `${height}px`);
    document.documentElement.style.setProperty("--chat-viewport-top", `${top}px`);
}

function scrollMessagesToBottom() {
    messages.scrollTop = messages.scrollHeight;
}

function getOrCreateSessionId() {
    const storageKey = "finance-rag-chat-session-id";
    const existing = window.localStorage.getItem(storageKey);
    if (existing) {
        return existing;
    }
    const next = window.crypto?.randomUUID
        ? window.crypto.randomUUID()
        : `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    window.localStorage.setItem(storageKey, next);
    return next;
}

function rememberChatTurn(role, content) {
    if (!content) {
        return;
    }
    chatHistory.push({role, content: String(content).slice(0, 1200)});
    chatHistory = chatHistory.slice(-12);
}

function focusChatInput() {
    try {
        input.focus({preventScroll: true});
    } catch (error) {
        input.focus();
    }
}

function rememberQuestionContext(question) {
    const ageMatch = question.match(/(?:만\s*)?\d{1,3}\s*세|\d{2,3}\s*대/);
    if (ageMatch) {
        lastQuestionContext = `${ageMatch[0].replace(/\s+/g, " ")} 조건`;
        return;
    }

    for (const hint of productContextHints) {
        if (hint.pattern.test(question)) {
            lastQuestionContext = hint.context;
            return;
        }
    }
}

function hasExplicitQuestionContext(question) {
    const compact = question.replace(/\s+/g, "");
    if (/(?:만\s*)?\d{1,3}\s*세|\d{2,3}\s*대/.test(question)) {
        return true;
    }
    if (productContextHints.some((hint) => hint.pattern.test(question))) {
        return true;
    }
    return explicitContextTerms.some((term) => compact.includes(term));
}

function isFollowUpQuestion(question) {
    const compact = question.replace(/\s+/g, "");
    if (!lastQuestionContext || compact.length > 8) {
        return false;
    }
    if (hasExplicitQuestionContext(question)) {
        return false;
    }
    return followUpMarkers.some((marker) => compact.includes(marker));
}

function resolveQuestionForRequest(question) {
    if (!isFollowUpQuestion(question)) {
        return question;
    }
    if (/조건$/.test(lastQuestionContext)) {
        return `${lastQuestionContext}에 맞는 적립식예금 추천해줘`;
    }
    return `${lastQuestionContext} 설명해줘`;
}

function setChatOpen(isOpen) {
    document.documentElement.classList.toggle("chat-lock", isOpen);
    document.body.classList.toggle("chat-lock", isOpen);
    if (isOpen) {
        updateChatViewport();
    }
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, {
        headers: {"Content-Type": "application/json"},
        ...options
    });
    if (!response.ok) {
        throw new Error(`요청 실패: ${response.status}`);
    }
    return response.json();
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function formatAnswerLine(line) {
    const hiddenLabels = ["출처:", "근거 문서:", "사용 가능한 출처 파일 제목:"];
    for (const label of hiddenLabels) {
        if (line.startsWith(label)) {
            return "";
        }
    }

    const removableLabels = ["핵심 답변:", "확인 내용:", "추가 확인 필요:", "답변:"];
    for (const label of removableLabels) {
        if (line.startsWith(label)) {
            return escapeHtml(line.slice(label.length).trim());
        }
    }

    return escapeHtml(line);
}

function renderAnswer(answer) {
    const lines = String(answer ?? "")
        .split(/\n+/)
        .map((line) => line.trim())
        .filter(Boolean);

    let html = "";
    let inList = false;
    for (const line of lines) {
        if (line.startsWith("- ")) {
            if (!inList) {
                html += "<ul>";
                inList = true;
            }
            html += `<li>${escapeHtml(line.slice(2).trim())}</li>`;
            continue;
        }

        if (inList) {
            html += "</ul>";
            inList = false;
        }
        const formattedLine = formatAnswerLine(line);
        if (formattedLine) {
            html += `<p>${formattedLine}</p>`;
        }
    }

    if (inList) {
        html += "</ul>";
    }
    return `<div class="answer-text">${html}</div>`;
}

function mascotHtml() {
    return `
        <span class="mascot" aria-hidden="true">
            <span class="mascot-ear left"></span>
            <span class="mascot-ear right"></span>
            <span class="mascot-face">
                <span class="mascot-eye left"></span>
                <span class="mascot-eye right"></span>
                <span class="mascot-mouth"></span>
            </span>
            <span class="headset left"></span>
            <span class="headset right"></span>
        </span>
    `;
}

function appendBot(html, extraClass = "") {
    const row = document.createElement("div");
    row.className = "bot-row";
    row.innerHTML = `
        <div class="bot-avatar">${mascotHtml()}</div>
        <div class="bubble bot-bubble ${extraClass}">${html}</div>
    `;
    messages.appendChild(row);
    scrollMessagesToBottom();
    return row;
}

function appendUser(text) {
    const row = document.createElement("div");
    row.className = "user-row";
    row.innerHTML = `<div class="bubble user-bubble">${escapeHtml(text)}</div>`;
    messages.appendChild(row);
    scrollMessagesToBottom();
}

function renderCitations(citations) {
    if (!citations || citations.length === 0) {
        return "";
    }

    const cards = citations.map((citation) => {
        const downloadUrl = citation.documentId
            ? `/api/documents/${encodeURIComponent(citation.documentId)}/download`
            : "";
        const link = downloadUrl
            ? `<a href="${escapeHtml(downloadUrl)}" download>다운로드</a>`
            : "";
        return `
            <div class="citation-card">
                <span>자료</span>
                <strong>${escapeHtml(citation.title)}</strong>
                ${link}
            </div>
        `;
    }).join("");

    return `<div class="citation-list">${cards}</div>`;
}

function renderFeedbackActions(historyId) {
    if (!historyId) {
        return "";
    }
    return `
        <div class="feedback-actions" data-history-id="${escapeHtml(historyId)}">
            <button type="button" data-rating="HELPFUL">도움됨</button>
            <button type="button" data-rating="NOT_HELPFUL">개선 필요</button>
            <span class="feedback-status" aria-live="polite"></span>
        </div>
    `;
}

function renderEvidenceAction(historyId, citations = []) {
    if (!historyId || !citations || citations.length === 0) {
        return "";
    }
    return `
        <div class="evidence-actions" data-history-id="${escapeHtml(historyId)}">
            <button class="evidence-toggle" type="button" aria-expanded="false">답변근거</button>
            <span class="evidence-status" aria-live="polite"></span>
        </div>
    `;
}

function renderEvidencePanel(evidence) {
    const items = evidence.evidences || [];
    const itemHtml = items.map((item) => {
        const score = Number.isFinite(Number(item.score))
            ? Number(item.score).toFixed(3)
            : "-";
        const downloadUrl = item.documentId
            ? `/api/documents/${encodeURIComponent(item.documentId)}/download`
            : "";
        const link = downloadUrl
            ? `<a href="${escapeHtml(downloadUrl)}" download>다운로드</a>`
            : "";
        return `
            <li>
                <div class="evidence-item-head">
                    <strong>${item.rank}. ${escapeHtml(item.title)}</strong>
                    <span>score ${escapeHtml(score)}</span>
                </div>
                <p>${escapeHtml(item.snippet || "발췌문이 없습니다.")}</p>
                ${link}
            </li>
        `;
    }).join("");

    return `
        <div class="evidence-panel">
            <p>${escapeHtml(evidence.summary)}</p>
            ${items.length ? `<ol>${itemHtml}</ol>` : ""}
        </div>
    `;
}

async function toggleEvidence(actions) {
    const button = actions.querySelector(".evidence-toggle");
    const status = actions.querySelector(".evidence-status");
    const existing = actions.querySelector(".evidence-panel");
    if (existing) {
        existing.remove();
        button.setAttribute("aria-expanded", "false");
        return;
    }

    button.disabled = true;
    status.textContent = "불러오는 중";
    try {
        const evidence = await requestJson(`/api/histories/${actions.dataset.historyId}/evidence`);
        actions.insertAdjacentHTML("beforeend", renderEvidencePanel(evidence));
        button.setAttribute("aria-expanded", "true");
        status.textContent = "";
    } catch (error) {
        status.textContent = "실패";
    } finally {
        button.disabled = false;
    }
}

function showRepresentativeQuestions() {
    appendUser("주요질문");
    const html = `
        <div class="question-list-intro">
            <p><strong>자주 확인하는 질문 10개입니다.</strong></p>
            <p>궁금한 항목을 누르면 바로 질문할 수 있어요.</p>
        </div>
        <div class="question-list">
            ${representativeQuestions.map((question, index) => `
                <button class="question-list-button" type="button" data-index="${index}">
                    <span>${index + 1}</span>
                    ${escapeHtml(question)}
                </button>
            `).join("")}
        </div>
    `;
    const row = appendBot(html, "question-list-bubble");
    row.querySelectorAll(".question-list-button").forEach((button) => {
        button.addEventListener("click", async () => {
            const question = representativeQuestions[Number(button.dataset.index)];
            if (!question) {
                return;
            }
            await ask(question);
        });
    });
}

async function submitFeedback(historyId, rating, statusElement) {
    await requestJson(`/api/histories/${historyId}/feedback`, {
        method: "POST",
        body: JSON.stringify({rating})
    });
    statusElement.textContent = "저장됨";
}

function welcome() {
    messages.innerHTML = "";
    appendBot(`
        <div class="welcome-card">
            <p><strong>안녕하세요.</strong></p>
            <p>BNK부산은행 상품공시 AI챗봇입니다.</p>
            <p>현재는 <strong>예금상품 &gt; 적립식예금</strong> PDF 기준으로 답변합니다.</p>
        </div>
    `);

    const quickGrid = document.createElement("div");
    quickGrid.className = "quick-grid";
    quickGrid.innerHTML = Object.keys(quickQuestions).map((label) => {
        const disabled = label === "예금" || label === "주요질문" ? "" : "disabled";
        return `<button class="quick-button" type="button" ${disabled} data-label="${escapeHtml(label)}">${escapeHtml(label)}</button>`;
    }).join("");
    messages.appendChild(quickGrid);

    quickGrid.querySelectorAll(".quick-button:not([disabled])").forEach((button) => {
        button.addEventListener("click", () => {
            if (button.dataset.label === "주요질문") {
                showRepresentativeQuestions();
                return;
            }
            input.value = quickQuestions[button.dataset.label];
            focusChatInput();
        });
    });
}

async function ask(question, requestQuestion = question) {
    appendUser(question);
    const loading = appendBot(`<span class="loading">답변을 찾고 있습니다...</span>`);
    const requestHistory = chatHistory.slice(-10);
    rememberChatTurn("user", question);

    try {
        const result = await requestJson("/api/ask", {
            method: "POST",
            body: JSON.stringify({
                question: requestQuestion,
                sessionId: chatSessionId,
                history: requestHistory
            })
        });
        loading.querySelector(".bot-bubble").innerHTML = `
            ${renderAnswer(result.answer)}
            ${renderCitations(result.citations)}
            ${renderEvidenceAction(result.historyId, result.citations)}
            ${renderFeedbackActions(result.historyId)}
        `;
        rememberChatTurn("assistant", result.answer);
        loading.querySelectorAll(".evidence-actions").forEach((actions) => {
            actions.querySelector(".evidence-toggle").addEventListener("click", async () => {
                await toggleEvidence(actions);
                scrollMessagesToBottom();
            });
        });
        loading.querySelectorAll(".feedback-actions button").forEach((button) => {
            button.addEventListener("click", async () => {
                const actions = button.closest(".feedback-actions");
                const status = actions.querySelector(".feedback-status");
                actions.querySelectorAll("button").forEach((item) => {
                    item.disabled = true;
                });
                try {
                    await submitFeedback(actions.dataset.historyId, button.dataset.rating, status);
                } catch (error) {
                    status.textContent = "실패";
                    actions.querySelectorAll("button").forEach((item) => {
                        item.disabled = false;
                    });
                }
            });
        });
    } catch (error) {
        loading.querySelector(".bot-bubble").textContent = "답변을 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.";
    }
    scrollMessagesToBottom();
}

updateChatViewport();

window.addEventListener("resize", updateChatViewport);
if (mobileMedia.addEventListener) {
    mobileMedia.addEventListener("change", updateChatViewport);
} else if (mobileMedia.addListener) {
    mobileMedia.addListener(updateChatViewport);
}
if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
        updateChatViewport();
        requestAnimationFrame(scrollMessagesToBottom);
    });
    window.visualViewport.addEventListener("scroll", updateChatViewport);
}

openButton.addEventListener("click", () => {
    panel.hidden = false;
    openButton.hidden = true;
    setChatOpen(true);
    chatDate.textContent = todayText();
    welcome();
    if (!isMobileChat()) {
        focusChatInput();
    }
});

closeButton.addEventListener("click", () => {
    input.blur();
    panel.hidden = true;
    openButton.hidden = false;
    setChatOpen(false);
});

input.addEventListener("focus", () => {
    updateChatViewport();
    window.setTimeout(scrollMessagesToBottom, 250);
});

input.addEventListener("blur", updateChatViewport);

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const question = input.value.trim();
    if (!question) {
        return;
    }
    input.value = "";
    const requestQuestion = resolveQuestionForRequest(question);
    rememberQuestionContext(question);
    await ask(question, requestQuestion);
});

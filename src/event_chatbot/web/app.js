const SESSION_KEY = "event_chatbot_session_id";

const messagesEl = document.querySelector("#messages");
const eventGridEl = document.querySelector("#eventGrid");
const resultCountEl = document.querySelector("#resultCount");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#messageInput");
const sendButtonEl = document.querySelector("#sendButton");
const refreshButtonEl = document.querySelector("#refreshSession");
const promptButtons = document.querySelectorAll("[data-prompt]");
const thinkingPhrases = [
  "I'm thinking",
  "Finding the best fits",
  "Checking the city lights",
  "Reading the event map",
];

let sessionId = getOrCreateSessionId();
let isLoading = false;

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message || isLoading) {
    return;
  }
  submitMessage(message);
});

refreshButtonEl.addEventListener("click", () => {
  sessionId = createSessionId();
  localStorage.setItem(SESSION_KEY, sessionId);
  messagesEl.innerHTML = "";
  renderAssistantMessage(
    "New session started. Tell me the city, mood, budget, or kind of event you want."
  );
  renderEventCards([]);
  inputEl.focus();
});

promptButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const prompt = button.dataset.prompt;
    if (!prompt || isLoading) {
      return;
    }
    inputEl.value = prompt;
    submitMessage(prompt);
  });
});

async function submitMessage(message) {
  setLoading(true);
  renderUserMessage(message);
  inputEl.value = "";
  const loadingEl = renderThinkingMessage();

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        message,
      }),
    });

    const responseText = await response.text();
    let payload;
    try {
      payload = JSON.parse(responseText);
    } catch (error) {
      console.error("Chat response was not valid JSON", error, responseText);
      throw new Error("Invalid chat response JSON");
    }
    removeThinkingMessage(loadingEl);

    if (!response.ok) {
      console.error("Chat request failed", response.status, payload);
      renderAssistantMessage("I couldn't reach the event brain. Try again in a moment.");
      renderEventCards([]);
      return;
    }

    if (!payload || typeof payload.assistant_message !== "string") {
      console.error("Chat response missed assistant_message", payload);
      renderAssistantMessage("I got a response, but it was missing the final message.");
      renderEventCards([]);
      return;
    }

    try {
      renderAssistantMessage(payload.assistant_message);
      renderEventCards(Array.isArray(payload.results) ? payload.results : []);
    } catch (error) {
      console.error("Failed to render chat response", error, payload);
      renderAssistantMessage("I found results, but the interface could not render them.");
      renderEventCards([]);
    }
  } catch (error) {
    console.error("Chat request failed before rendering", error);
    removeThinkingMessage(loadingEl);
    renderAssistantMessage("I couldn't reach the event brain. Try again in a moment.");
    renderEventCards([]);
  } finally {
    setLoading(false);
  }
}

function renderUserMessage(message) {
  const article = document.createElement("article");
  article.className = "message user";
  article.innerHTML = `<div class="bubble"></div>`;
  article.querySelector(".bubble").textContent = message;
  messagesEl.appendChild(article);
  scrollMessages();
}

function renderAssistantMessage(message) {
  const article = document.createElement("article");
  article.className = "message assistant";
  article.innerHTML = `
    <div class="avatar" aria-hidden="true"><span class="bot-face"></span></div>
    <div class="bubble"></div>
  `;
  article.querySelector(".bubble").append(...formatMessage(message));
  messagesEl.appendChild(article);
  scrollMessages();
}

function renderThinkingMessage() {
  const article = document.createElement("article");
  article.className = "message assistant";
  let phraseIndex = 0;
  article.innerHTML = `
    <div class="avatar" aria-hidden="true"><span class="bot-face"></span></div>
    <div class="bubble">
      <span class="thinking">
        <span class="thinking-text">${escapeHtml(thinkingPhrases[phraseIndex])}</span>
        <span class="dots" aria-hidden="true"><span></span><span></span><span></span></span>
      </span>
    </div>
  `;
  const phraseEl = article.querySelector(".thinking-text");
  const timerId = window.setInterval(() => {
    phraseIndex = (phraseIndex + 1) % thinkingPhrases.length;
    phraseEl.textContent = thinkingPhrases[phraseIndex];
  }, 2000);
  article.cleanup = () => window.clearInterval(timerId);
  messagesEl.appendChild(article);
  scrollMessages();
  return article;
}

function removeThinkingMessage(article) {
  if (typeof article.cleanup === "function") {
    article.cleanup();
  }
  article.remove();
}

function renderEventCards(results) {
  const topResults = results.slice(0, 3);
  eventGridEl.innerHTML = "";
  resultCountEl.textContent = topResults.length
    ? `${topResults.length} top match${topResults.length === 1 ? "" : "es"}`
    : "No cards yet";

  if (!topResults.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No matching event cards for this query. Try broadening the filters.";
    eventGridEl.appendChild(empty);
    return;
  }

  topResults.forEach((rankedEvent) => {
    const event = rankedEvent.event;
    const card = document.createElement("article");
    card.className = "event-card";
    card.innerHTML = `
      <div class="event-image">
        ${renderImage(event)}
        <span class="source-badge">${escapeHtml(event.source || "event")}</span>
      </div>
      <div class="event-body">
        <h3>${escapeHtml(event.title || "Untitled event")}</h3>
        <p class="event-meta">
          ${escapeHtml(formatDate(event.start_at))}
          <br />
          ${escapeHtml(event.venue_name || event.city || "Venue unavailable")}
        </p>
        <div class="card-footer">
          <span class="score-pill">${formatScore(rankedEvent.score)}</span>
          ${renderLink(event.url)}
        </div>
      </div>
    `;
    eventGridEl.appendChild(card);
  });
}

function renderImage(event) {
  if (!event.image_url) {
    return "";
  }
  return `<img src="${escapeAttribute(event.image_url)}" alt="${escapeAttribute(event.title || "Event image")}" loading="lazy" />`;
}

function renderLink(url) {
  if (!url) {
    return `<span class="event-link">No link</span>`;
  }
  return `<a class="event-link" href="${escapeAttribute(url)}" target="_blank" rel="noreferrer">Open</a>`;
}

function formatMessage(message) {
  const cleaned = String(message)
    .replace(/\*\*(.*?)\*\*/g, "$1")
    .replace(/^\s*#{1,6}\s+/gm, "")
    .replace(/^\s*[-*]\s+/gm, "• ")
    .replace(/\s+-\s+/g, " - ");

  return cleaned
    .split(/\n{2,}/)
    .map((block) => {
      const paragraph = document.createElement("p");
      paragraph.textContent = block.trim();
      return paragraph;
    })
    .filter((paragraph) => paragraph.textContent);
}

function formatDate(value) {
  if (!value) {
    return "Date unavailable";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatScore(score) {
  if (typeof score !== "number") {
    return "Match";
  }
  return `${Math.round(score * 100)}% match`;
}

function setLoading(nextLoading) {
  isLoading = nextLoading;
  inputEl.disabled = nextLoading;
  sendButtonEl.disabled = nextLoading;
}

function scrollMessages() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function getOrCreateSessionId() {
  const existing = localStorage.getItem(SESSION_KEY);
  if (existing) {
    return existing;
  }
  const next = createSessionId();
  localStorage.setItem(SESSION_KEY, next);
  return next;
}

function createSessionId() {
  if (crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replaceAll("`", "&#096;");
}

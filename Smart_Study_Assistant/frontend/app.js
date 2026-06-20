const API_BASE = "http://127.0.0.1:8000";

let documentsCache = [];
let quizState = { total: 0, answered: 0, correct: 0 };
let deckState = { cards: [], index: 0, flipped: false };

// ---------------------------------------------------------------------
// Tab navigation
// ---------------------------------------------------------------------

function switchTab(tabId) {
  document.querySelectorAll(".tab-panel").forEach((el) => el.classList.remove("active"));
  document.getElementById(tabId).classList.add("active");

  document.querySelectorAll(".nav-link").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });

  // Keep document dropdowns fresh whenever these tabs are opened
  if (tabId === "flashcards" || tabId === "quiz" || tabId === "upload") {
    loadDocuments();
  }
}

// ---------------------------------------------------------------------
// Small UI helpers
// ---------------------------------------------------------------------

function showLoader(id, show) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle("show", show);
}

function showAlert(id, message, type = "error") {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = message;
  el.className = `alert show ${type}`;
}

function hideAlert(id) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = "alert";
  el.textContent = "";
}

function renderMarkdown(containerId, text) {
  const el = document.getElementById(containerId);
  if (!el) return;

  if (!text) {
    el.innerHTML = '<p class="placeholder">Nothing to show yet.</p>';
    return;
  }

  if (window.marked) {
    el.innerHTML = marked.parse(text);
  } else {
    el.textContent = text;
  }
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch (err) {
    return {};
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}

// ---------------------------------------------------------------------
// Backend connection status
// ---------------------------------------------------------------------

async function checkApiStatus() {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");

  try {
    const res = await fetch(`${API_BASE}/health`);
    if (!res.ok) throw new Error("not ok");
    dot.className = "status-dot online";
    text.textContent = "Backend Connected";
  } catch (err) {
    dot.className = "status-dot offline";
    text.textContent = "Backend not reachable";
  }
}

// ---------------------------------------------------------------------
// Documents: upload, list, clear, and dropdown population
// ---------------------------------------------------------------------

async function loadDocuments() {
  const list = document.getElementById("documentsList");
  const countMeta = document.getElementById("docCountMeta");

  try {
    const res = await fetch(`${API_BASE}/documents`);
    const docs = await safeJson(res);
    documentsCache = Array.isArray(docs) ? docs : [];

    if (countMeta) {
      countMeta.textContent = `${documentsCache.length} uploaded`;
    }

    if (list) {
      if (!documentsCache.length) {
        list.innerHTML = '<p class="muted">No documents uploaded yet.</p>';
      } else {
        list.innerHTML = documentsCache
          .map(
            (doc) => `
              <div class="doc-card">
                <span class="doc-index mono">#${doc.id}</span>
                <div style="flex:1; min-width:0;">
                  <strong>${escapeHtml(doc.filename)}</strong>
                  <small>${doc.characters.toLocaleString()} characters extracted</small>
                </div>
              </div>`
          )
          .join("");
      }
    }

    populateDocSelect("flashcardDocSelect");
    populateDocSelect("quizDocSelect");
  } catch (err) {
    if (list) list.innerHTML = '<p class="muted">Could not load documents from the backend.</p>';
  }
}

function populateDocSelect(selectId) {
  const select = document.getElementById(selectId);
  if (!select) return;

  const previousValue = select.value;

  const options = ['<option value="">-- Select a document --</option>'].concat(
    documentsCache.map(
      (doc) => `<option value="${doc.id}">${escapeHtml(doc.filename)} (ID: ${doc.id})</option>`
    )
  );

  select.innerHTML = options.join("");

  if (previousValue && documentsCache.some((d) => String(d.id) === previousValue)) {
    select.value = previousValue;
  }
}

async function uploadDocument() {
  const fileInput = document.getElementById("fileInput");
  hideAlert("uploadAlert");

  if (!fileInput || !fileInput.files.length) {
    showAlert("uploadAlert", "Please select a file first.");
    return;
  }

  const formData = new FormData();
  formData.append("file", fileInput.files[0]);

  showLoader("uploadLoader", true);

  try {
    const res = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || "Upload failed.");
    }

    showAlert(
      "uploadAlert",
      `"${data.filename}" uploaded successfully (${data.characters_extracted.toLocaleString()} characters extracted).`,
      "success"
    );
    fileInput.value = "";
    await loadDocuments();
  } catch (err) {
    showAlert("uploadAlert", err.message || "Upload failed. Please try again.");
  } finally {
    showLoader("uploadLoader", false);
  }
}

async function clearAllDocuments() {
  if (!confirm("This will remove all uploaded document records. Continue?")) return;

  try {
    const res = await fetch(`${API_BASE}/documents`, { method: "DELETE" });
    await safeJson(res);
    showAlert("uploadAlert", "All documents cleared.", "info");
    await loadDocuments();
  } catch (err) {
    showAlert("uploadAlert", "Could not clear documents. Please try again.");
  }
}

// ---------------------------------------------------------------------
// Q&A
// ---------------------------------------------------------------------

async function askQuestion() {
  const question = document.getElementById("questionInput").value.trim();
  const useDocs = document.getElementById("useDocs").checked;

  hideAlert("askAlert");

  if (!question) {
    showAlert("askAlert", "Please enter a question first.");
    return;
  }

  document.getElementById("askBtn").disabled = true;
  showLoader("askLoader", true);

  try {
    const res = await fetch(`${API_BASE}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, use_uploaded_docs: useDocs }),
    });

    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || "Failed to get an answer.");
    }

    renderMarkdown("answerOutput", data.answer);
  } catch (err) {
    showAlert("askAlert", err.message || "Failed to get an answer. Please try again.");
  } finally {
    document.getElementById("askBtn").disabled = false;
    showLoader("askLoader", false);
  }
}

// ---------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------

async function summarizeNotes() {
  hideAlert("summaryAlert");
  document.getElementById("summaryBtn").disabled = true;
  showLoader("summaryLoader", true);

  try {
    const res = await fetch(`${API_BASE}/summarize`, { method: "POST" });
    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || "Failed to generate summary.");
    }

    renderMarkdown("summaryOutput", data.summary);
  } catch (err) {
    showAlert("summaryAlert", err.message || "Failed to generate summary. Please try again.");
  } finally {
    document.getElementById("summaryBtn").disabled = false;
    showLoader("summaryLoader", false);
  }
}

// ---------------------------------------------------------------------
// Study Plan
// ---------------------------------------------------------------------

async function generateStudyPlan() {
  const topic = document.getElementById("topicInput").value.trim();
  const days = Number(document.getElementById("daysInput").value);

  hideAlert("planAlert");

  if (!topic) {
    showAlert("planAlert", "Please enter a topic.");
    return;
  }
  if (!days || days < 1) {
    showAlert("planAlert", "Please enter a valid number of days.");
    return;
  }

  document.getElementById("planBtn").disabled = true;
  showLoader("planLoader", true);

  try {
    const res = await fetch(`${API_BASE}/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topic, days }),
    });

    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || "Failed to generate study plan.");
    }

    renderMarkdown("planOutput", data.study_plan);
  } catch (err) {
    showAlert("planAlert", err.message || "Failed to generate study plan. Please try again.");
  } finally {
    document.getElementById("planBtn").disabled = false;
    showLoader("planLoader", false);
  }
}

// ---------------------------------------------------------------------
// Flashcards — one-at-a-time deck
// ---------------------------------------------------------------------

async function loadFlashcards() {
  const docId = document.getElementById("flashcardDocSelect").value;
  const numCards = Number(document.getElementById("flashcardCount").value) || 10;
  const container = document.getElementById("flashcardContainer");

  hideAlert("flashcardAlert");
  container.innerHTML = "";
  deckState = { cards: [], index: 0, flipped: false };

  if (!docId) {
    showAlert("flashcardAlert", "No document selected. Please choose a document first.");
    return;
  }

  document.getElementById("flashcardBtn").disabled = true;
  showLoader("flashcardLoader", true);

  try {
    const res = await fetch(
      `${API_BASE}/flashcards?document_id=${encodeURIComponent(docId)}&num_cards=${encodeURIComponent(numCards)}`
    );
    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || "Failed to generate flashcards.");
    }

    const cards = data.flashcards || [];
    if (!cards.length) {
      showAlert("flashcardAlert", "No flashcards could be generated from this document.", "info");
      return;
    }

    deckState = { cards, index: 0, flipped: false };
    renderDeck();
  } catch (err) {
    showAlert("flashcardAlert", err.message || "Failed to generate flashcards. Please try again.");
  } finally {
    document.getElementById("flashcardBtn").disabled = false;
    showLoader("flashcardLoader", false);
  }
}

function renderDeck() {
  const container = document.getElementById("flashcardContainer");
  if (!container) return;

  const { cards, index, flipped } = deckState;
  if (!cards.length) {
    container.innerHTML = "";
    return;
  }

  const card = cards[index];
  const total = cards.length;
  const progressPct = ((index + 1) / total) * 100;

  container.innerHTML = `
    <div class="deck-wrap">
      <div class="deck-progress-track">
        <div class="deck-progress-fill" style="width:${progressPct}%"></div>
      </div>
      <div class="deck-counter">CARD ${index + 1} OF ${total}</div>

      <div class="deck-stack">
        <div class="deck-shadow-layer s1"></div>
        <div class="deck-shadow-layer s2"></div>
        <div class="study-card ${flipped ? "flipped" : ""}" id="studyCard" onclick="flipDeckCard()">
          <div class="study-card-inner">
            <div class="study-card-face study-card-front">
              <span class="tag">Question</span>
              <div class="face-text">${escapeHtml(card.question)}</div>
              <span class="hint">Tap to reveal answer</span>
            </div>
            <div class="study-card-face study-card-back">
              <span class="tag">Answer</span>
              <div class="face-text">${escapeHtml(card.answer)}</div>
              <span class="hint">Tap to flip back</span>
            </div>
          </div>
        </div>
      </div>

      <div class="deck-controls">
        <button class="btn-icon" id="deckPrevBtn" onclick="prevDeckCard(event)" ${index === 0 ? "disabled" : ""}>&#8249;</button>
        <span class="deck-flip-hint">Click card to flip</span>
        <button class="btn-icon" id="deckNextBtn" onclick="nextDeckCard(event)" ${index === total - 1 ? "disabled" : ""}>&#8250;</button>
      </div>
    </div>
  `;
}

function flipDeckCard() {
  deckState.flipped = !deckState.flipped;
  const card = document.getElementById("studyCard");
  if (card) card.classList.toggle("flipped", deckState.flipped);
}

function prevDeckCard(event) {
  if (event) event.stopPropagation();
  if (deckState.index <= 0) return;
  deckState.index -= 1;
  deckState.flipped = false;
  renderDeck();
}

function nextDeckCard(event) {
  if (event) event.stopPropagation();
  if (deckState.index >= deckState.cards.length - 1) return;
  deckState.index += 1;
  deckState.flipped = false;
  renderDeck();
}

// Keyboard navigation while the Flashcards tab is open
document.addEventListener("keydown", (e) => {
  const flashTab = document.getElementById("flashcards");
  if (!flashTab || !flashTab.classList.contains("active")) return;
  if (!deckState.cards.length) return;

  if (e.key === "ArrowRight") nextDeckCard();
  if (e.key === "ArrowLeft") prevDeckCard();
  if (e.key === " ") {
    e.preventDefault();
    flipDeckCard();
  }
});

// ---------------------------------------------------------------------
// Quiz
// ---------------------------------------------------------------------

async function loadQuiz() {
  const docId = document.getElementById("quizDocSelect").value;
  const numQuestions = Number(document.getElementById("quizCount").value) || 5;
  const container = document.getElementById("quizContainer");
  const scoreBar = document.getElementById("quizScoreBar");

  hideAlert("quizAlert");
  container.innerHTML = "";
  scoreBar.classList.add("hidden");

  if (!docId) {
    showAlert("quizAlert", "No document selected. Please choose a document first.");
    return;
  }

  document.getElementById("quizBtn").disabled = true;
  showLoader("quizLoader", true);

  try {
    const res = await fetch(
      `${API_BASE}/quiz?document_id=${encodeURIComponent(docId)}&num_questions=${encodeURIComponent(numQuestions)}`
    );
    const data = await safeJson(res);

    if (!res.ok) {
      throw new Error(data.detail || "Failed to generate quiz.");
    }

    const questions = data.quiz || [];
    if (!questions.length) {
      showAlert("quizAlert", "No quiz questions could be generated from this document.", "info");
      return;
    }

    quizState = { total: questions.length, answered: 0, correct: 0 };
    updateQuizScore();
    scoreBar.classList.remove("hidden");

    questions.forEach((q, idx) => {
      const qDiv = document.createElement("div");
      qDiv.className = "quiz-question";

      const titleDiv = document.createElement("div");
      titleDiv.className = "q-title";
      titleDiv.textContent = `Q${idx + 1}. ${q.question}`;
      qDiv.appendChild(titleDiv);

      const optionsDiv = document.createElement("div");
      optionsDiv.className = "quiz-options";

      (q.options || []).forEach((opt) => {
        const btn = document.createElement("button");
        btn.className = "quiz-option";
        btn.type = "button";
        btn.textContent = opt;
        btn.onclick = () => handleQuizAnswer(qDiv, btn, opt, q.answer);
        optionsDiv.appendChild(btn);
      });

      qDiv.appendChild(optionsDiv);
      container.appendChild(qDiv);
    });
  } catch (err) {
    showAlert("quizAlert", err.message || "Failed to generate quiz. Please try again.");
  } finally {
    document.getElementById("quizBtn").disabled = false;
    showLoader("quizLoader", false);
  }
}

function handleQuizAnswer(questionDiv, clickedBtn, selectedOption, correctAnswer) {
  const buttons = questionDiv.querySelectorAll(".quiz-option");
  buttons.forEach((b) => (b.disabled = true));

  buttons.forEach((b) => {
    if (b.textContent === correctAnswer) {
      b.classList.add("correct");
    }
  });

  const isCorrect = selectedOption === correctAnswer;
  if (!isCorrect) {
    clickedBtn.classList.add("incorrect");
  }

  quizState.answered += 1;
  if (isCorrect) quizState.correct += 1;
  updateQuizScore();
}

function updateQuizScore() {
  const fill = document.getElementById("quizScoreFill");
  const label = document.getElementById("quizScoreLabel");
  if (!fill || !label) return;

  const pct = quizState.total ? (quizState.answered / quizState.total) * 100 : 0;
  fill.style.width = `${pct}%`;
  label.textContent = `${quizState.correct} correct / ${quizState.answered} answered / ${quizState.total} total`;
}

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------

checkApiStatus();
loadDocuments();
setInterval(checkApiStatus, 20000);

// Placement test: questions are shown in stages, the server checks the answers.
(() => {
  const BASE_PATH = window.BASE_PATH || "";
  const byId = (id) => document.getElementById(id);

  let queue = [...window.QUESTIONS];
  const answers = [];
  let currentQuestion = null;
  let selectedOption = null;
  let shownCount = 0;
  let experience = "";  // the answer to "have you programmed before"

  function showQuestion(question) {
    currentQuestion = question;
    selectedOption = null;
    shownCount += 1;
    byId("question-counter").textContent = `Вопрос ${shownCount}`;
    byId("progress-bar").style.width = Math.min(100, (shownCount - 1) * 100 / 6) + "%";
    byId("question-text").textContent = question.text;
    byId("question-code").textContent = question.code || "";
    byId("question-code").style.display = question.code ? "block" : "none";
    byId("answer-btn").disabled = true;

    const container = byId("question-options");
    container.innerHTML = "";
    question.options.forEach((option) => {
      const button = document.createElement("button");
      button.className = "option";
      button.textContent = option;
      button.onclick = () => {
        container.querySelectorAll(".option").forEach((other) => other.classList.remove("selected"));
        button.classList.add("selected");
        selectedOption = option;
        byId("answer-btn").disabled = false;
      };
      container.appendChild(button);
    });
  }

  async function submitStage() {
    let data;
    try {
      const response = await fetch(`${BASE_PATH}/hog/test/submit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ answers, experience }),
      });
      data = await response.json();
      if (!response.ok) throw responseError(response, data);
    } catch (error) {
      // Answers are kept: a retry sends the same stage again
      showError(errorText(error), submitStage);
      return;
    }
    if (!data.done) {
      queue = data.questions;
      showQuestion(queue.shift());
      return;
    }
    showResult(data);
  }

  function showResult(result) {
    byId("test-flow").style.display = "none";
    byId("test-result").style.display = "block";
    byId("result-level").textContent = result.level_label;
    if (result.from_zero) {
      // The test was skipped: say where the course will start
      byId("result-score").textContent = "Тест пропускаем: начнём с самого начала.";
      byId("result-gaps").textContent = "Первый модуль — что такое программа, команда print и как читать ошибки.";
      byId("review-card").style.display = "none";
    } else {
      byId("result-score").textContent = `Верно ${result.correct} из ${result.total}`;
      byId("result-gaps").textContent = (result.weak_topics.length
        ? "Обратим внимание на: " + result.weak_topics.join(", ") + "."
        : "Пробелов не нашли — стартуем бодро.")
        + (experience === "other"
          ? " Курс начнётся с модуля «Python после другого языка»: знакомые конструкции в синтаксисе Python."
          : "");
    }
    byId("continue-link").href = `${BASE_PATH}/register`;

    const review = byId("review");
    review.innerHTML = "";
    result.explanations.forEach((item) => {
      const line = document.createElement("p");
      line.innerHTML = `${item.correct ? "✅" : "❌"} <span class="muted">${item.text}</span>`;
      review.appendChild(line);
    });
  }

  function acceptAnswer(value) {
    answers.push({ id: currentQuestion.id, answer: value });
    if (queue.length) {
      showQuestion(queue.shift());
    } else {
      submitStage();
    }
  }

  byId("answer-btn").onclick = () => selectedOption && acceptAnswer(selectedOption);
  byId("skip-btn").onclick = () => acceptAnswer("");

  // The experience question comes first. "Never" goes straight to the result
  // without a test; otherwise the first test question is shown.
  document.querySelectorAll("[data-experience]").forEach((button) => {
    button.onclick = () => {
      experience = button.dataset.experience;
      byId("experience").style.display = "none";
      if (experience === "none") {
        submitStage();
      } else {
        byId("test-flow").style.display = "block";
        showQuestion(queue.shift());
      }
    };
  });
})();

// Lesson task checks: the code is sent to the server, where it actually runs.
(() => {
  const BASE_PATH = window.BASE_PATH || "";
  const escapeHtml = (s) => String(s ?? "").replace(/[&<>]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  async function postJson(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw responseError(response, data);
    return data;
  }

  function showReward(reward) {
    document.getElementById("reward-text").innerHTML =
      `+${reward.xp} XP и +${reward.coins} 🪙 · серия ${reward.streak} дн.` +
      (reward.spins ? `<br>Доступно вращений колеса: <b>${reward.spins}</b>` : "") +
      (reward.capped ? '<br><span class="muted">Сегодня уже три урока — монеты за следующие не начисляются.</span>' : "");

    // A meme after a completed lesson: requirement 3.1, UC-2
    const memeFigure = document.getElementById("reward-meme");
    if (memeFigure) {
      if (reward.meme) {
        memeFigure.querySelector("img").src = reward.meme.url;
        memeFigure.querySelector("figcaption").textContent = reward.meme.caption || "";
        memeFigure.style.display = "block";
      } else {
        memeFigure.style.display = "none";
      }
    }

    // New medals: requirement 3.5, UC-7
    const medalList = document.getElementById("reward-medals");
    if (medalList) {
      const medals = reward.medals || [];
      medalList.innerHTML = medals.map((medal) =>
        `<div class="medal"><span class="icon">${escapeHtml(medal.icon)}</span>` +
        `<span class="name">${escapeHtml(medal.title)}</span></div>`).join("");
      medalList.previousElementSibling.style.display = medals.length ? "block" : "none";
      medalList.style.display = medals.length ? "grid" : "none";
    }

    document.getElementById("reward-modal").classList.add("visible");

    // The admin's header shows "∞": adding to it would produce NaN
    const balance = document.getElementById("balance");
    if (balance) {
      const before = parseInt(balance.textContent, 10);
      if (Number.isFinite(before)) balance.textContent = before + reward.coins;
    }
  }

  function describeResult(result) {
    const lines = [];
    if (result.correct) {
      lines.push('<span class="ok">✅ Верно!</span>');
      if (result.explanation) lines.push(escapeHtml(result.explanation));
    } else {
      lines.push('<span class="bad">❌ Пока не сходится.</span>');
    }
    if (result.error) lines.push(`<span class="bad">${escapeHtml(result.error)}</span>`);
    if (result.output) lines.push("Вывод:\n" + escapeHtml(result.output));
    (result.checks || []).forEach((check) => {
      const mark = check.passed ? '<span class="ok">✓</span>' : '<span class="bad">✗</span>';
      lines.push(`${mark} ${escapeHtml(check.call)} → ожидалось ${escapeHtml(JSON.stringify(check.expected))}` +
                 (check.passed ? "" : `, получено ${escapeHtml(JSON.stringify(check.got))}`) +
                 (check.error ? ` (${escapeHtml(check.error)})` : ""));
    });
    return lines.join("\n");
  }

  document.querySelectorAll(".task").forEach((card) => {
    const taskId = card.dataset.id;
    const kind = card.dataset.kind;
    const output = card.querySelector(".output");
    const checkButton = card.querySelector(".check-btn");
    const hintButton = card.querySelector(".hint-btn");
    let selectedOption = null;

    card.querySelectorAll(".option").forEach((button) => {
      button.onclick = () => {
        card.querySelectorAll(".option").forEach((other) => other.classList.remove("selected"));
        button.classList.add("selected");
        selectedOption = button.dataset.value;
      };
    });

    const editorCode = () => {
      const editor = card.querySelector(".editor");
      return editor ? editor.value : "";
    };

    function collectAnswer() {
      if (kind === "quiz") return { answer: selectedOption || "" };
      if (kind === "predict") return { answer: card.querySelector(".answer-input").value };
      return { code: editorCode() };
    }

    function showOutput(html, cls) {
      output.style.display = "block";
      output.innerHTML = cls ? `<span class="${cls}">${html}</span>` : html;
    }

    checkButton.onclick = async () => {
      showOutput("Проверяю…", "");
      let result;
      try {
        result = await postJson(`${BASE_PATH}/hog/task/${taskId}/check`, collectAnswer());
      } catch (error) {
        showOutput(errorText(error), "bad");
        if (isNetworkError(error)) showError(errorText(error), () => checkButton.click());
        return;
      }

      showOutput(describeResult(result));
      if (result.correct) {
        card.classList.add("correct");
        card.querySelectorAll(".option").forEach((button) => {
          if (button.dataset.value === selectedOption) button.classList.add("correct");
        });
      }
      if (result.lesson_done) showReward(result.lesson_done);
    };

    hintButton.onclick = async () => {
      hintButton.disabled = true;
      showOutput("Думаю…", "");
      try {
        const hint = await postJson(`${BASE_PATH}/hog/task/${taskId}/hint`,
                                    { code: kind === "code" ? editorCode() : "" });
        showOutput("💡 " + escapeHtml(hint.hint), "");
      } catch (error) {
        showOutput("Подсказка сейчас недоступна", "bad");
        showError("Подсказка сейчас недоступна. " + errorText(error), () => hintButton.click());
      }
      hintButton.disabled = false;
    };
  });
})();

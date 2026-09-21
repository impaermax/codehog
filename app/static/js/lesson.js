// Проверка заданий урока: код уходит на сервер, там он реально запускается.
(() => {
  const экранировать = (s) => String(s ?? "").replace(/[&<>]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  document.querySelectorAll(".задание").forEach((карточка) => {
    const id = карточка.dataset.id;
    const тип = карточка.dataset.kind;
    const вывод = карточка.querySelector(".вывод");
    let выбран = null;

    карточка.querySelectorAll(".вариант").forEach((кнопка) => {
      кнопка.onclick = () => {
        карточка.querySelectorAll(".вариант").forEach((э) => э.classList.remove("выбран"));
        кнопка.classList.add("выбран");
        выбран = кнопка.dataset.value;
      };
    });

    function собратьОтвет() {
      if (тип === "quiz") return { answer: выбран || "" };
      if (тип === "predict") return { answer: карточка.querySelector(".ответ").value };
      return { code: карточка.querySelector(".редактор").value };
    }

    function показать(текст, класс) {
      вывод.style.display = "block";
      вывод.innerHTML = класс ? `<span class="${класс}">${текст}</span>` : текст;
    }

    карточка.querySelector(".проверить").onclick = async () => {
      показать("Проверяю…", "");
      let д;
      try {
        const ответ = await fetch(`/hog/task/${id}/check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(собратьОтвет()),
        });
        д = await ответ.json();
        if (!ответ.ok) throw new Error(д.detail || "Ошибка проверки");
      } catch (e) {
        показать(e.message, "плохо");
        return;
      }

      let строки = [];
      if (д.correct) {
        строки.push('<span class="ок">✅ Верно!</span>');
        if (д.explanation) строки.push(экранировать(д.explanation));
      } else {
        строки.push('<span class="плохо">❌ Пока не сходится.</span>');
      }
      if (д.error) строки.push(`<span class="плохо">${экранировать(д.error)}</span>`);
      if (д.output) строки.push("Вывод:\n" + экранировать(д.output));
      (д.checks || []).forEach((п) => {
        const знак = п.passed ? '<span class="ок">✓</span>' : '<span class="плохо">✗</span>';
        строки.push(`${знак} ${экранировать(п.call)} → ожидалось ${экранировать(JSON.stringify(п.expected))}` +
                    (п.passed ? "" : `, получено ${экранировать(JSON.stringify(п.got))}`) +
                    (п.error ? ` (${экранировать(п.error)})` : ""));
      });
      показать(строки.join("\n"));

      if (д.correct) {
        карточка.style.borderColor = "var(--акцент)";
        карточка.querySelectorAll(".вариант").forEach((э) => {
          if (э.dataset.value === выбран) э.classList.add("верно");
        });
      }

      if (д.lesson_done) {
        const н = д.lesson_done;
        document.getElementById("текст-награды").innerHTML =
          `+${н.xp} XP и +${н.coins} 🪙 · серия ${н.streak} дн.` +
          (н.spins ? `<br>Доступно вращений колеса: <b>${н.spins}</b>` : "") +
          (н.capped ? '<br><span class="тише">Сегодня уже три урока — монеты за следующие не начисляются.</span>' : "");
        document.getElementById("окно-награды").classList.add("видно");
        const баланс = document.getElementById("баланс");
        if (баланс) баланс.textContent = Number(баланс.textContent) + н.coins;
      }
    };

    карточка.querySelector(".подсказать").onclick = async (e) => {
      e.target.disabled = true;
      показать("Думаю…", "");
      const код = тип === "code" ? карточка.querySelector(".редактор").value : "";
      try {
        const ответ = await fetch(`/hog/task/${id}/hint`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code: код }),
        });
        const д = await ответ.json();
        показать("💡 " + экранировать(д.hint), "");
      } catch {
        показать("Подсказка сейчас недоступна", "плохо");
      }
      e.target.disabled = false;
    };
  });
})();

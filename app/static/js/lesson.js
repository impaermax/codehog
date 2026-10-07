// Проверка заданий урока: код уходит на сервер, там он реально запускается.
(() => {
  const БАЗА = window.БАЗА || "";
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
        const ответ = await fetch(`${БАЗА}/hog/task/${id}/check`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(собратьОтвет()),
        });
        д = await ответ.json();
        if (!ответ.ok) throw ошибкаОтвета(ответ, д);
      } catch (e) {
        показать(текстОшибки(e), "плохо");
        if (ошибкаСвязи(e)) {
          показатьОшибку(текстОшибки(e), () => карточка.querySelector(".проверить").click());
        }
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
        карточка.classList.add("верно");
        карточка.querySelectorAll(".вариант").forEach((э) => {
          if (э.dataset.value === выбран) э.classList.add("верно");
        });
      }

      if (д.lesson_done) показатьНаграду(д.lesson_done);
    };

    function показатьНаграду(н) {
      document.getElementById("текст-награды").innerHTML =
        `+${н.xp} XP и +${н.coins} 🪙 · серия ${н.streak} дн.` +
        (н.spins ? `<br>Доступно вращений колеса: <b>${н.spins}</b>` : "") +
        (н.capped ? '<br><span class="тише">Сегодня уже три урока — монеты за следующие не начисляются.</span>' : "");

      // Мем после пройденного урока — требование 3.1, UC-2
      const рамкаМема = document.getElementById("мем");
      if (рамкаМема) {
        if (н.meme) {
          рамкаМема.querySelector("img").src = н.meme.url;
          рамкаМема.querySelector("figcaption").textContent = н.meme.caption || "";
          рамкаМема.style.display = "block";
        } else {
          рамкаМема.style.display = "none";
        }
      }

      // Новые медали — требование 3.5, UC-7
      const списокМедалей = document.getElementById("медали-награда");
      if (списокМедалей) {
        const медали = н.medals || [];
        списокМедалей.innerHTML = медали.map((м) =>
          `<div class="медаль"><span class="значок">${экранировать(м.icon)}</span>` +
          `<span class="имя">${экранировать(м.title)}</span></div>`).join("");
        списокМедалей.previousElementSibling.style.display = медали.length ? "block" : "none";
        списокМедалей.style.display = медали.length ? "grid" : "none";
      }

      document.getElementById("окно-награды").classList.add("видно");

      // У админа в шапке стоит «∞» — складывать с ним нельзя, выйдет NaN
      const баланс = document.getElementById("баланс");
      if (баланс) {
        const было = parseInt(баланс.textContent, 10);
        if (Number.isFinite(было)) баланс.textContent = было + н.coins;
      }
    }

    карточка.querySelector(".подсказать").onclick = async (e) => {
      e.target.disabled = true;
      показать("Думаю…", "");
      const код = тип === "code" ? карточка.querySelector(".редактор").value : "";
      try {
        const ответ = await fetch(`${БАЗА}/hog/task/${id}/hint`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code: код }),
        });
        const д = await ответ.json();
        показать("💡 " + экранировать(д.hint), "");
      } catch (ошибка) {
        показать("Подсказка сейчас недоступна", "плохо");
        показатьОшибку("Подсказка сейчас недоступна. " + текстОшибки(ошибка),
                       () => карточка.querySelector(".подсказать").click());
      }
      e.target.disabled = false;
    };
  });
})();

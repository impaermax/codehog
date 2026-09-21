// Входной тест: показываем вопросы этапами, ответы проверяет сервер.
(() => {
  let очередь = [...window.ВОПРОСЫ];
  let ответы = [];
  let текущий = null;
  let выбран = null;
  let всегоПоказано = 0;

  const $ = (id) => document.getElementById(id);

  function показать(вопрос) {
    текущий = вопрос;
    выбран = null;
    всегоПоказано += 1;
    $("счётчик").textContent = `Вопрос ${всегоПоказано}`;
    $("полоса").style.width = Math.min(100, (всегоПоказано - 1) * 100 / 6) + "%";
    $("текст").textContent = вопрос.text;
    $("код").textContent = вопрос.code || "";
    $("код").style.display = вопрос.code ? "block" : "none";
    $("дальше").disabled = true;

    const блок = $("варианты");
    блок.innerHTML = "";
    вопрос.options.forEach((вариант) => {
      const кнопка = document.createElement("button");
      кнопка.className = "вариант";
      кнопка.textContent = вариант;
      кнопка.onclick = () => {
        блок.querySelectorAll(".вариант").forEach((э) => э.classList.remove("выбран"));
        кнопка.classList.add("выбран");
        выбран = вариант;
        $("дальше").disabled = false;
      };
      блок.appendChild(кнопка);
    });
  }

  async function отправитьЭтап() {
    const ответ = await fetch("/hog/test/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers: ответы }),
    });
    const данные = await ответ.json();
    if (!данные.done) {
      очередь = данные.questions;
      показать(очередь.shift());
      return;
    }
    показатьИтог(данные);
  }

  function показатьИтог(д) {
    $("ход").style.display = "none";
    $("итог").style.display = "block";
    $("уровень").textContent = д.level_label;
    $("счёт").textContent = `Верно ${д.correct} из ${д.total}`;
    $("пробелы").textContent = д.weak_topics.length
      ? "Обратим внимание на: " + д.weak_topics.join(", ")
      : "Пробелов не нашли — стартуем бодро.";
    $("кдалее").href = "/register";

    const разбор = $("разбор");
    разбор.innerHTML = "";
    д.explanations.forEach((э) => {
      const строка = document.createElement("p");
      строка.innerHTML = `${э.correct ? "✅" : "❌"} <span class="тише">${э.text}</span>`;
      разбор.appendChild(строка);
    });
  }

  function принять(значение) {
    ответы.push({ id: текущий.id, answer: значение });
    if (очередь.length) {
      показать(очередь.shift());
    } else {
      отправитьЭтап();
    }
  }

  $("дальше").onclick = () => выбран && принять(выбран);
  $("незнаю").onclick = () => принять("");

  показать(очередь.shift());
})();

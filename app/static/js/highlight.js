// Подсветка синтаксиса Python (требование 2.6).
//
// Своя, а не библиотека с CDN: у проекта нет сборки, а тащить 40 КБ
// стороннего кода ради одного языка и одного экрана незачем. Плюс
// приложение продолжает работать без интернета.
//
// Приём: подсвеченный <pre> лежит ПОД прозрачной textarea и повторяет её
// содержимое и прокрутку. Ввод, выделение, курсор и автодополнение
// браузера остаются штатными, а селектор .редактор, на котором висит
// lesson.js, не меняется.
(() => {
  const КЛЮЧЕВЫЕ = new Set([
    "and","as","assert","async","await","break","class","continue","def","del",
    "elif","else","except","finally","for","from","global","if","import","in",
    "is","lambda","nonlocal","not","or","pass","raise","return","try","while",
    "with","yield","True","False","None","match","case",
  ]);

  const ВСТРОЕННЫЕ = new Set([
    "abs","all","any","bool","dict","dir","enumerate","filter","float","format",
    "frozenset","getattr","hasattr","input","int","isinstance","len","list","map",
    "max","min","next","open","ord","chr","print","range","repr","reversed","round",
    "set","setattr","sorted","str","sum","tuple","type","zip","self",
  ]);

  const экр = (s) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

  // Порядок важен: сначала то, внутри чего подсветка не нужна.
  const ЛЕКСЕМА = new RegExp([
    /#[^\n]*/,                                   // комментарий
    /"""[\s\S]*?"""|'''[\s\S]*?'''/,             // тройные строки
    /"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/,   // обычные строки
    /\b\d+\.?\d*(?:[eE][+-]?\d+)?\b/,            // числа
    /\b[A-Za-z_]\w*\b/,                          // слова
  ].map((р) => р.source).join("|"), "g");

  function подсветить(код) {
    let итог = "", позиция = 0, м;
    ЛЕКСЕМА.lastIndex = 0;
    while ((м = ЛЕКСЕМА.exec(код)) !== null) {
      итог += экр(код.slice(позиция, м.index));
      const т = м[0];
      позиция = м.index + т.length;
      let класс = "";
      if (т[0] === "#") класс = "тк-ком";
      else if (т[0] === '"' || т[0] === "'") класс = "тк-стр";
      else if (/^\d/.test(т)) класс = "тк-чис";
      else if (КЛЮЧЕВЫЕ.has(т)) класс = "тк-кл";
      else if (ВСТРОЕННЫЕ.has(т)) класс = "тк-вст";
      else if (код[позиция] === "(") класс = "тк-фун";
      итог += класс ? `<span class="${класс}">${экр(т)}</span>` : экр(т);
    }
    итог += экр(код.slice(позиция));
    // хвостовой перевод строки нужен, иначе последняя строка «съедается»
    return итог + "\n";
  }

  document.querySelectorAll("textarea.редактор").forEach((поле) => {
    if (поле.closest(".редактор-обёртка")) return;

    const обёртка = document.createElement("div");
    обёртка.className = "редактор-обёртка";
    поле.parentNode.insertBefore(обёртка, поле);

    const слой = document.createElement("pre");
    слой.className = "подсветка";
    слой.setAttribute("aria-hidden", "true");
    обёртка.append(слой, поле);

    const обновить = () => { слой.innerHTML = подсветить(поле.value); };
    const синхронно = () => {
      слой.scrollTop = поле.scrollTop;
      слой.scrollLeft = поле.scrollLeft;
    };

    поле.addEventListener("input", () => { обновить(); синхронно(); });
    поле.addEventListener("scroll", синхронно);

    // Tab внутри редактора — отступ, а не уход фокуса.
    // Esc возвращает штатное поведение, чтобы не запирать клавиатурных пользователей.
    let выпускать = false;
    поле.addEventListener("keydown", (с) => {
      if (с.key === "Escape") { выпускать = true; return; }
      if (с.key !== "Tab" || выпускать) { выпускать = false; return; }
      с.preventDefault();
      const н = поле.selectionStart, к = поле.selectionEnd;
      поле.value = поле.value.slice(0, н) + "    " + поле.value.slice(к);
      поле.selectionStart = поле.selectionEnd = н + 4;
      обновить();
    });

    обновить();
  });
})();

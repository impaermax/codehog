// Окно ошибки: понятный текст и кнопка «Повторить» вместо сырой системной ошибки.
//
// Повтор предлагается только когда он может помочь: обрыв связи или сбой
// сервера (код 500 и выше). Если сервер ответил по делу — «не хватает монет»,
// «вращений нет», — повторять бесполезно, такое сообщение показывается как есть.
// Подробности сбоя сервер уже записал в свой журнал.
(() => {
  // fetch бросает TypeError, когда до сервера не удалось достучаться
  window.ошибкаСвязи = (e) => e instanceof TypeError || (e && e.status >= 500);

  window.текстОшибки = (e) => {
    if (e instanceof TypeError) return "Нет связи с сервером. Проверьте интернет.";
    return (e && e.message) || "Что-то пошло не так.";
  };

  let окно = null;

  window.показатьОшибку = (текст, повторить) => {
    if (окно) окно.remove();
    окно = document.createElement("div");
    окно.className = "тост";
    окно.setAttribute("role", "alert");

    const надпись = document.createElement("span");
    надпись.textContent = текст;
    окно.append(надпись);

    if (повторить) {
      const кнопка = document.createElement("button");
      кнопка.className = "кнопка";
      кнопка.textContent = "Повторить";
      кнопка.onclick = () => { окно.remove(); окно = null; повторить(); };
      окно.append(кнопка);
    }

    const закрыть = document.createElement("button");
    закрыть.className = "тост-закрыть";
    закрыть.setAttribute("aria-label", "Закрыть");
    закрыть.textContent = "✕";
    закрыть.onclick = () => { окно.remove(); окно = null; };
    окно.append(закрыть);

    document.body.append(окно);
  };

  // Ошибку с кодом ответа удобно бросать одной строкой
  window.ошибкаОтвета = (ответ, данные) => {
    const e = new Error((данные && данные.detail) || "Не получилось");
    e.status = ответ.status;
    return e;
  };
})();

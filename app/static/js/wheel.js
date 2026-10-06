// Колесо: приз определяет сервер, браузер только показывает анимацию.
(() => {
  const БАЗА = window.БАЗА || "";
  const окно = document.getElementById("окно-колеса");
  const колесо = document.getElementById("колесо");
  const крутить = document.getElementById("крутить");
  const итог = document.getElementById("итог-колеса");
  const баланс = document.getElementById("баланс");
  if (!окно) return;

  let угол = 0;
  let вРаботе = false;

  document.getElementById("открыть-колесо").onclick = () => окно.classList.add("видно");
  document.getElementById("закрыть-колесо").onclick = () => окно.classList.remove("видно");
  окно.onclick = (e) => { if (e.target === окно) окно.classList.remove("видно"); };

  крутить.onclick = async () => {
    if (вРаботе) return;
    вРаботе = true;
    крутить.disabled = true;

    let данные;
    try {
      const ответ = await fetch(`${БАЗА}/hog/wheel/spin`, { method: "POST" });
      данные = await ответ.json();
      if (!ответ.ok) throw ошибкаОтвета(ответ, данные);
    } catch (e) {
      // кнопку возвращаем, иначе после сбоя колесо не крутится до перезагрузки
      вРаботе = false;
      крутить.disabled = false;
      if (ошибкаСвязи(e)) {
        показатьОшибку(текстОшибки(e), () => крутить.click());
      } else {
        итог.textContent = e.message;
      }
      return;
    }

    // сектора идут по кругу; докручиваем несколько полных оборотов для эффекта
    const секторов = 5;
    const шаг = 360 / секторов;
    угол += 360 * 4 + (секторов - данные.sector) * шаг;
    колесо.style.transform = `rotate(${угол}deg)`;

    setTimeout(() => {
      итог.innerHTML = `Выпало <b style="color:var(--золото)">${данные.coins_won}</b> монет · ` +
                       `осталось вращений: <b>${данные.spins_left}</b>`;
      if (баланс) баланс.textContent = данные.coins;
      крутить.disabled = данные.spins_left <= 0;
      вРаботе = false;
    }, 4100);
  };
})();

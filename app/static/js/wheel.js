// Колесо: приз определяет сервер, браузер только показывает анимацию.
(() => {
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
      const ответ = await fetch("/hog/wheel/spin", { method: "POST" });
      данные = await ответ.json();
      if (!ответ.ok) throw new Error(данные.detail || "Не получилось");
    } catch (e) {
      итог.textContent = e.message;
      вРаботе = false;
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

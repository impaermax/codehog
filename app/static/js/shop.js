// Покупка и экипировка. После действия перезагружаем страницу — ёж перерисуется на сервере.
(() => {
  const БАЗА = window.БАЗА || "";
  document.querySelectorAll(".товар").forEach((карточка) => {
    const sku = карточка.dataset.sku;
    const сообщение = карточка.querySelector(".сообщение");

    const действие = async (адрес, кнопка) => {
      кнопка.disabled = true;
      try {
        const ответ = await fetch(адрес, { method: "POST" });
        const д = await ответ.json();
        if (!ответ.ok) throw ошибкаОтвета(ответ, д);
        location.reload();
      } catch (e) {
        кнопка.disabled = false;
        if (ошибкаСвязи(e)) {
          показатьОшибку(текстОшибки(e), () => действие(адрес, кнопка));
        } else {
          сообщение.textContent = e.message;   // «не хватает монет» и подобное
        }
      }
    };

    const купить = карточка.querySelector(".купить");
    if (купить) купить.onclick = () => действие(`${БАЗА}/hog/shop/buy/${sku}`, купить);

    const надеть = карточка.querySelector(".надеть");
    if (надеть) надеть.onclick = () => действие(`${БАЗА}/hog/shop/equip/${sku}`, надеть);
  });
})();

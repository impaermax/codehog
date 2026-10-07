// Buying a skin and making it active. After the action the page reloads,
// so the server redraws the hedgehog.
(() => {
  const BASE_PATH = window.BASE_PATH || "";

  document.querySelectorAll(".product").forEach((card) => {
    const sku = card.dataset.sku;
    const message = card.querySelector(".message");

    const run = async (url, button) => {
      button.disabled = true;
      try {
        const response = await fetch(url, { method: "POST" });
        const data = await response.json();
        if (!response.ok) throw responseError(response, data);
        location.reload();
      } catch (error) {
        button.disabled = false;
        if (isNetworkError(error)) {
          showError(errorText(error), () => run(url, button));
        } else {
          message.textContent = error.message;  // "not enough coins" and the like
        }
      }
    };

    const buyButton = card.querySelector(".buy-btn");
    if (buyButton) buyButton.onclick = () => run(`${BASE_PATH}/hog/shop/buy/${sku}`, buyButton);

    const equipButton = card.querySelector(".equip-btn");
    if (equipButton) equipButton.onclick = () => run(`${BASE_PATH}/hog/shop/equip/${sku}`, equipButton);
  });
})();

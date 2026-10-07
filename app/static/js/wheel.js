// Wheel of fortune: the server picks the prize, the browser only animates it.
(() => {
  const BASE_PATH = window.BASE_PATH || "";
  const SECTOR_COUNT = 5;
  const SPIN_DURATION_MS = 4100;

  const modal = document.getElementById("wheel-modal");
  if (!modal) return;
  const wheel = document.getElementById("wheel");
  const spinButton = document.getElementById("spin-btn");
  const result = document.getElementById("wheel-result");
  const balance = document.getElementById("balance");

  let angle = 0;
  let spinning = false;

  document.getElementById("open-wheel").onclick = () => modal.classList.add("visible");
  document.getElementById("close-wheel").onclick = () => modal.classList.remove("visible");
  modal.onclick = (event) => { if (event.target === modal) modal.classList.remove("visible"); };

  spinButton.onclick = async () => {
    if (spinning) return;
    spinning = true;
    spinButton.disabled = true;

    let data;
    try {
      const response = await fetch(`${BASE_PATH}/hog/wheel/spin`, { method: "POST" });
      data = await response.json();
      if (!response.ok) throw responseError(response, data);
    } catch (error) {
      // Re-enable the button, otherwise the wheel stays stuck until a reload
      spinning = false;
      spinButton.disabled = false;
      if (isNetworkError(error)) {
        showError(errorText(error), () => spinButton.click());
      } else {
        result.textContent = error.message;
      }
      return;
    }

    // Sectors go round the circle; add a few full turns for effect
    const sectorAngle = 360 / SECTOR_COUNT;
    angle += 360 * 4 + (SECTOR_COUNT - data.sector) * sectorAngle;
    wheel.style.transform = `rotate(${angle}deg)`;

    setTimeout(() => {
      result.innerHTML = `Выпало <b style="color:var(--gold)">${data.coins_won}</b> монет · ` +
                         `осталось вращений: <b>${data.spins_left}</b>`;
      if (balance) balance.textContent = data.coins;
      spinButton.disabled = data.spins_left <= 0;
      spinning = false;
    }, SPIN_DURATION_MS);
  };
})();

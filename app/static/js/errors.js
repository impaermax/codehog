// Error toast: a clear message and a "Retry" button instead of a raw system error.
//
// Retry is offered only when it can help: a lost connection or a server failure
// (status 500 and above). When the server answered on purpose ("not enough
// coins", "no spins left"), retrying is pointless, so the message is shown as is.
// The server has already logged the details of any failure.
(() => {
  // fetch throws a TypeError when the server cannot be reached at all
  window.isNetworkError = (error) => error instanceof TypeError || (error && error.status >= 500);

  window.errorText = (error) => {
    if (error instanceof TypeError) return "Нет связи с сервером. Проверьте интернет.";
    return (error && error.message) || "Что-то пошло не так.";
  };

  let toast = null;

  const closeToast = () => {
    if (toast) toast.remove();
    toast = null;
  };

  window.showError = (message, retry) => {
    closeToast();
    toast = document.createElement("div");
    toast.className = "toast";
    toast.setAttribute("role", "alert");

    const text = document.createElement("span");
    text.textContent = message;
    toast.append(text);

    if (retry) {
      const retryButton = document.createElement("button");
      retryButton.className = "btn";
      retryButton.textContent = "Повторить";
      retryButton.onclick = () => { closeToast(); retry(); };
      toast.append(retryButton);
    }

    const closeButton = document.createElement("button");
    closeButton.className = "toast-close";
    closeButton.setAttribute("aria-label", "Закрыть");
    closeButton.textContent = "✕";
    closeButton.onclick = closeToast;
    toast.append(closeButton);

    document.body.append(toast);
  };

  // An Error that carries the HTTP status, so callers can throw it in one line
  window.responseError = (response, data) => {
    const error = new Error((data && data.detail) || "Не получилось");
    error.status = response.status;
    return error;
  };
})();

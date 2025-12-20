// ===============================
// LOGIN UX İYİLEŞTİRMELERİ
// ===============================

document.addEventListener("DOMContentLoaded", () => {
    const loginForm = document.querySelector("form[action*='login']");
    if (!loginForm) return;

    const usernameInput = loginForm.querySelector("input[name='username']");
    const passwordInput = loginForm.querySelector("input[name='password']");
    const submitBtn = loginForm.querySelector("button[type='submit']");

    // Submit olunca loading + disable
    loginForm.addEventListener("submit", () => {
        submitBtn.classList.add("login-loading");
        submitBtn.disabled = true;
    });

    // Input yazınca hata stillerini temizle
    [usernameInput, passwordInput].forEach(input => {
        if (!input) return;
        input.addEventListener("input", () => {
            input.classList.remove("is-invalid");
            input.classList.add("is-valid");
        });
    });
});

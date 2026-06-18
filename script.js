const yearNode = document.querySelector("[data-year]");
const copyButton = document.querySelector("[data-copy-email]");
const copyStatus = document.querySelector(".copy-status");
const email = "hello@example.com";

if (yearNode) {
  yearNode.textContent = new Date().getFullYear();
}

if (copyButton && copyStatus) {
  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(email);
      copyStatus.textContent = "Email скопирован.";
    } catch {
      copyStatus.textContent = `Email: ${email}`;
    }
  });
}

const revealItems = document.querySelectorAll(".reveal");

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.2 },
  );

  revealItems.forEach((item) => observer.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}

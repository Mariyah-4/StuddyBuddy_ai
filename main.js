document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menuToggle");
  const sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) toggle.addEventListener("click", () => sidebar.classList.toggle("sidebar-open"));

  const fileInput = document.getElementById("syllabusFile");
  const fileName = document.getElementById("fileName");
  if (fileInput && fileName) fileInput.addEventListener("change", () => {
    fileName.textContent = fileInput.files.length ? fileInput.files[0].name : "Drop a file here or click to browse";
  });

  const messages = document.getElementById("chatMessages");
  if (messages) messages.scrollTop = messages.scrollHeight;
  document.querySelectorAll("[data-prompt]").forEach(btn => btn.addEventListener("click", () => {
    const input = document.getElementById("chatInput");
    if (input) { input.value = btn.dataset.prompt; input.focus(); }
  }));
});

document.addEventListener("DOMContentLoaded", function () {
  const uploadButton = document.getElementById("uploadButton");
  const fileInput = document.getElementById("fileInput");
  const submitButton = document.getElementById("submitButton");
  const loader = document.getElementById("load");

  if (uploadButton && fileInput) {
    uploadButton.addEventListener("click", function () {
      fileInput.click();
    });
    fileInput.addEventListener("change", function () {
      if (submitButton) {
        submitButton.style.display = "block";
      }
    });
  }
  if (submitButton) {
    submitButton.addEventListener("click", function () {
      load.style.display = "flex";
    });
  }
});

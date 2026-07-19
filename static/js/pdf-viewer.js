/* RegulaVasc — PDF.js Mobile Viewer
   Carrega PDF.js via jsDelivr CDN e gerencia navegação/zoom.
   Uso: pdfViewer.init(pdfUrl, options)
*/

const pdfViewer = (function () {
  "use strict";

  let pdfDoc = null;
  let currentPage = 1;
  let totalPages = 0;
  let scale = 1.0;
  let canvas = null;
  let ctx = null;
  let pdfjsLib = null;
  let isLoading = false;

  const MIN_SCALE = 0.5;
  const MAX_SCALE = 4.0;
  const SCALE_STEP = 0.25;

  const elements = {
    canvas: null,
    pageInfo: null,
    prevBtn: null,
    nextBtn: null,
    zoomInBtn: null,
    zoomOutBtn: null,
    zoomLevel: null,
    loading: null,
    error: null,
    container: null,
    pageInput: null,
    goToBtn: null,
  };

  function getElement(id) {
    const el = document.getElementById(id);
    if (!el) console.warn("pdfViewer: elemento #" + id + " não encontrado.");
    return el;
  }

  function cacheElements() {
    elements.canvas = getElement("pdf-canvas");
    elements.pageInfo = getElement("page-info");
    elements.prevBtn = getElement("prev-page");
    elements.nextBtn = getElement("next-page");
    elements.zoomInBtn = getElement("zoom-in");
    elements.zoomOutBtn = getElement("zoom-out");
    elements.zoomLevel = getElement("zoom-level");
    elements.loading = getElement("pdf-loading");
    elements.error = getElement("pdf-error");
    elements.container = getElement("pdf-container");
    elements.pageInput = getElement("page-input");
    elements.goToBtn = getElement("go-to-page");
  }

  function showLoading(show) {
    if (elements.loading) {
      elements.loading.style.display = show ? "block" : "none";
    }
    isLoading = show;
  }

  function showError(msg) {
    if (elements.error) {
      elements.error.style.display = "block";
      elements.error.textContent = msg;
    }
    if (elements.loading) {
      elements.loading.style.display = "none";
    }
    if (elements.container) {
      elements.container.style.display = "none";
    }
    isLoading = false;
  }

  function updatePageInfo() {
    if (elements.pageInfo) {
      elements.pageInfo.textContent = "Página " + currentPage + " de " + totalPages;
    }
    if (elements.pageInput) {
      elements.pageInput.value = currentPage;
      elements.pageInput.max = totalPages;
    }
    if (elements.prevBtn) {
      elements.prevBtn.disabled = currentPage <= 1;
    }
    if (elements.nextBtn) {
      elements.nextBtn.disabled = currentPage >= totalPages;
    }
  }

  function updateZoomLevel() {
    if (elements.zoomLevel) {
      elements.zoomLevel.textContent = Math.round(scale * 100) + "%";
    }
  }

  function renderPage(num) {
    if (!pdfDoc || isLoading) return;

    showLoading(true);

    pdfDoc.getPage(num).then(function (page) {
      var viewport = page.getViewport({ scale: scale });

      if (canvas) {
        canvas.width = viewport.width;
        canvas.height = viewport.height;
      }

      var renderContext = {
        canvasContext: ctx,
        viewport: viewport,
      };

      var renderTask = page.render(renderContext);
      renderTask.promise.then(
        function () {
          showLoading(false);
          updatePageInfo();
        },
        function (err) {
          showLoading(false);
          if (err && err.name !== "RenderingCancelledException") {
            console.error("Erro ao renderizar página:", err);
          }
        }
      );
    }).catch(function (err) {
      showLoading(false);
      console.error("Erro ao carregar página:", err);
      showError("Erro ao carregar página " + num + ".");
    });
  }

  function changePage(delta) {
    var newPage = currentPage + delta;
    if (newPage < 1 || newPage > totalPages) return;
    currentPage = newPage;
    renderPage(currentPage);
  }

  function goToPage(num) {
    var page = parseInt(num, 10);
    if (isNaN(page) || page < 1 || page > totalPages) return;
    currentPage = page;
    renderPage(currentPage);
  }

  function zoomIn() {
    scale = Math.min(scale + SCALE_STEP, MAX_SCALE);
    updateZoomLevel();
    if (pdfDoc) renderPage(currentPage);
  }

  function zoomOut() {
    scale = Math.max(scale - SCALE_STEP, MIN_SCALE);
    updateZoomLevel();
    if (pdfDoc) renderPage(currentPage);
  }

  function setupKeyboard() {
    document.addEventListener("keydown", function (e) {
      // Ignorar se foco está em input
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

      if (e.key === "ArrowLeft" || e.key === "PageUp") {
        e.preventDefault();
        changePage(-1);
      } else if (e.key === "ArrowRight" || e.key === "PageDown") {
        e.preventDefault();
        changePage(1);
      } else if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        zoomIn();
      } else if (e.key === "-") {
        e.preventDefault();
        zoomOut();
      } else if (e.key === "Home") {
        e.preventDefault();
        goToPage(1);
      } else if (e.key === "End") {
        e.preventDefault();
        goToPage(totalPages);
      }
    });
  }

  function setupTouch(containerEl) {
    var touchStartX = 0;
    var touchStartY = 0;
    var touchHandled = false;

    containerEl.addEventListener("touchstart", function (e) {
      if (e.touches.length === 1) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
        touchHandled = false;
      }
    }, { passive: true });

    containerEl.addEventListener("touchmove", function (e) {
      if (e.touches.length === 1 && !touchHandled) {
        var dx = e.touches[0].clientX - touchStartX;
        var dy = e.touches[0].clientY - touchStartY;
        // Swipe horizontal (|dx| > 30 e mais horizontal que vertical)
        if (Math.abs(dx) > 30 && Math.abs(dx) > Math.abs(dy) * 1.5) {
          touchHandled = true;
          if (dx > 0) {
            changePage(-1); // swipe right → página anterior
          } else {
            changePage(1);  // swipe left → próxima página
          }
        }
      }
    }, { passive: true });
  }

  function bindUI() {
    if (elements.prevBtn) {
      elements.prevBtn.addEventListener("click", function () { changePage(-1); });
    }
    if (elements.nextBtn) {
      elements.nextBtn.addEventListener("click", function () { changePage(1); });
    }
    if (elements.zoomInBtn) {
      elements.zoomInBtn.addEventListener("click", zoomIn);
    }
    if (elements.zoomOutBtn) {
      elements.zoomOutBtn.addEventListener("click", zoomOut);
    }
    if (elements.pageInput && elements.goToBtn) {
      elements.goToBtn.addEventListener("click", function () {
        goToPage(elements.pageInput.value);
      });
      elements.pageInput.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          goToPage(elements.pageInput.value);
        }
      });
    }
  }

  /* API pública */
  return {
    init: function (pdfUrl, options) {
      options = options || {};
      cacheElements();

      canvas = elements.canvas;
      if (!canvas) {
        showError("Erro: canvas não encontrado.");
        return;
      }
      ctx = canvas.getContext("2d");

      if (options.scale) scale = options.scale;
      updateZoomLevel();
      bindUI();
      setupKeyboard();

      if (elements.container) {
        setupTouch(elements.container);
      }

      showLoading(true);

      // Carrega PDF.js via jsDelivr CDN
      var script = document.createElement("script");
      script.src = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.0.379/build/pdf.min.mjs";
      script.type = "module";
      script.onload = function () {
        // pdfjsLib is available as global after module import
        // We need to use dynamic import instead for module type
        import("https://cdn.jsdelivr.net/npm/pdfjs-dist@4.0.379/build/pdf.min.mjs").then(function (mod) {
          pdfjsLib = mod;
          if (pdfjsLib.GlobalWorkerOptions) {
            pdfjsLib.GlobalWorkerOptions.workerSrc =
              "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.0.379/build/pdf.worker.min.mjs";
          }
          loadPdf(pdfUrl);
        }).catch(function (err) {
          showError("Erro ao carregar PDF.js: " + (err.message || "desconhecido"));
        });
      };
      script.onerror = function () {
        showError("Erro ao carregar PDF.js do CDN. Verifique sua conexão.");
      };
      document.head.appendChild(script);
    },

    destroy: function () {
      pdfDoc = null;
      currentPage = 1;
      totalPages = 0;
      scale = 1.0;
      isLoading = false;
      if (canvas) {
        canvas.width = 0;
        canvas.height = 0;
      }
    },
  };

  function loadPdf(pdfUrl) {
    if (!pdfjsLib) {
      showError("PDF.js não carregado.");
      return;
    }

    var loadingTask = pdfjsLib.getDocument(pdfUrl);
    loadingTask.promise.then(
      function (pdf) {
        pdfDoc = pdf;
        totalPages = pdf.numPages;
        showLoading(false);
        if (elements.container) elements.container.style.display = "block";
        updatePageInfo();
        renderPage(1);
      },
      function (err) {
        showError("Erro ao carregar PDF: " + (err.message || "arquivo inválido ou inacessível."));
      }
    );
  }
})();
